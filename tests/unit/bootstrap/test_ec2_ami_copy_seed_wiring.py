"""Unit tests for static EC2 AMI copy bootstrap seed wiring.

These assert seed JT/playbook/defaults without running Molecule generate-and-verify.
Keep ``integration_bootstrap_ec2_ami_copy`` for the full preflight → generated
files path.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected mapping in {path}"
    return data


def test_copy_ami_job_template_points_at_seed_playbook() -> None:
    jt = _load_yaml(
        ROOT
        / "roles/bootstrap_controller/files/job_templates"
        / "ado-copy-ami-bootstrap.jt.yml"
    )
    templates = jt["controller_templates"]
    assert templates[0]["playbook"] == "playbooks/aws/ado-copy-ami-bootstrap.yml"
    assert templates[0]["survey_enabled"] is True

    by_var = {
        item["variable"]: item for item in templates[0]["survey_spec"]["spec"]
    }
    assert by_var["ec2_ami_copy_source_region"]["default"] == "us-east-1"
    assert by_var["ec2_ami_copy_dest_region"]["default"] == "us-west-2"
    assert by_var["ec2_ami_copy_wait"]["type"] == "multiplechoice"
    assert by_var["ec2_ami_copy_wait"]["choices"] == "true\nfalse"
    assert by_var["ec2_ami_copy_wait"]["default"] == "true"


def test_seed_playbook_uses_shared_aws_vault_and_module() -> None:
    playbook = (
        ROOT
        / "roles/bootstrap_generate_playbook_repo/files/playbooks/aws"
        / "ado-copy-ami-bootstrap.yml"
    )
    text = playbook.read_text(encoding="utf-8")
    assert "infra.ado.ec2_ami_copy:" in text
    assert "vault_aws.yml" in text
    assert "vars_{{ component }}.yml" in text
    assert "vault_ec2_ami_copy.yml" not in text


def test_playbook_repo_map_registers_ec2_ami_copy() -> None:
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
    )
    component_map = defaults["bootstrap_generate_playbook_repo_component_map"]
    assert component_map["ec2_ami_copy"] == ["ec2_ami_copy"]
    assert "ec2_ami_copy" in component_map["aws"]

    generated = defaults["bootstrap_generate_playbook_repo_generated_playbooks"]
    ami_entries = [item for item in generated if item.get("app") == "ec2_ami_copy"]
    assert len(ami_entries) == 1
    assert ami_entries[0]["dest"] == "playbooks/aws/ado-copy-ami-bootstrap.yml"


def test_components_defaults_match_survey_region_defaults() -> None:
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_resolve_component/files/components_defaults.yml"
    )
    ec2 = defaults["components_defaults"]["ec2_ami_copy"]
    assert ec2["ec2_ami_copy_source_region"] == "us-east-1"
    assert ec2["ec2_ami_copy_dest_region"] == "us-west-2"
    assert ec2["ec2_ami_copy_wait"] is True
