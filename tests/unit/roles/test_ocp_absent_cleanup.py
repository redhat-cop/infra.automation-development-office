# SPDX-License-Identifier: GPL-3.0-or-later
"""Safety tests for namespace deletion and OLM cleanup selection."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_filter():
    path = ROOT / "plugins" / "filter" / "ocp_absent_cleanup.py"
    spec = importlib.util.spec_from_file_location("ocp_absent_cleanup_filter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = _load_filter()


def _csv(name, namespace, copied_from="", operator_namespace="", finalizers=None):
    labels = {}
    annotations = {}
    if copied_from:
        labels["olm.copiedFrom"] = copied_from
    if operator_namespace:
        annotations["olm.operatorNamespace"] = operator_namespace
    return {
        "kind": "ClusterServiceVersion",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
            "annotations": annotations,
            "finalizers": finalizers or [],
        },
    }


def test_platform_namespaces_cannot_be_deleted():
    for name in (
        "default",
        "kube-system",
        "kube-public",
        "kube-node-lease",
        "openshift",
        "openshift-etcd",
        "openshift-monitoring",
        "openshift-operators",
        "openshift-operator-lifecycle-manager",
        "kube-anything",
        "",
        " ",
        "*",
        "a,b",
        "ns/other",
    ):
        assert F.namespace_delete_blocked(name), name


def test_component_namespaces_can_be_deleted():
    for name in ("test-namespace", "cert-manager", "cert-manager-operator", "openshift-gitops", "grafana"):
        assert not F.namespace_delete_blocked(name), name


def test_cleanup_refuses_platform_and_broad_shared_operators():
    assert F.cleanup_refused("kube-system", {"mode": "check"})
    assert F.cleanup_refused("openshift-etcd", {"mode": "cleanup"})
    assert F.cleanup_refused(
        "openshift-operators",
        {
            "mode": "cleanup",
            "sweep_olm": True,
            "csv_name_match": "",
            "authorize_unfiltered_csv_delete": True,
        },
    )
    assert F.cleanup_refused(
        "openshift-operators",
        {"mode": "cleanup", "sweep_workloads": True, "csv_name_match": "gitops"},
    )
    assert F.cleanup_refused(
        "openshift-operators",
        {"mode": "cleanup", "delete_copied_csvs": True, "csv_name_match": "gitops"},
    )
    assert not F.cleanup_refused(
        "openshift-operators",
        {
            "mode": "cleanup",
            "sweep_olm": True,
            "csv_name_match": "cert-manager",
            "authorize_unfiltered_csv_delete": False,
            "delete_copied_csvs": False,
            "sweep_workloads": False,
        },
    )
    assert not F.cleanup_refused("openshift-operators", {"mode": "check"})
    assert not F.cleanup_refused("test-namespace", {"mode": "cleanup", "sweep_olm": True})
    assert not F.cleanup_refused("openshift-gitops", {"mode": "cleanup"})


def test_default_csv_selection_is_empty():
    copied = _csv(
        "cert-manager-operator.v1.20.1",
        "test-namespace",
        copied_from="cert-manager-operator",
        operator_namespace="cert-manager-operator",
    )
    original = _csv(
        "cert-manager-operator.v1.20.1",
        "cert-manager-operator",
        operator_namespace="cert-manager-operator",
    )
    foreign = _csv(
        "openshift-gitops-operator.v1.21.1",
        "openshift-operators",
        operator_namespace="openshift-operators",
    )
    resources = [copied, original, foreign]
    assert F.select_csvs(resources, "test-namespace") == []
    assert (
        F.select_csvs(
            resources,
            "test-namespace",
            authorize_csv_delete=True,
            authorize_unfiltered_csv_delete=True,
        )
        == []
    )
    assert (
        F.select_csvs(
            resources,
            "test-namespace",
            csv_name_match="cert-manager",
            authorize_csv_delete=True,
        )
        == []
    )


def test_copied_csvs_require_explicit_authorization():
    copied = _csv(
        "openshift-gitops-operator.v1.21.1",
        "test-namespace",
        copied_from="openshift-operators",
        operator_namespace="openshift-operators",
    )
    assert F.is_olm_copy(copied, "test-namespace")
    assert not F.is_olm_copy(
        _csv(
            "openshift-gitops-operator.v1.21.1",
            "openshift-operators",
            operator_namespace="openshift-operators",
        ),
        "openshift-operators",
    )
    selected = F.select_csvs(
        [copied],
        "test-namespace",
        authorize_csv_delete=True,
        authorize_unfiltered_csv_delete=True,
        delete_copied_csvs=True,
    )
    assert [item["metadata"]["name"] for item in selected] == ["openshift-gitops-operator.v1.21.1"]
    assert all(item["metadata"]["namespace"] == "test-namespace" for item in selected)


def test_name_match_stays_in_the_operator_namespace():
    original = _csv(
        "cert-manager-operator.v1.20.1",
        "cert-manager-operator",
        operator_namespace="cert-manager-operator",
    )
    other = _csv(
        "quay-operator.v3.17.6",
        "cert-manager-operator",
        operator_namespace="quay-enterprise",
    )
    leaked = _csv(
        "cert-manager-operator.v1.20.1",
        "openshift-operators",
        operator_namespace="cert-manager-operator",
    )
    selected = F.select_csvs(
        [original, other, leaked],
        "cert-manager-operator",
        csv_name_match="cert-manager-operator",
        authorize_csv_delete=True,
    )
    assert selected == [original]
    assert (
        F.select_csvs(
            [original],
            "cert-manager-operator",
            csv_name_match="cert-manager",
            authorize_csv_delete=True,
        )
        == []
    )
    assert not F.csv_name_matches("openshift-gitops-operator.v1.21.1", "operator")
    assert F.csv_name_matches("cert-manager-operator.v1.20.1", "cert-manager-operator")
    assert F.csv_name_matches("cert-manager-operator.v1.20.1", "cert-manager-operator.v1.20.1")


def test_unfiltered_authorization_does_not_cross_namespaces():
    local = _csv("custom.v1", "test-namespace")
    remote = _csv("custom.v1", "openshift-operators")
    selected = F.select_csvs(
        [local, remote],
        "test-namespace",
        authorize_csv_delete=True,
        authorize_unfiltered_csv_delete=True,
    )
    assert selected == [local]
    assert F.select_csvs(
        [local],
        "test-namespace",
        authorize_csv_delete=True,
        authorize_unfiltered_csv_delete=False,
    ) == []


def test_workloads_and_installplans_stay_in_namespace():
    deploy_local = {"metadata": {"name": "api", "namespace": "grafana"}}
    deploy_other = {"metadata": {"name": "api", "namespace": "openshift-monitoring"}}
    assert F.select_workloads([deploy_local, deploy_other], "grafana") == []
    assert F.select_workloads(
        [deploy_local, deploy_other],
        "grafana",
        authorize_unfiltered=True,
    ) == [deploy_local]
    assert F.select_workloads(
        [deploy_local, deploy_other],
        "grafana",
        names=["api"],
    ) == [deploy_local]
    plan_local = {
        "metadata": {"name": "install-1", "namespace": "cert-manager-operator"},
        "spec": {"clusterServiceVersionNames": ["cert-manager-operator.v1.20.1"]},
    }
    plan_other = {
        "metadata": {"name": "install-2", "namespace": "openshift-operators"},
        "spec": {"clusterServiceVersionNames": ["cert-manager-operator.v1.20.1"]},
    }
    assert F.select_installplans([plan_local, plan_other], "cert-manager-operator") == []
    selected = F.select_installplans(
        [plan_local, plan_other],
        "cert-manager-operator",
        csv_name_match="cert-manager-operator",
        authorize_csv_delete=True,
    )
    assert selected == [plan_local]
    mixed = {
        "metadata": {"name": "install-mixed", "namespace": "cert-manager-operator"},
        "spec": {
            "clusterServiceVersionNames": [
                "cert-manager-operator.v1.20.1",
                "openshift-gitops-operator.v1.21.1",
            ]
        },
    }
    assert (
        F.select_installplans(
            [mixed],
            "cert-manager-operator",
            csv_name_match="cert-manager-operator",
            authorize_csv_delete=True,
        )
        == []
    )


def _text(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_namespace_role_does_not_enable_cleanup_by_default():
    main = _text("roles/ocp_namespace/tasks/main.yml")
    advanced = _text("roles/ocp_namespace/tasks/advanced_cleanup.yml")
    defaults = _text("roles/ocp_namespace/defaults/main.yml")
    assert "sweep_olm | default(true)" not in main
    assert "sweep_workloads | default(true)" not in main
    assert "advanced_cleanup | default(true)" not in main
    assert "absent_finalize | default(true)" not in main
    assert "strip_csv_finalizers | default(true)" not in main
    assert "authorize_csv_delete | default(true)" not in main
    assert "default(true)" not in advanced
    assert "ocp_absent_cleanup" not in main.split("include_role")[0] or "include_role" not in main
    assert "include_role" not in main
    assert "advanced_cleanup.yml" in main
    assert "Advanced cleanup of a Terminating namespace before create" not in main
    assert main.count("include_tasks: advanced_cleanup.yml") == 2
    assert "ocp_namespace_advanced_cleanup_requested" in main
    assert "ocp_namespace_advanced_cleanup: false" in defaults
    assert "ocp_namespace_absent_sweep_olm: false" in defaults
    assert "ocp_namespace_absent_sweep_workloads: false" in defaults
    assert "ocp_namespace_absent_finalize: false" in defaults
    assert "ocp_namespace_absent_strip_csv_finalizers: false" in defaults
    assert "default(false)" in advanced
    assert "include_tasks: finalize_namespace.yml" not in main


def test_cleanup_role_requires_authorization_before_csv_deletion():
    defaults = _text("roles/ocp_absent_cleanup/defaults/main.yml")
    cleanup = _text("roles/ocp_absent_cleanup/tasks/cleanup_one_namespace.yml")
    assert "ocp_absent_cleanup_sweep_olm: false" in defaults
    assert "ocp_absent_cleanup_sweep_workloads: false" in defaults
    assert "ocp_absent_cleanup_finalize: false" in defaults
    assert "ocp_absent_cleanup_authorize_csv_delete: false" in defaults
    assert "ocp_absent_cleanup_strip_csv_finalizers: false" in defaults
    assert "ocp_absent_cleanup_delete_copied_csvs: false" in defaults
    assert "ocp_absent_cleanup_select_csvs" in cleanup
    assert "ocp_absent_cleanup_strip_csv_finalizers | default(false)" in cleanup
    delete_csv = cleanup.split("- name: Absent cleanup | Delete authorized CSVs", 1)[1]
    delete_csv = delete_csv.split("- name:", 1)[0]
    assert 'namespace: "{{ ocp_absent_cleanup_ns }}"' in delete_csv
    assert "ocp_absent_cleanup_authorize_csv_delete | default(false)" in delete_csv
    strip = cleanup.split("- name: Absent cleanup | Strip CSV finalizers", 1)[1]
    strip = strip.split("- name:", 1)[0]
    assert "ocp_absent_cleanup_strip_csv_finalizers | default(false)" in strip
    assert "sweep_olm | default(true)" not in cleanup
    assert "sweep_workloads | default(true)" not in cleanup
    assert "finalize | default(true)" not in cleanup
    assert "strip_csv_finalizers | default(true)" not in cleanup


def test_subscription_and_cert_manager_opt_in_explicitly():
    subscription = _text("roles/ocp_operator_subscription/tasks/uninstall_operator.yml")
    cert_manager = _text(
        "roles/bootstrap_generate_playbook_repo/files/playbooks/cert-manager/"
        "uninstall-cert-manager-tasks.yml"
    )
    assert "ocp_absent_cleanup_select_csvs" in subscription
    assert "ocp_absent_cleanup_csv_name_matches" in subscription
    assert "ocp_absent_cleanup_select_installplans" in subscription
    assert "is search(" not in subscription
    assert "ocp_absent_cleanup_authorize_unfiltered_csv_delete: false" in subscription
    assert "ocp_absent_cleanup_delete_copied_csvs: false" in subscription
    assert "ocp_absent_cleanup_finalize: false" in subscription
    assert "ocp_absent_cleanup_csv_name_match: cert-manager-operator" in cert_manager
    assert "ocp_absent_cleanup_delete_copied_csvs: false" in cert_manager
    assert "ocp_absent_cleanup_authorize_unfiltered_csv_delete: false" in cert_manager
    assert "ocp_absent_cleanup_authorize_unfiltered_workloads: false" in cert_manager
    assert "ocp_absent_cleanup_finalize: false" in cert_manager
    assert "cert-manager-operator-controller-manager" in cert_manager
    assert "ocp_operator_subscription_absent_sweep_workloads: false" in cert_manager


if __name__ == "__main__":
    test_platform_namespaces_cannot_be_deleted()
    test_component_namespaces_can_be_deleted()
    test_cleanup_refuses_platform_and_broad_shared_operators()
    test_default_csv_selection_is_empty()
    test_copied_csvs_require_explicit_authorization()
    test_name_match_stays_in_the_operator_namespace()
    test_unfiltered_authorization_does_not_cross_namespaces()
    test_workloads_and_installplans_stay_in_namespace()
    test_namespace_role_does_not_enable_cleanup_by_default()
    test_cleanup_role_requires_authorization_before_csv_deletion()
    test_subscription_and_cert_manager_opt_in_explicitly()
    print("PASS unit ocp_absent_cleanup")
