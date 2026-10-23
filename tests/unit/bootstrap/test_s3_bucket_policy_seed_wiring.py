"""Unit tests for static S3 bucket policy bootstrap seed wiring.

These assert seed JT/playbook/defaults without running Molecule generate-and-verify.
Keep ``integration_bootstrap_s3_bucket_policy`` for the full preflight → generated
files path.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
JT_DIR = ROOT / "roles/bootstrap_controller/files/job_templates"
SEED_DIR = (
    ROOT / "roles/bootstrap_generate_playbook_repo/files/playbooks/aws/s3"
)
COLLECTION_PLAYBOOK_DIR = ROOT / "playbooks/aws/s3"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected mapping in {path}"
    return data


def _survey_by_var(jt_path: Path) -> dict:
    jt = _load_yaml(jt_path)
    templates = jt["controller_templates"]
    return {item["variable"]: item for item in templates[0]["survey_spec"]["spec"]}


def test_set_job_template_points_at_seed_playbook() -> None:
    jt_path = JT_DIR / "ado-s3-bucket-policy-set-bootstrap.jt.yml"
    jt = _load_yaml(jt_path)
    templates = jt["controller_templates"]
    assert (
        templates[0]["playbook"]
        == "playbooks/aws/s3/ado-s3-bucket-policy-set-bootstrap.yml"
    )
    assert templates[0]["survey_enabled"] is True

    by_var = _survey_by_var(jt_path)
    assert by_var["s3_bucket_name"]["required"] is True
    assert by_var["s3_bucket_aws_account_id"]["default"] == "123456789012"
    assert by_var["s3_bucket_reader_role_name"]["default"] == "AppReader"


def test_set_from_file_and_info_job_templates() -> None:
    from_file = _load_yaml(
        JT_DIR / "ado-s3-bucket-policy-set-from-file-bootstrap.jt.yml"
    )
    info = _load_yaml(JT_DIR / "ado-s3-bucket-policy-info-bootstrap.jt.yml")
    assert (
        from_file["controller_templates"][0]["playbook"]
        == "playbooks/aws/s3/ado-s3-bucket-policy-set-from-file-bootstrap.yml"
    )
    assert (
        info["controller_templates"][0]["playbook"]
        == "playbooks/aws/s3/ado-s3-bucket-policy-info-bootstrap.yml"
    )
    from_file_by_var = _survey_by_var(
        JT_DIR / "ado-s3-bucket-policy-set-from-file-bootstrap.jt.yml"
    )
    assert "s3_bucket_policy_file" in from_file_by_var
    assert from_file_by_var["s3_bucket_policy_file"]["required"] is False


def test_seed_playbooks_import_collection_fqcns_and_shared_aws_vault() -> None:
    expected = {
        "ado-s3-bucket-policy-set-bootstrap.yml": (
            "infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set"
        ),
        "ado-s3-bucket-policy-set-from-file-bootstrap.yml": (
            "infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set_from_file"
        ),
        "ado-s3-bucket-policy-info-bootstrap.yml": (
            "infra.automation_development_office.aws.s3.ado_s3_bucket_policy_info"
        ),
    }
    for filename, fqcn in expected.items():
        text = (SEED_DIR / filename).read_text(encoding="utf-8")
        assert f"ansible.builtin.import_playbook: {fqcn}" in text
        assert "vault_aws.yml" in text
        assert "vars_{{ component }}.yml" in text
        assert "vault_s3_bucket_policy.yml" not in text
        assert "component: s3_bucket_policy" in text


def test_sample_policy_file_is_jinja_templated() -> None:
    collection_policy = (
        COLLECTION_PLAYBOOK_DIR / "policies/allow_list_and_read.json"
    ).read_text(encoding="utf-8")
    seed_policy = (
        SEED_DIR / "policies/allow_list_and_read.json"
    ).read_text(encoding="utf-8")
    for text in (collection_policy, seed_policy):
        assert "{{ s3_bucket_name }}" in text
        assert "{{ s3_bucket_aws_account_id }}" in text
        assert "{{ s3_bucket_reader_role_name }}" in text
        assert "AllowRoleList" in text
        assert "DenyInsecureTransport" in text


def test_playbook_repo_map_registers_s3_bucket_policy_under_aws() -> None:
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
    )
    component_map = defaults["bootstrap_generate_playbook_repo_component_map"]
    assert component_map["s3_bucket_policy"] == ["s3_bucket_policy"]
    assert "s3_bucket_policy" in component_map["aws"]

    generated = defaults["bootstrap_generate_playbook_repo_generated_playbooks"]
    dests = {
        item["dest"]
        for item in generated
        if item.get("app") == "s3_bucket_policy"
    }
    assert "playbooks/aws/s3/ado-s3-bucket-policy-set-bootstrap.yml" in dests
    assert (
        "playbooks/aws/s3/ado-s3-bucket-policy-set-from-file-bootstrap.yml"
        in dests
    )
    assert "playbooks/aws/s3/ado-s3-bucket-policy-info-bootstrap.yml" in dests
    assert "playbooks/aws/s3/tasks/promote-s3-bucket-policy-facts.yml" in dests
    assert "playbooks/aws/s3/policies/allow_list_and_read.json" in dests


def test_components_defaults_include_s3_bucket_policy() -> None:
    defaults = _load_yaml(
        ROOT / "roles/bootstrap_resolve_component/files/components_defaults.yml"
    )
    s3 = defaults["components_defaults"]["s3_bucket_policy"]
    assert s3["component"] == "s3_bucket_policy"
    assert s3["s3_bucket_aws_account_id"] == "123456789012"
    assert s3["s3_bucket_reader_role_name"] == "AppReader"


def test_controller_component_map_includes_s3_jts() -> None:
    text = (
        ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"
    ).read_text(encoding="utf-8")
    assert "s3_bucket_policy:" in text
    assert "ado-s3-bucket-policy-set-bootstrap.jt.yml" in text
    assert "ado-s3-bucket-policy-set-from-file-bootstrap.jt.yml" in text
    assert "ado-s3-bucket-policy-info-bootstrap.jt.yml" in text
