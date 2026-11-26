# SPDX-License-Identifier: GPL-3.0-or-later
"""Self Service guard for OpenShift Virt VM launches (filter plugin)."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest
import yaml

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
    assert set(F.FilterModule().filters()) == {
        "ocp_virt_self_service_violations",
        "ocp_virt_self_service_guard",
        "ocp_virt_quota_shortfalls",
    }


# ---- trusted policy, cloud-init and project checks ----

USER_DATA = (
    "#cloud-config\n"
    "hostname: web-01\n"
    "ssh_pwauth: false\n"
    "disable_root: true\n"
    "users:\n"
    "  - default\n"
    "  - name: cloud-user\n"
    "    sudo: ALL=(ALL) NOPASSWD:ALL\n"
    "    shell: /bin/bash\n"
    "    lock_passwd: true\n"
    "    ssh_authorized_keys:\n"
    "      - ssh-ed25519 AAAA-example approved@lab\n"
)


def _project(tmp_path, policy=POLICY, env="lab", raw=None):
    """A project tree: <root>/playbooks/provision and <root>/group_vars/all/<env>/vars_openshift_virt.yml."""
    playbooks = tmp_path / "playbooks" / "provision"
    playbooks.mkdir(parents=True)
    env_dir = tmp_path / "group_vars" / "all" / env
    env_dir.mkdir(parents=True)
    text = raw if raw is not None else yaml.safe_dump({"openshift_virt_other": "kept", F.POLICY_KEY: policy})
    (env_dir / F.POLICY_FILE).write_text(text)
    return str(playbooks)


def _guard(playbook_dir, user_data=USER_DATA, network_data="", env="lab", **changes):
    return F.self_service_guard(playbook_dir, env, _effective(**changes), user_data, network_data)


def test_guard_allows_the_approved_launch(tmp_path):
    assert _guard(_project(tmp_path)) == []


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda t: t + "runcmd:\n  - id\n", id="runcmd added"),
        pytest.param(lambda t: t + "write_files:\n  - path: /etc/x\n    content: y\n", id="write_files added"),
        pytest.param(lambda t: t + "chpasswd:\n  list: root:x\n", id="chpasswd added"),
        pytest.param(lambda t: t + "bootcmd:\n  - id\n", id="bootcmd added"),
        pytest.param(lambda t: t.replace("ssh_pwauth: false", "ssh_pwauth: true"), id="password login on"),
        pytest.param(lambda t: t.replace("disable_root: true", "disable_root: false"), id="root login on"),
        pytest.param(lambda t: t.replace("hostname: web-01", "hostname: other"), id="hostname changed"),
        pytest.param(lambda t: t.replace("approved@lab", "attacker@evil"), id="other ssh key"),
        pytest.param(lambda t: t.replace("NOPASSWD:ALL", "NOPASSWD:ALL, !requiretty"), id="sudo changed"),
        pytest.param(lambda t: t + "  - name: root\n    lock_passwd: false\n", id="extra user (indent trick)"),
        pytest.param(lambda t: t + "hostname: other\n", id="duplicate key hides a value"),
        pytest.param(lambda t: t + "---\nruncmd: [id]\n", id="second YAML document"),
        pytest.param(lambda t: t.replace("#cloud-config\n", ""), id="no cloud-config header"),
        pytest.param(lambda t: t.replace("ssh_pwauth: false", "ssh_pwauth: &a false\nx: *a"), id="alias"),
        pytest.param(lambda t: "#cloud-config\nruncmd: [id]\n", id="entirely different"),
        pytest.param(lambda t: "", id="empty"),
        pytest.param(lambda t: "#cloud-config\n: : :\n  [", id="not YAML"),
    ],
)
def test_cloud_init_that_differs_from_the_approved_structure_is_refused(tmp_path, mutate):
    problems = _guard(_project(tmp_path), user_data=mutate(USER_DATA))
    assert any("Cloud-init user data" in item for item in problems), problems


def test_cloud_init_network_data_must_be_empty(tmp_path):
    playbook_dir = _project(tmp_path)
    assert _guard(playbook_dir, network_data="") == []
    assert _guard(playbook_dir, network_data="  \n") == []  # whitespace only is the same as none
    problems = _guard(playbook_dir, network_data="version: 2\nethernets: {}\n")
    assert any("network data" in item for item in problems)


def test_the_policy_is_read_from_the_project_file_not_from_the_caller(tmp_path):
    """There is no argument through which a caller's policy can reach the check."""
    assert list(inspect.signature(F.self_service_guard).parameters) == [
        "playbook_dir", "env", "effective", "cloud_init_user_data", "cloud_init_network_data",
    ]
    permissive = {**POLICY, "sizes": [{"label": "Huge", "instance_type": "u1.8xlarge"}]}
    playbook_dir = _project(tmp_path, policy=POLICY)
    problems = _guard(playbook_dir, size="Huge", instance_type="u1.8xlarge")
    assert any("Size 'Huge' is not approved" in item for item in problems)
    assert permissive != POLICY  # the permissive policy never had a way in


