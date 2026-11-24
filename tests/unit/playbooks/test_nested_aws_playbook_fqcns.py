"""Nested AWS collection playbook FQCNs resolve on ansible-core >= 2.17.

Automation Hub 2.1.4 import reported ``Failed to find`` for these FQCNs.
ansible-core resolves ``playbooks/<platform>/<service>/<name>.yml`` as
``namespace.collection.<platform>.<service>.<name>``. Keep the nested layout;
do not flatten for Hub. Seed Contoller playbooks that ``import_playbook`` these
FQCNs stay under ``roles/bootstrap_generate_playbook_repo/files/playbooks/**``
and are excluded from Hub lint via ``.ansible-lint`` (see issue #370 / #369).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

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

_MINIMAL_PLAYBOOK = """---
- hosts: localhost
  gather_facts: false
  tasks:
    - ansible.builtin.debug:
        msg: nested-fqcn-ok
"""


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


def test_nested_aws_playbook_fqcns_resolve_via_ansible(tmp_path: Path) -> None:
    """ansible-playbook finds nested collection playbooks by dotted FQCN."""
    coll_root = (
        tmp_path
        / "ansible_collections"
        / "infra"
        / "automation_development_office"
    )
    coll_root.mkdir(parents=True)
    # Minimal collection (no amazon.aws deps) at the same nested paths as production.
    for _fqcn, rel in NESTED_AWS_PLAYBOOKS:
        dest = coll_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_MINIMAL_PLAYBOOK, encoding="utf-8")
    shutil.copy(ROOT / "galaxy.yml", coll_root / "galaxy.yml")
    meta = yaml.safe_load((ROOT / "meta" / "runtime.yml").read_text(encoding="utf-8"))
    (coll_root / "meta").mkdir()
    (coll_root / "meta" / "runtime.yml").write_text(
        yaml.safe_dump(meta),
        encoding="utf-8",
    )
    (coll_root / "README.md").write_text("unit fixture\n", encoding="utf-8")
    (coll_root / "plugins").mkdir()

    env = os.environ.copy()
    env["ANSIBLE_COLLECTIONS_PATH"] = str(tmp_path)
    env["ANSIBLE_LOCAL_TEMP"] = str(tmp_path / "tmp")
    # Avoid picking up a different collections path from ansible.cfg in the repo.
    env.pop("ANSIBLE_CONFIG", None)

    ansible_playbook = shutil.which("ansible-playbook") or "ansible-playbook"
    for fqcn, _rel in NESTED_AWS_PLAYBOOKS:
        proc = subprocess.run(
            [ansible_playbook, "--syntax-check", fqcn],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        assert proc.returncode == 0, (
            f"{fqcn} failed syntax-check (exit {proc.returncode}):\n{combined}"
        )
        assert "could not be found" not in combined.lower()
