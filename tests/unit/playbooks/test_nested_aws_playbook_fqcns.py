"""Nested AWS collection playbook FQCN path mapping (fast unit checks).

Automation Hub 2.1.4 import reported ``Failed to find`` for nested AWS FQCNs.
ansible-core resolves ``playbooks/<platform>/<service>/<name>.yml`` as
``namespace.collection.<platform>.<service>.<name>``.

Built-artifact syntax-check of the real playbooks and Contoller seed wrappers
lives in ``scripts/check_nested_aws_playbook_fqcns.py`` (CI job). That covers
production content; these unit tests only assert on-disk FQCN ↔ path mapping.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

# README Content index / Collection playbooks table — the seven Hub entry points.
NESTED_AWS_PLAYBOOKS = (
    (
        "infra.automation_development_office.aws.ec2.ado_ec2_instance_create",
        "playbooks/aws/ec2/ado_ec2_instance_create.yml",
    ),
    (
        "infra.automation_development_office.aws.ec2.ado_ec2_instance_delete",
        "playbooks/aws/ec2/ado_ec2_instance_delete.yml",
    ),
    (
        "infra.automation_development_office.aws.ec2.ado_ec2_instance_info",
        "playbooks/aws/ec2/ado_ec2_instance_info.yml",
    ),
    (
        "infra.automation_development_office.aws.ec2.ado_ec2_instance_modify",
        "playbooks/aws/ec2/ado_ec2_instance_modify.yml",
    ),
    (
        "infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set",
        "playbooks/aws/s3/ado_s3_bucket_policy_set.yml",
    ),
    (
        "infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set_from_file",
        "playbooks/aws/s3/ado_s3_bucket_policy_set_from_file.yml",
    ),
    (
        "infra.automation_development_office.aws.s3.ado_s3_bucket_policy_info",
        "playbooks/aws/s3/ado_s3_bucket_policy_info.yml",
    ),
)


@pytest.mark.parametrize("fqcn,rel", NESTED_AWS_PLAYBOOKS)
def test_nested_aws_playbook_file_and_fqcn_comment(fqcn: str, rel: str) -> None:
    path = ROOT / rel
    assert path.is_file(), rel
    text = path.read_text(encoding="utf-8")
    assert f"# FQCN: {fqcn}" in text


@pytest.mark.parametrize("fqcn,rel", NESTED_AWS_PLAYBOOKS)
def test_nested_aws_playbook_fqcn_maps_to_nested_path(fqcn: str, rel: str) -> None:
    """Dotted segments after ns.collection are the path under playbooks/."""
    parts = fqcn.split(".")
    assert parts[:2] == ["infra", "automation_development_office"]
    assert rel == "playbooks/" + "/".join(parts[2:]) + ".yml"
