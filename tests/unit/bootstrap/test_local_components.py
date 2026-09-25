"""Unit tests for local_components pure helpers.

Regression coverage that used to live only in the removed
``integration_local_components`` Molecule scenario.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = (
    ROOT
    / "roles/bootstrap_generate_playbook_repo/files/local_components.py"
)
_SPEC = importlib.util.spec_from_file_location("local_components", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
local_components = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(local_components)


CATALOGUE = [
    {"dest": "playbooks/cert-manager/ado-deploy-and-configure-bootstrap.yml"},
    {"dest": "playbooks/cert-manager/ado-configure-idm-acme-clusterissuer.yml"},
    {
        "dest": (
            "playbooks/cert-manager/"
            "ado-install-and-configure-awspca-bootstrap.yml"
        )
    },
    {
        "dest": (
            "playbooks/openshift/"
            "ado-update-default-ingress-cert-bootstrap.yml"
        )
    },
]


def test_filter_cert_manager_default_mode_keeps_core_only() -> None:
    kept = local_components.filter_cert_manager(CATALOGUE, mode="cert")
    dests = [item["dest"] for item in kept]
    assert dests == [
        "playbooks/cert-manager/ado-deploy-and-configure-bootstrap.yml",
    ]


def test_filter_cert_manager_idm_acme_includes_issuer() -> None:
    kept = local_components.filter_cert_manager(CATALOGUE, mode="idm_acme")
    dests = [item["dest"] for item in kept]
    assert "ado-configure-idm-acme-clusterissuer.yml" in dests[1]
    assert all("awspca" not in dest for dest in dests)


def test_filter_cert_manager_aws_pca_and_ingress() -> None:
    kept = local_components.filter_cert_manager(
        CATALOGUE,
        mode="aws_pca",
        update_default_ingress=True,
    )
    dests = [item["dest"] for item in kept]
    assert any("awspca" in dest for dest in dests)
    assert any("update-default-ingress" in dest for dest in dests)
    assert all("idm-acme" not in dest for dest in dests)


def test_workflow_playbooks_expands_nested_workflow() -> None:
    names = {
        "ADO | Deploy RHBK": "playbooks/rhbk/ado-deploy-and-configure-bootstrap.yml",
        "ADO | Configure OAuth": "playbooks/openshift/ado-configure-oauth-bootstrap.yml",
    }
    workflows = {
        "ADO | RHBK Workflow": {
            "simplified_workflow_nodes": [
                {
                    "identifier": "deploy",
                    "unified_job_template": "ADO | Deploy RHBK",
                    "success_nodes": ["oauth"],
                },
                {
                    "identifier": "oauth",
                    "unified_job_template": "ADO | Configure OAuth",
                },
            ]
        }
    }
    playbooks = local_components._workflow_playbooks(
        "ADO | RHBK Workflow",
        names,
        workflows,
    )
    assert playbooks == {
        "playbooks/rhbk/ado-deploy-and-configure-bootstrap.yml",
        "playbooks/openshift/ado-configure-oauth-bootstrap.yml",
    }


def test_workflow_playbooks_cycle_safe() -> None:
    names = {}
    workflows = {
        "A": {
            "simplified_workflow_nodes": [
                {"unified_job_template": "B"},
            ]
        },
        "B": {
            "simplified_workflow_nodes": [
                {"unified_job_template": "A"},
            ]
        },
    }
    assert local_components._workflow_playbooks("A", names, workflows) == set()


def test_is_day2_helper_detects_enable_realm() -> None:
    assert local_components.is_day2_helper(
        "playbooks/rhbk/ado-enable-realm-bootstrap.yml",
        "ADO | Enable Realm",
    )
    assert not local_components.is_day2_helper(
        "playbooks/rhbk/ado-deploy-and-configure-bootstrap.yml",
        "ADO | Deploy RHBK",
    )


def test_order_selected_respects_hard_edges_and_selection_ties() -> None:
    edges = {
        "playbooks/b.yml": {"playbooks/a.yml"},
    }
    by_id = {
        "playbooks/a.yml": {"id": "playbooks/a.yml", "title": "A"},
        "playbooks/b.yml": {"id": "playbooks/b.yml", "title": "B"},
        "playbooks/c.yml": {"id": "playbooks/c.yml", "title": "C"},
    }
    # c before a in selection, but a must still run before b.
    ordered = local_components.order_selected(
        ["playbooks/c.yml", "playbooks/b.yml", "playbooks/a.yml"],
        by_id,
        edges,
    )
    ids = [step["id"] for step in ordered]
    assert ids.index("playbooks/a.yml") < ids.index("playbooks/b.yml")
    assert ids[0] == "playbooks/c.yml"
