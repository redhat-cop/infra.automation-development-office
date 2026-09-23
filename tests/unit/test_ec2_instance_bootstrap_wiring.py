"""Sanity checks for AWS GovCloud EC2 instance bootstrap wiring."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected mapping in {path}"
    return data


def test_govcloud_survey_defaults_are_present():
    vars_data = _load_yaml(ROOT / "roles/bootstrap_controller/vars/aws_govcloud.yml")
    instance_types = vars_data["bootstrap_controller_aws_govcloud_instance_type_choices"]
    regions = vars_data["bootstrap_controller_aws_govcloud_region_choices"]
    states = vars_data["bootstrap_controller_ec2_instance_state_choices"]

    assert vars_data["bootstrap_controller_aws_govcloud_default_instance_type"] == "m5.large"
    assert vars_data["bootstrap_controller_aws_govcloud_default_region"] == "us-gov-west-1"
    assert "m5.large" in instance_types
    assert "t3.medium" in instance_types
    assert "g5.xlarge" in instance_types
    assert regions == ["us-gov-west-1", "us-gov-east-1"]
    assert states == ["present", "running", "stopped", "terminated"]
    assert "us-east-1" not in regions


def test_job_template_survey_uses_govcloud_vars():
    jt = _load_yaml(
        ROOT
        / "roles/bootstrap_controller/files/job_templates"
        / "ado-aws-ec2-instance-bootstrap.jt.yml"
    )
    templates = jt["controller_templates"]
    assert templates[0]["playbook"] == "playbooks/aws/ado-manage-ec2-instance-bootstrap.yml"
    spec = templates[0]["survey_spec"]["spec"]
    by_var = {item["variable"]: item for item in spec}
    assert "m5.large" in by_var["ec2_instance_instance_type"]["choices"] or "{{" in str(
        by_var["ec2_instance_instance_type"]["choices"]
    )
    assert by_var["ec2_instance_region"]["type"] == "multiplechoice"
    assert by_var["ec2_instance_instance_type"]["type"] == "multiplechoice"
    assert by_var["ec2_instance_state"]["type"] == "multiplechoice"


def test_seed_playbook_calls_amazon_aws_ec2_instance():
    playbook = (
        ROOT
        / "roles/bootstrap_generate_playbook_repo/files/playbooks/aws"
        / "ado-manage-ec2-instance-bootstrap.yml"
    )
    text = playbook.read_text(encoding="utf-8")
    assert "amazon.aws.ec2_instance:" in text
    assert "vault_aws.yml" in text
    assert "vars_{{ component }}.yml" in text
    assert "infra.ado.ec2_instance" not in text


def test_components_defaults_include_ec2_instance():
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_resolve_component/files/components_defaults.yml"
    )
    ec2 = defaults["components_defaults"]["ec2_instance"]
    assert ec2["ec2_instance_instance_type"] == "m5.large"
    assert ec2["ec2_instance_region"] == "us-gov-west-1"
    assert ec2["ec2_instance_state"] == "present"


def test_component_map_homes_ec2_instance_under_aws_not_provision():
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
    )
    component_map = defaults["bootstrap_generate_playbook_repo_component_map"]
    assert "ec2_instance" in component_map["aws"]
    assert "ec2_ami_copy" in component_map["aws"]
    assert component_map["provision"] == ["openshift_virt"]
    assert "aws_instance" not in component_map["provision"]
    assert "ec2_instance" not in component_map["provision"]
    # Legacy alias remains for old preflight JSON.
    assert component_map["aws_instance"] == ["ec2_instance"]
