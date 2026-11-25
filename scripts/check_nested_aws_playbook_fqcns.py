#!/usr/bin/env python3
"""Validate nested AWS collection playbook FQCNs against a built artifact.

1. Build + install this collection into a collections path (reuse deps if present).
2. ``ansible-playbook --syntax-check`` the seven README-advertised nested FQCNs
   from the installed artifact (reproduces the Hub ``Failed to find`` case).
3. Syntax-check Contoller seed wrappers that ``import_playbook`` those FQCNs
   (excluded from Hub ansible-lint) inside a stub generated-project layout.

amazon.aws must be installed into ``--collections-path`` (CI installs
``collections/requirements.yml`` first). Without it, playbook resolution is
still checked, but module resolution failures are reported as errors.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NS_COLL = "infra.automation_development_office"

NESTED_AWS_FQCNS = (
    f"{NS_COLL}.aws.ec2.ado_ec2_instance_create",
    f"{NS_COLL}.aws.ec2.ado_ec2_instance_delete",
    f"{NS_COLL}.aws.ec2.ado_ec2_instance_info",
    f"{NS_COLL}.aws.ec2.ado_ec2_instance_modify",
    f"{NS_COLL}.aws.s3.ado_s3_bucket_policy_set",
    f"{NS_COLL}.aws.s3.ado_s3_bucket_policy_set_from_file",
    f"{NS_COLL}.aws.s3.ado_s3_bucket_policy_info",
)

AWS_SEED_PLAYBOOKS = (
    "playbooks/aws/ec2/ado-ec2-instance-create-bootstrap.yml",
    "playbooks/aws/ec2/ado-ec2-instance-delete-bootstrap.yml",
    "playbooks/aws/ec2/ado-ec2-instance-info-bootstrap.yml",
    "playbooks/aws/ec2/ado-ec2-instance-modify-bootstrap.yml",
    "playbooks/aws/s3/ado-s3-bucket-policy-set-bootstrap.yml",
    "playbooks/aws/s3/ado-s3-bucket-policy-set-from-file-bootstrap.yml",
    "playbooks/aws/s3/ado-s3-bucket-policy-info-bootstrap.yml",
)

SEED_ROOT = Path("roles/bootstrap_generate_playbook_repo/files")


def _run(
    cmd: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _combined(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "") + (proc.stderr or "")


def _playbook_missing(text: str) -> bool:
    lower = text.lower()
    return (
        "could not be found" in lower
        or "failed to find" in lower
        or "error! the playbook:" in lower
    )


def _amazon_aws_installed(collections_path: Path) -> bool:
    aws_root = collections_path / "ansible_collections" / "amazon" / "aws"
    # Installed collections often keep MANIFEST.json and omit galaxy.yml.
    return (aws_root / "MANIFEST.json").is_file() or (aws_root / "galaxy.yml").is_file()


def _must_syntax_ok(proc: subprocess.CompletedProcess[str], label: str) -> None:
    text = _combined(proc)
    if _playbook_missing(text):
        raise SystemExit(f"FAIL: playbook not found for {label}\n{text}")
    if proc.returncode != 0:
        raise SystemExit(f"FAIL: {label} (exit {proc.returncode})\n{text}")
    print(f"OK: {label}")


def install_this_collection(repo: Path, collections_path: Path) -> None:
    dist = collections_path / "_dist"
    dist.mkdir(parents=True, exist_ok=True)
    build = _run(
        [
            "ansible-galaxy",
            "collection",
            "build",
            "--force",
            "--output-path",
            str(dist),
        ],
        cwd=repo,
        env=os.environ.copy(),
    )
    if build.returncode != 0:
        raise SystemExit(f"collection build failed:\n{_combined(build)}")
    tarballs = sorted(dist.glob("*.tar.gz"))
    if not tarballs:
        raise SystemExit("no collection tarball produced")
    install = _run(
        [
            "ansible-galaxy",
            "collection",
            "install",
            str(tarballs[-1]),
            "--force",
            "--no-deps",
            "-p",
            str(collections_path),
        ],
        cwd=repo,
        env=os.environ.copy(),
    )
    if install.returncode != 0:
        raise SystemExit(f"collection install failed:\n{_combined(install)}")


def check_nested_fqcns(collections_path: Path, work: Path) -> None:
    env = os.environ.copy()
    env["ANSIBLE_COLLECTIONS_PATH"] = str(collections_path)
    env["ANSIBLE_LOCAL_TEMP"] = str(work / "tmp")
    env.pop("ANSIBLE_CONFIG", None)
    ansible_playbook = shutil.which("ansible-playbook") or "ansible-playbook"
    for fqcn in NESTED_AWS_FQCNS:
        proc = _run(
            [ansible_playbook, "--syntax-check", fqcn],
            cwd=work,
            env=env,
        )
        _must_syntax_ok(proc, f"syntax-check {fqcn}")


def _write_stub_group_vars(project: Path) -> None:
    gv = project / "group_vars" / "all" / "ci"
    gv.mkdir(parents=True, exist_ok=True)
    (gv / "infra_config_vars.yml").write_text(
        "---\n# CI stub for seed playbook syntax-check\n",
        encoding="utf-8",
    )
    (gv / "vault_aws.yml").write_text(
        "---\nvault_aws_access_key_id: ci\nvault_aws_secret_access_key: ci\n",
        encoding="utf-8",
    )
    (gv / "vars_ec2_instance.yml").write_text(
        "---\nec2_instance_name: ci-instance\n",
        encoding="utf-8",
    )
    (gv / "vars_s3_bucket_policy.yml").write_text(
        "---\ns3_bucket_name: ci-bucket\n",
        encoding="utf-8",
    )


def check_aws_seed_playbooks(
    repo: Path, collections_path: Path, work: Path
) -> None:
    project = work / "controller_project"
    seed_src = repo / SEED_ROOT
    for rel in AWS_SEED_PLAYBOOKS:
        src = seed_src / rel
        dest = project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    for rel in (
        "playbooks/aws/ec2/tasks/promote-ec2-instance-facts.yml",
        "playbooks/aws/s3/tasks/promote-s3-bucket-policy-facts.yml",
        "playbooks/aws/s3/policies/allow_list_and_read.json",
    ):
        src = seed_src / rel
        if src.is_file():
            dest = project / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    _write_stub_group_vars(project)

    env = os.environ.copy()
    env["ANSIBLE_COLLECTIONS_PATH"] = str(collections_path)
    env["ANSIBLE_LOCAL_TEMP"] = str(work / "tmp")
    env.pop("ANSIBLE_CONFIG", None)
    ansible_playbook = shutil.which("ansible-playbook") or "ansible-playbook"

    for rel in AWS_SEED_PLAYBOOKS:
        playbook = project / rel
        proc = _run(
            [ansible_playbook, "--syntax-check", str(playbook), "-e", "env=ci"],
            cwd=project,
            env=env,
        )
        _must_syntax_ok(proc, f"seed syntax-check {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Collection repository root (default: cwd)",
    )
    parser.add_argument(
        "--collections-path",
        type=Path,
        default=None,
        help=(
            "Collections path that already contains amazon.aws and other deps "
            "(default: temporary directory)"
        ),
    )
    args = parser.parse_args()
    repo = args.repo.resolve()

    with tempfile.TemporaryDirectory(prefix="ado-nested-aws-fqcn-") as tmp:
        tmp_path = Path(tmp)
        if args.collections_path is not None:
            collections_path = args.collections_path.resolve()
            collections_path.mkdir(parents=True, exist_ok=True)
        else:
            collections_path = tmp_path / "collections"
            collections_path.mkdir()

        print(f"Installing this collection into {collections_path} …")
        install_this_collection(repo, collections_path)
        if not _amazon_aws_installed(collections_path):
            raise SystemExit(
                "amazon.aws is not installed in the collections path. "
                "Install collections/requirements.yml first (CI does this), "
                f"then re-run. Missing: {collections_path}/ansible_collections/amazon/aws"
            )

        print("Checking nested AWS FQCNs from installed artifact…")
        check_nested_fqcns(collections_path, tmp_path)
        print("Checking Contoller AWS seed playbooks (Hub lint excludes)…")
        check_aws_seed_playbooks(repo, collections_path, tmp_path)

    print("All nested AWS playbook FQCN / seed syntax checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