@pytest.mark.parametrize("env", ["", ".", "..", "../lab", "lab/../lab", "a/b", "lab ", "-x", "l\nab", "/etc"])
def test_an_environment_name_cannot_point_outside_group_vars(tmp_path, env):
    playbook_dir = _project(tmp_path)
    policy, problem = F.load_policy_file(playbook_dir, env)
    assert policy == {} and problem
    assert _guard(playbook_dir, env=env)


def test_a_missing_or_empty_policy_file_is_refused_as_not_configured(tmp_path):
    for raw in (None, "", "{}\n", "openshift_virt_other: 1\n", f"{F.POLICY_KEY}: {{}}\n", "[1, 2]\n", "a: [\n"):
        sub = tmp_path / str(abs(hash(raw)))
        sub.mkdir()
        playbook_dir = _project(sub, raw=raw if raw is not None else "x: 1\n")
        problems = _guard(playbook_dir)
        assert problems and "not configured" in problems[0], (raw, problems)
    assert "not configured" in _guard(str(tmp_path / "nowhere" / "a" / "b"))[0]


def test_a_disabled_policy_is_refused(tmp_path):
    problems = _guard(_project(tmp_path, policy={**POLICY, "enabled": False}))
    assert "not configured" in problems[0]


def test_a_policy_with_template_expressions_is_refused(tmp_path):
    templated = {**POLICY, "defaults": {**POLICY["defaults"], "storage_class": "{{ vault_storage }}"}}
    problems = _guard(_project(tmp_path, policy=templated))
    assert problems and "template expressions" in problems[0]


def test_vault_tags_elsewhere_in_the_vars_file_do_not_break_the_policy_read(tmp_path):
    raw = "secret: !vault |\n  $ANSIBLE_VAULT;1.1;AES256\n  6162\n" + yaml.safe_dump({F.POLICY_KEY: POLICY})
    assert _guard(_project(tmp_path, raw=raw)) == []


def test_removal_through_the_state_the_namespace_role_reads_is_refused(tmp_path):
    playbook_dir = _project(tmp_path)
    # vm_state says present (the play's copy), but the namespace role reads ``state`` itself.
    problems = _guard(playbook_dir, vm_state="present", role_state="absent")
    assert any("Removal" in item for item in problems)
    assert any("Removal" in item for item in _guard(playbook_dir, vm_state="absent", role_state="present"))
    assert _guard(playbook_dir, vm_state="present", role_state="present") == []


def test_the_namespace_role_cannot_create_a_different_project(tmp_path):
    playbook_dir = _project(tmp_path)
    problems = _guard(playbook_dir, namespace_effective="kube-system")
    assert any("project to create" in item for item in problems)
    assert _guard(playbook_dir, namespace_effective="team-a") == []
    assert _guard(playbook_dir, namespace_effective="") != []


def test_expected_user_data_matches_the_playbook_rendering():
    """The expected structure is the one the generated playbook builds for Self Service."""
    expected = F.expected_user_data("web-01", POLICY)
    assert yaml.safe_load(USER_DATA) == expected
    without_key = F.expected_user_data("web-01", {**POLICY, "defaults": {**POLICY["defaults"], "ssh_public_key": ""}})
    assert "ssh_authorized_keys" not in without_key["users"][1]
    assert json.dumps(expected, sort_keys=True)


def test_a_password_is_refused_when_only_the_fact_that_one_is_set_reaches_the_guard():
    """The generated playbook passes ``*_password_set`` so no password value enters the filter."""
    assert any("Passwords" in item for item in _check(cloud_user_password_set=True))
    assert any("Passwords" in item for item in _check(root_password_set="true"))
    assert _check(cloud_user_password_set=False, root_password_set="false") == []
