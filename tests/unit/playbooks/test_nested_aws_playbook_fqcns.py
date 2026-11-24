"""Nested AWS collection playbook FQCNs resolve on ansible-core >= 2.17.

Automation Hub 2.1.4 import reported ``Failed to find`` for these FQCNs.
ansible-core resolves ``playbooks/<platform>/<service>/<name>.yml`` as
``namespace.collection.<platform>.<service>.<name>``. Keep the nested layout;
do not flatten for Hub. Seed Contoller playbooks that ``import_playbook`` these
FQCNs stay under ``roles/bootstrap_generate_playbook_repo/files/playbooks/**``
and are excluded from Hub lint via ``.ansible-lint`` (see issue #370 / #369).
"""
from __future__ import annotations

import shutil
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


def test_nested_aws_playbook_fqcns_resolve_via_ansible(tmp_path: Path) -> None:
    """ansible-core collection loader maps nested dirs to dotted FQCNs."""
    coll_root = (
        tmp_path
        / "ansible_collections"
        / "infra"
        / "automation_development_office"
    )
    coll_root.mkdir(parents=True)
    shutil.copytree(ROOT / "playbooks", coll_root / "playbooks")
    shutil.copytree(ROOT / "meta", coll_root / "meta")
    shutil.copy(ROOT / "galaxy.yml", coll_root / "galaxy.yml")
    (coll_root / "README.md").write_text("unit fixture\n", encoding="utf-8")

    from ansible.utils.collection_loader import _collection_finder as cf
    from ansible.utils.collection_loader._collection_finder import (
        _get_collection_playbook_path,
    )

    finder = cf._AnsibleCollectionFinder(paths=[str(tmp_path)])
    finder._install()

    for fqcn, rel in NESTED_AWS_PLAYBOOKS:
        resolved = _get_collection_playbook_path(fqcn)
        assert resolved is not None, fqcn
        _name, path, collection = resolved
        assert collection == "infra.automation_development_office"
        assert Path(path).resolve() == (coll_root / rel).resolve()
