# SPDX-License-Identifier: GPL-3.0-or-later
"""Dual OpenShift Virt job templates: one playbook, one role, two surveys.

Static checks on the seed files and the policy normalizer. Execution against a real
generated repository is covered in ``test_topology_lifecycle.py``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
JT_DIR = ROOT / "roles" / "bootstrap_controller" / "files" / "job_templates"
ADVANCED = JT_DIR / "ado-provision-openshift-virt-vm-bootstrap.jt.yml"
SELF_SERVICE = JT_DIR / "ado-create-vm-self-service-bootstrap.jt.yml"
PLAYBOOK = (
    ROOT
    / "roles/bootstrap_generate_playbook_repo/files/playbooks/provision"
    / "ado-provision-openshift-virt-vm-bootstrap.yml"
)
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"
GENERATE = ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"

ADVANCED_ONLY = {
    "state",
    "provision_openshift_virt_hostname",
    "provision_openshift_virt_source_namespace",
    "provision_openshift_virt_preference",
    "provision_openshift_virt_instance_type",
    "provision_openshift_virt_cpu_cores",
    "provision_openshift_virt_memory",
    "provision_openshift_virt_root_disk_size",
    "provision_openshift_virt_storage_class",
    "provision_openshift_virt_cloud_user",
    "provision_openshift_virt_cloud_user_password",
    "provision_openshift_virt_root_password",
    "provision_openshift_virt_ssh_public_key",
    "provision_openshift_virt_enable_root_ssh",
    "provision_openshift_virt_network_mode",
    "provision_openshift_virt_multus_nad_name",
    "provision_openshift_virt_static_ip",
    "provision_openshift_virt_gateway",
    "provision_openshift_virt_dns_servers",
}


def _template(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))["controller_templates"][0]


def _survey_variables(template):
    return [question["variable"] for question in template["survey_spec"]["spec"]]


def test_both_templates_run_the_same_playbook_and_credentials():
    advanced, self_service = _template(ADVANCED), _template(SELF_SERVICE)
    assert advanced["playbook"] == self_service["playbook"]
    for key in ("inventory", "project", "execution_environment", "credentials", "organization"):
        assert advanced[key] == self_service[key], key


def test_advanced_template_is_unchanged_in_name_and_still_prompts():
    advanced = _template(ADVANCED)
    assert advanced["name"] == "ADO | Provision OpenShift Virt VM"
    assert "ado_vm_template_mode" not in (advanced.get("extra_vars") or {})
    assert "provision_openshift_virt_instance_type" in _survey_variables(advanced)


def test_self_service_fixes_its_mode_and_turns_launch_variables_off():
    template = _template(SELF_SERVICE)
    assert template["name"] == "ADO | Create VM — Self Service"
    assert template["extra_vars"]["ado_vm_template_mode"] == "self_service"
    assert template["extra_vars"]["state"] == "present"
    assert template["ask_variables_on_launch"] is False


def test_self_service_survey_has_only_the_simple_questions():
    variables = _survey_variables(_template(SELF_SERVICE))
    assert variables == [
        "env",
        "provision_openshift_virt_namespace",
        "provision_openshift_virt_vm_name",
        "provision_openshift_virt_source_name",
        "provision_openshift_virt_size",
        "provision_openshift_virt_start",
    ]
    assert not (set(variables) & ADVANCED_ONLY)


def test_self_service_name_does_not_match_the_preflight_advanced_lookup():
    """Preflight finds the Advanced template by this hint; the new name must not collide."""
    assert "Provision OpenShift Virt VM" not in _template(SELF_SERVICE)["name"]


def test_self_service_choices_are_placeholders_filled_from_the_policy():
    text = SELF_SERVICE.read_text(encoding="utf-8")
    for key in ("namespace_choices", "image_choices", "size_choices"):
        assert f"bootstrap_controller_self_service_{key}" in text
        assert f"bootstrap_controller_self_service_{key}" in GENERATE.read_text()


def test_generator_registers_and_prunes_the_self_service_template():
    text = GENERATE.read_text()
    assert text.count("ado-create-vm-self-service-bootstrap.jt.yml") >= 2
    assert "no enabled openshift_virt self-service policy" in text


def test_the_policy_never_puts_secrets_or_defaults_in_the_survey_facts():
    text = GENERATE.read_text()
    start = text.index("bootstrap_controller_virt_self_service:")
    block = text[start : start + 1200]
    assert "defaults" not in block and "ssh_public_key" not in block


def test_one_playbook_decides_the_mode_and_enforces_the_policy():
    play = yaml.safe_load(PLAYBOOK.read_text())[0]
    assert "ado_vm_self_service" in play["vars"]
    assert play["vars"]["ado_vm_policy"] == "{{ openshift_virt_self_service_policy | default({}) }}"
    names = [task["name"] for task in play["pre_tasks"]]
    assert any(name.startswith("Self Service | Refuse any value outside") for name in names)
    guard = next(task for task in play["pre_tasks"] if task["name"].startswith("Self Service | Refuse any value"))
    assert guard["when"] == "ado_vm_self_service | bool"
    joined = " ".join(guard["ansible.builtin.assert"]["that"])
    assert "ocp_virt_self_service_violations" in joined
    assert "cloud_init_user_data == ado_cloud_init_user_data_expected" in joined
    assert "cloud_init_network_data == ado_cloud_init_network_data_expected" in joined


def test_guard_runs_before_any_role_creates_anything():
    play = yaml.safe_load(PLAYBOOK.read_text())[0]
    assert "pre_tasks" in play and play["roles"]
    # roles run after pre_tasks in Ansible; the guard is a pre_task, so nothing is created first.
    assert [role["role"] for role in play["roles"]] == [
        "infra.automation_development_office.ocp_namespace",
        "infra.automation_development_office.ocp_virtualization",
    ]


def test_quota_check_is_read_only():
    play = yaml.safe_load(PLAYBOOK.read_text())[0]
    for task in play["pre_tasks"]:
        if "Read the" in task["name"] and task["name"].startswith("Self Service"):
            module = next(key for key in task if key.startswith("kubernetes.core."))
            assert module == "kubernetes.core.k8s_info"
            assert task["failed_when"] is False
            assert task["when"] == "ado_vm_self_service | bool"


def test_self_service_values_are_taken_from_the_policy_not_the_survey():
    play = yaml.safe_load(PLAYBOOK.read_text())[0]["vars"]
    for variable in ("instance_type", "preference", "storage_class", "root_disk_size", "network_mode", "multus_network_name"):
        value = play[variable]
        assert "ado_vm_self_service | bool" in value, variable
    assert "'' if (ado_vm_self_service | bool)" in play["cloud_user_password"]
    assert "false if (ado_vm_self_service | bool)" in play["enable_root_ssh"]


def test_no_existing_vm_is_replaced_by_the_role():
    """Both templates share the role; it looks the VM up and creates only when missing."""
    create = (ROOT / "roles/ocp_virtualization/tasks/create_vm.yml").read_text()
    assert "name: Check whether VirtualMachine already exists" in create
    assert "when: (ocp_virtualization_existing_vm.resources | default([]) | length) == 0" in create


def _normalizer():
    tree = ast.parse(OVERLAY.read_text())
    wanted = {"as_bool", "normalize_virt_self_service"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in functions} == wanted
    namespace = {"re": re}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(OVERLAY), "exec"), namespace)
    return namespace["normalize_virt_self_service"]


def test_normalizer_keeps_approved_names_and_defaults():
    policy = _normalizer()(
        {
            "enabled": True,
            "images": [{"id": "rhel9", "label": "RHEL 9"}, "rhel10", {"id": "rhel9"}, {"id": ""}, {"id": "centos"}],
            "sizes": [
                {"label": "Small", "instance_type": "u1.medium"},
                {"label": "Bad", "instance_type": "custom"},
                {"label": "", "instance_type": "u1.large"},
                {"label": "Small", "instance_type": "u1.xlarge"},
            ],
            "namespaces": ["team-a", "", "team-a", "team-b"],
            "defaults": {"storage_class": " fast ", "ssh_public_key": "ssh-ed25519 AAAA"},
        }
    )
    assert policy["enabled"] is True
    assert [item["id"] for item in policy["images"]] == ["rhel9", "rhel10"]
    assert policy["images"][1]["preference"] == "rhel.10"
    assert policy["sizes"] == [{"label": "Small", "instance_type": "u1.medium"}]
    assert policy["namespaces"] == ["team-a", "team-b"]
    assert policy["defaults"]["storage_class"] == "fast"
    assert policy["defaults"]["network_mode"] == "masquerade"
    assert policy["defaults"]["cloud_user"] == "cloud-user"
    assert policy["defaults"]["source_namespace"] == "openshift-virtualization-os-images"


def test_normalizer_disables_an_incomplete_policy():
    normalize = _normalizer()
    complete = {
        "images": [{"id": "rhel9"}],
        "sizes": [{"label": "S", "instance_type": "u1.medium"}],
        "namespaces": ["team-a"],
    }
    assert normalize({**complete, "enabled": True})["enabled"] is True
    assert normalize({**complete, "enabled": False})["enabled"] is False
    assert normalize(complete)["enabled"] is False
    for missing in ("images", "sizes", "namespaces"):
        assert normalize({**complete, "enabled": True, missing: []})["enabled"] is False
    assert normalize(None)["enabled"] is False


def test_overlay_writes_the_policy_only_when_preflight_supplies_it():
    text = OVERLAY.read_text()
    assert 'if "self_service" in public_values:' in text
    assert "openshift_virt_self_service_policy" in text
