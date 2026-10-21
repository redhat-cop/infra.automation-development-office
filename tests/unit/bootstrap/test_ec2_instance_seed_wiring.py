"""Unit tests for static EC2 instance bootstrap seed wiring.

These assert seed JT/playbook/defaults without running Molecule generate-and-verify.
Keep ``integration_bootstrap_ec2_instance`` for the full preflight → generated
files path.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
JT_DIR = ROOT / "roles/bootstrap_controller/files/job_templates"
SEED_DIR = (
    ROOT / "roles/bootstrap_generate_playbook_repo/files/playbooks/aws/ec2"
)

# amazon.aws.ec2_instance state choices used by the modify survey (minus terminate).
EC2_INSTANCE_STATES = {
    "present",
    "running",
    "started",
    "stopped",
    "restarted",
    "rebooted",
}

CREATE_TYPE_CHOICES = [
    "t3.micro",
    "t3.small",
    "t3.medium",
    "t3.large",
    "t3.xlarge",
    "t3a.micro",
    "t3a.small",
    "t3a.medium",
    "t3a.large",
    "t2.micro",
    "t2.small",
    "t2.medium",
    "t2.large",
    "m5.large",
    "m5.xlarge",
    "m6i.large",
    "m6i.xlarge",
    "c5.large",
    "c5.xlarge",
    "c6i.large",
    "r5.large",
    "r6i.large",
]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected mapping in {path}"
    return data


def _survey_by_var(jt_path: Path) -> dict:
    jt = _load_yaml(jt_path)
    templates = jt["controller_templates"]
    return {item["variable"]: item for item in templates[0]["survey_spec"]["spec"]}


def test_create_job_template_instance_type_is_multiplechoice() -> None:
    jt_path = JT_DIR / "ado-ec2-instance-create-bootstrap.jt.yml"
    jt = _load_yaml(jt_path)
    templates = jt["controller_templates"]
    assert (
        templates[0]["playbook"]
        == "playbooks/aws/ec2/ado-ec2-instance-create-bootstrap.yml"
    )
    assert templates[0]["survey_enabled"] is True

    by_var = _survey_by_var(jt_path)
    type_q = by_var["ec2_instance_type"]
    assert type_q["type"] == "multiplechoice"
    assert type_q["default"] == "t3.small"
    assert type_q["choices"] == CREATE_TYPE_CHOICES
    assert "t3.small" in type_q["choices"]
    assert "c5.large" in type_q["choices"]

    assert by_var["ec2_instance_assign_public_ip"]["type"] == "multiplechoice"
    assert by_var["ec2_instance_assign_public_ip"]["choices"] == ["true", "false"]
    assert by_var["ec2_instance_wait"]["type"] == "multiplechoice"
    assert by_var["ec2_instance_wait"]["choices"] == ["true", "false"]


def test_modify_job_template_state_matches_amazon_aws_choices() -> None:
    jt_path = JT_DIR / "ado-ec2-instance-modify-bootstrap.jt.yml"
    jt = _load_yaml(jt_path)
    templates = jt["controller_templates"]
    assert (
        templates[0]["playbook"]
        == "playbooks/aws/ec2/ado-ec2-instance-modify-bootstrap.yml"
    )

    by_var = _survey_by_var(jt_path)
    state_q = by_var["ec2_instance_state"]
    assert state_q["type"] == "multiplechoice"
    assert state_q["default"] == "(no change)"
    assert state_q["choices"][0] == "(no change)"
    assert set(state_q["choices"][1:]) == EC2_INSTANCE_STATES
    assert "terminated" not in state_q["choices"]
    assert "absent" not in state_q["choices"]

    type_q = by_var["ec2_instance_type"]
    assert type_q["type"] == "multiplechoice"
    assert type_q["default"] == "(no change)"
    assert type_q["choices"][0] == "(no change)"
    assert type_q["choices"][1:] == CREATE_TYPE_CHOICES


def test_delete_and_info_job_templates_point_at_seed_playbooks() -> None:
    delete_jt = _load_yaml(JT_DIR / "ado-ec2-instance-delete-bootstrap.jt.yml")
    info_jt = _load_yaml(JT_DIR / "ado-ec2-instance-info-bootstrap.jt.yml")
    assert (
        delete_jt["controller_templates"][0]["playbook"]
        == "playbooks/aws/ec2/ado-ec2-instance-delete-bootstrap.yml"
    )
    assert (
        info_jt["controller_templates"][0]["playbook"]
        == "playbooks/aws/ec2/ado-ec2-instance-info-bootstrap.yml"
    )
    delete_by_var = _survey_by_var(
        JT_DIR / "ado-ec2-instance-delete-bootstrap.jt.yml"
    )
    assert delete_by_var["ec2_instance_wait"]["type"] == "multiplechoice"
    assert delete_by_var["ec2_instance_wait"]["choices"] == ["true", "false"]


def test_seed_playbooks_import_collection_fqcns_and_shared_aws_vault() -> None:
    expected = {
        "ado-ec2-instance-create-bootstrap.yml": (
            "infra.automation_development_office.aws.ec2.ado_ec2_instance_create"
        ),
        "ado-ec2-instance-delete-bootstrap.yml": (
            "infra.automation_development_office.aws.ec2.ado_ec2_instance_delete"
        ),
        "ado-ec2-instance-modify-bootstrap.yml": (
            "infra.automation_development_office.aws.ec2.ado_ec2_instance_modify"
        ),
        "ado-ec2-instance-info-bootstrap.yml": (
            "infra.automation_development_office.aws.ec2.ado_ec2_instance_info"
        ),
    }
    for filename, fqcn in expected.items():
        text = (SEED_DIR / filename).read_text(encoding="utf-8")
        assert f"ansible.builtin.import_playbook: {fqcn}" in text
        assert "vault_aws.yml" in text
        assert "vars_{{ component }}.yml" in text
        assert "vault_ec2_instance.yml" not in text
        assert "component: ec2_instance" in text


def test_playbook_repo_map_registers_ec2_instance_under_aws() -> None:
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
    )
    component_map = defaults["bootstrap_generate_playbook_repo_component_map"]
    assert component_map["ec2_instance"] == ["ec2_instance"]
    assert "ec2_instance" in component_map["aws"]
    assert "ec2_ami_copy" in component_map["aws"]

    generated = defaults["bootstrap_generate_playbook_repo_generated_playbooks"]
    dests = {
        item["dest"]
        for item in generated
        if item.get("app") == "ec2_instance"
    }
    assert "playbooks/aws/ec2/ado-ec2-instance-create-bootstrap.yml" in dests
    assert "playbooks/aws/ec2/ado-ec2-instance-delete-bootstrap.yml" in dests
    assert "playbooks/aws/ec2/ado-ec2-instance-modify-bootstrap.yml" in dests
    assert "playbooks/aws/ec2/ado-ec2-instance-info-bootstrap.yml" in dests
    assert "playbooks/aws/ec2/tasks/promote-ec2-instance-facts.yml" in dests


def test_components_defaults_include_ec2_instance() -> None:
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_resolve_component/files/components_defaults.yml"
    )
    ec2 = defaults["components_defaults"]["ec2_instance"]
    assert ec2["component"] == "ec2_instance"
    assert ec2["ec2_instance_type"] == "t3.small"
    assert ec2["ec2_instance_wait"] is True
