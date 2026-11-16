"""Cert Manager deploy vs Default Ingress playbook selection gates.

Covers the four Step 4 combinations for both AAP-style (controller flag) and
No-AAP (preflight-only) resolution. The ingress playbook must survive when
``update_default_ingress`` is set even if ``aap_config_vars.yml`` is skipped.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

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
            "playbooks/cert-manager/"
            "ado-update-default-ingress-cert-bootstrap.yml"
        )
    },
]

DEPLOY = "playbooks/cert-manager/ado-deploy-and-configure-bootstrap.yml"
INGRESS = (
    "playbooks/cert-manager/ado-update-default-ingress-cert-bootstrap.yml"
)


def _dests(kept):
    return [item["dest"] for item in kept]


@pytest.mark.parametrize(
    "want_deploy,want_ingress,expect_deploy,expect_ingress",
    [
        (False, False, False, False),
        (True, False, True, False),
        (False, True, False, True),
        (True, True, True, True),
    ],
)
def test_filter_four_combinations(
    want_deploy, want_ingress, expect_deploy, expect_ingress
):
    kept = local_components.filter_cert_manager(
        CATALOGUE,
        mode="cert",
        update_default_ingress=want_ingress,
        want_deploy=want_deploy,
    )
    dests = _dests(kept)
    assert (DEPLOY in dests) is expect_deploy
    assert (INGRESS in dests) is expect_ingress
    assert all("idm-acme" not in d for d in dests)
    assert all("awspca" not in d for d in dests)


@pytest.mark.parametrize(
    "preflight,expect_deploy,expect_ingress",
    [
        (
            {
                "components": ["openshift"],
                "component_apps": {"openshift": []},
                "component_options": {"openshift": []},
                "component_config": {"cert_manager": {}},
                "selected_component_apps": [],
            },
            False,
            False,
        ),
        (
            {
                "components": ["openshift"],
                "component_apps": {"openshift": ["cert_manager"]},
                "component_options": {"openshift": []},
                "component_config": {"cert_manager": {"mode": "cert"}},
                "selected_component_apps": ["cert_manager"],
            },
            True,
            False,
        ),
        (
            {
                "components": ["openshift"],
                "component_apps": {"openshift": []},
                "component_options": {
                    "openshift": ["update_default_ingress"]
                },
                "component_config": {
                    "cert_manager": {"update_default_ingress": True}
                },
                "selected_component_apps": [],
            },
            False,
            True,
        ),
        (
            {
                "components": ["openshift"],
                "component_apps": {"openshift": ["cert_manager"]},
                "component_options": {
                    "openshift": ["update_default_ingress"]
                },
                "component_config": {
                    "cert_manager": {
                        "mode": "cert",
                        "update_default_ingress": True,
                    }
                },
                "selected_component_apps": ["cert_manager"],
            },
            True,
            True,
        ),
    ],
)
def test_resolve_intent_from_preflight_no_aap(
    preflight, expect_deploy, expect_ingress
):
    intent = local_components.resolve_cert_manager_playbook_intent(preflight)
    assert intent["want_deploy"] is expect_deploy
    assert intent["want_ingress"] is expect_ingress
    kept = local_components.filter_cert_manager(
        CATALOGUE,
        mode=intent["mode"],
        update_default_ingress=intent["want_ingress"],
        want_deploy=intent["want_deploy"],
    )
    dests = _dests(kept)
    assert (DEPLOY in dests) is expect_deploy
    assert (INGRESS in dests) is expect_ingress


def test_aap_style_controller_flag_keeps_ingress_without_deploy():
    """AAP path sets bootstrap_controller_update_default_ingress; deploy stays independent."""
    intent = local_components.resolve_cert_manager_playbook_intent(
        {
            "components": ["openshift"],
            "component_apps": {"openshift": []},
            "component_options": {"openshift": []},
            "component_config": {"cert_manager": {}},
        },
        update_default_ingress=True,
        want_deploy=False,
    )
    assert intent["want_ingress"] is True
    assert intent["want_deploy"] is False
    kept = local_components.filter_cert_manager(
        CATALOGUE,
        update_default_ingress=True,
        want_deploy=False,
    )
    assert INGRESS in _dests(kept)
    assert DEPLOY not in _dests(kept)


def test_tasks_gate_reads_preflight_and_drops_deploy_when_not_explicit():
    tasks = (
        ROOT / "roles/bootstrap_generate_playbook_repo/tasks/main.yml"
    ).read_text(encoding="utf-8")
    assert "bootstrap_generate_env_vars_preflight.component_config.cert_manager" in tasks
    assert "Drop cert-manager deploy unless explicitly selected" in tasks
    assert "ado-deploy-and-configure-bootstrap.yml" in tasks
    env_tasks = (
        ROOT / "roles/bootstrap_generate_env_vars/tasks/main.yml"
    ).read_text(encoding="utf-8")
    assert "Publish cert-manager playbook gates from preflight" in env_tasks
    assert "bootstrap_controller_update_default_ingress" in env_tasks
    assert "bootstrap_controller_cert_manager_explicit" in env_tasks
