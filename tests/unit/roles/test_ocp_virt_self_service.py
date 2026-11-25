# SPDX-License-Identifier: GPL-3.0-or-later
"""Self Service guard for OpenShift Virt VM launches (filter plugin)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load():
    path = ROOT / "plugins" / "filter" / "ocp_virt_self_service.py"
    spec = importlib.util.spec_from_file_location("ocp_virt_self_service_filter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = _load()

POLICY = {
    "enabled": True,
    "images": [
        {"id": "rhel9", "label": "RHEL 9", "preference": "rhel.9"},
        {"id": "rhel10", "label": "RHEL 10", "preference": "rhel.10"},
    ],
    "sizes": [
        {"label": "Small", "instance_type": "u1.medium"},
        {"label": "Medium", "instance_type": "u1.large"},
        {"label": "Large", "instance_type": "u1.xlarge"},
    ],
    "namespaces": ["team-a", "team-b"],
    "defaults": {
        "storage_class": "ocs-storagecluster-ceph-rbd",
        "network_mode": "masquerade",
        "multus_network_name": "",
        "root_disk_size": "30Gi",
        "source_namespace": "openshift-virtualization-os-images",
        "cloud_user": "cloud-user",
        "ssh_public_key": "ssh-ed25519 AAAA-example approved@lab",
    },
}


def _effective(**changes):
    value = {
        "vm_name": "web-01",
        "vm_namespace": "team-a",
        "source_kind": "DataSource",
        "source_name": "rhel9",
        "source_namespace": "openshift-virtualization-os-images",
        "preference": "rhel.9",
        "instance_type": "u1.large",
        "size": "Medium",
        "storage_class": "ocs-storagecluster-ceph-rbd",
        "network_mode": "masquerade",
        "multus_network_name": "",
        "root_disk_size": "30Gi",
        "vm_state": "present",
        "cloud_user": "cloud-user",
        "ssh_public_key": "ssh-ed25519 AAAA-example approved@lab",
        "cloud_user_password": "",
        "root_password": "",
        "enable_root_ssh": False,
        "hostname": "web-01",
    }
    value.update(changes)
    return value


def _check(**changes):
    return F.self_service_violations(_effective(**changes), POLICY)


def test_an_approved_launch_has_no_violations():
    assert _check() == []


def test_name_must_be_a_dns_label():
    for bad in ("", "Web_01", "-web", "web-", "a" * 64, "has space"):
        assert _check(vm_name=bad, hostname=bad), bad
    assert _check(vm_name="a" * 63, hostname="a" * 63) == []


def test_project_must_be_approved():
    assert any("kube-system" in item for item in _check(vm_namespace="kube-system"))
    assert any("not approved" in item for item in _check(vm_namespace=""))


def test_image_and_preference_must_match_the_approved_pair():
    assert any("not approved" in item for item in _check(source_name="custom-win"))
    assert any("Preference" in item for item in _check(preference="rhel.10"))


def test_only_a_datasource_in_the_approved_namespace_is_allowed():
    assert any("DataSource" in item for item in _check(source_kind="PVC"))
    assert any("namespace" in item for item in _check(source_namespace="default"))


def test_size_maps_to_an_instance_type_and_custom_is_refused():
    assert any("Size 'Huge'" in item for item in _check(size="Huge"))
    assert any("Instance type" in item for item in _check(instance_type="u1.2xlarge"))
    custom = _check(instance_type="custom")
    assert any("Advanced template" in item for item in custom)


def test_storage_and_network_must_equal_the_approved_defaults():
    assert any("Storage class" in item for item in _check(storage_class="fast"))
    assert any("Network mode" in item for item in _check(network_mode="bridge"))
    assert any("Network attachment" in item for item in _check(multus_network_name="ns/other"))
    assert any("Root disk" in item for item in _check(root_disk_size="500Gi"))


def test_login_is_the_approved_user_and_key_with_no_passwords_or_root_ssh():
    assert any("Login user" in item for item in _check(cloud_user="root"))
    assert any("SSH public key" in item for item in _check(ssh_public_key="ssh-rsa AAAA-other"))
    assert any("Passwords" in item for item in _check(cloud_user_password="x"))
    assert any("Passwords" in item for item in _check(root_password="x"))
    for enabled in (True, "true", "yes"):
        assert any("Root SSH" in item for item in _check(enable_root_ssh=enabled)), enabled
    assert any("hostname" in item for item in _check(hostname="other"))


def test_removal_is_not_available():
    assert any("only create" in item for item in _check(vm_state="absent"))


def test_missing_or_disabled_policy_refuses_everything():
    for policy in ({}, {"enabled": False}, {**POLICY, "enabled": False}, {**POLICY, "images": []},
                   {**POLICY, "sizes": []}, {**POLICY, "namespaces": []}, None):
        problems = F.self_service_violations(_effective(), policy)
        assert len(problems) == 1 and "not configured" in problems[0]


def test_every_problem_is_reported_not_only_the_first():
    problems = _check(vm_namespace="kube-system", source_name="x", storage_class="fast")
    assert len(problems) >= 3


def test_quantity_parsing():
    assert F.quantity_bytes("1Gi") == 1024**3
    assert F.quantity_bytes("512Mi") == 512 * 1024**2
    assert F.quantity_bytes("2G") == 2 * 10**9
    assert F.quantity_bytes("1500m") == 1.5
    assert F.quantity_bytes("") is None
    assert F.quantity_bytes("lots") is None


def _quota(hard, used=None, name="compute"):
    return {"metadata": {"name": name}, "status": {"hard": hard, "used": used or {}}}


def test_quota_with_room_has_no_shortfall():
    quotas = [_quota({"requests.memory": "64Gi", "requests.storage": "500Gi"}, {"requests.memory": "8Gi"})]
    assert F.quota_shortfalls(quotas, "8Gi", "30Gi") == []


def test_quota_memory_shortfall_names_the_quota():
    quotas = [_quota({"requests.memory": "10Gi"}, {"requests.memory": "6Gi"})]
    problems = F.quota_shortfalls(quotas, "8Gi", "30Gi")
    assert len(problems) == 1 and "compute" in problems[0] and "requests.memory" in problems[0]


def test_quota_storage_pvc_and_vm_count_shortfalls():
    quotas = [_quota({"requests.storage": "20Gi", "persistentvolumeclaims": "3",
                      "count/virtualmachines.kubevirt.io": "2"},
                     {"persistentvolumeclaims": "3", "count/virtualmachines.kubevirt.io": "2"})]
    problems = F.quota_shortfalls(quotas, "2Gi", "30Gi")
    assert len(problems) == 3


def test_cpu_quota_is_deliberately_not_checked():
    quotas = [_quota({"requests.cpu": "1", "limits.cpu": "1"}, {"requests.cpu": "1"})]
    assert F.quota_shortfalls(quotas, "2Gi", "30Gi") == []


def test_unknown_or_empty_quota_data_never_blocks():
    assert F.quota_shortfalls([], "8Gi", "30Gi") == []
    assert F.quota_shortfalls(None, "8Gi", "30Gi") == []
    assert F.quota_shortfalls([{"status": {}}], "8Gi", "30Gi") == []
    assert F.quota_shortfalls([_quota({"requests.memory": "1Gi"})], "", "") == []


def test_spec_hard_is_used_when_status_is_missing():
    quota = {"metadata": {"name": "q"}, "spec": {"hard": {"requests.memory": "1Gi"}}}
    assert F.quota_shortfalls([quota], "8Gi", "10Gi")


def test_filters_are_registered():
    assert set(F.FilterModule().filters()) == {"ocp_virt_self_service_violations", "ocp_virt_quota_shortfalls"}
