#!/usr/bin/env python3
"""Run ansible-doc against a built collection without amazon.aws installed.

Reproduces the Automation Hub import failure mode where
``extends_documentation_fragment: amazon.aws.*`` breaks ``ansible-doc``, and
verifies TLS filter sidecars parse without external collections.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NS = "infra.automation_development_office"

FILTERS = (
    f"{NS}.tls_first_pem_trust_bundle",
    f"{NS}.tls_pem_looks_like_certificate",
    f"{NS}.tls_split_pem_certificates",
    f"{NS}.tls_trust_bundle_from_secret",
    # Also exercised during Hub import alongside the TLS filters.
    f"{NS}.ocp_absent_cleanup_cleanup_refused",
)

MODULES = (
    f"{NS}.ec2_ami_copy",
    f"{NS}.rhel_stig_cac_report",
    f"{NS}.rhel_stig_cac_resolve",
)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Collection repository root",
    )
    args = parser.parse_args()
    root: Path = args.repo_root.resolve()

    work = Path(tempfile.mkdtemp(prefix="ado-ansible-doc-hub-"))
    collections_path = work / "collections"
    collections_path.mkdir(parents=True)

    env = os.environ.copy()
    # Isolated path: amazon.aws must not be present.
    env["ANSIBLE_COLLECTIONS_PATH"] = str(collections_path)
    env["ANSIBLE_COLLECTIONS_PATHS"] = str(collections_path)
    env["ANSIBLE_LOCAL_TEMP"] = str(work / "ansible-tmp")
    (work / "ansible-tmp").mkdir(parents=True, exist_ok=True)
    env.pop("ANSIBLE_LIBRARY", None)

    try:
        build = _run(
            ["ansible-galaxy", "collection", "build", "--force"],
            cwd=root,
            env=env,
        )
        if build.returncode != 0:
            print(_combined(build), file=sys.stderr)
            print("ERROR: collection build failed", file=sys.stderr)
            return 1

        tarballs = sorted(root.glob("infra-automation_development_office-*.tar.gz"))
        if not tarballs:
            print("ERROR: no collection tarball found after build", file=sys.stderr)
            return 1
        tarball = tarballs[-1]

        # --no-deps keeps amazon.aws (and other deps) out of the path so this
        # matches Automation Hub's ansible-doc pass without those fragments.
        install = _run(
            [
                "ansible-galaxy",
                "collection",
                "install",
                str(tarball),
                "-p",
                str(collections_path),
                "--force",
                "--no-deps",
            ],
            cwd=root,
            env=env,
        )
        if install.returncode != 0:
            print(_combined(install), file=sys.stderr)
            print("ERROR: collection install failed", file=sys.stderr)
            return 1

        # Guard: amazon.aws must not sneak in via transitive install.
        amazon_aws = (
            collections_path / "ansible_collections" / "amazon" / "aws"
        )
        if amazon_aws.exists():
            print(
                "ERROR: amazon.aws is present under the isolated collections "
                "path; Hub-import simulation is invalid",
                file=sys.stderr,
            )
            return 1

        failures: list[str] = []

        filter_cmd = [
            "ansible-doc",
            "--type",
            "filter",
            "--json",
            *FILTERS,
        ]
        filt = _run(filter_cmd, cwd=root, env=env)
        if filt.returncode != 0:
            failures.append("filters:\n" + _combined(filt))

        module_cmd = [
            "ansible-doc",
            "--type",
            "module",
            "--json",
            *MODULES,
        ]
        mods = _run(module_cmd, cwd=root, env=env)
        if mods.returncode != 0:
            failures.append("modules:\n" + _combined(mods))
        else:
            # Explicitly catch the Hub fragment error string if somehow rc==0.
            text = _combined(mods)
            if "unknown doc_fragment" in text or "Missing documentation" in text:
                failures.append("modules (doc parse):\n" + text)

        if failures:
            print("\n".join(failures), file=sys.stderr)
            print(
                "ERROR: ansible-doc failed without amazon.aws installed "
                "(Automation Hub import scenario)",
                file=sys.stderr,
            )
            return 1

        print(
            "OK: ansible-doc succeeded for TLS filters and modules "
            f"without amazon.aws (artifact {tarball.name})"
        )
        return 0
    finally:
        # Leave tarball in repo root like other build scripts; only wipe workdir.
        shutil.rmtree(work, ignore_errors=True)
        for leftover in root.glob("infra-automation_development_office-*.tar.gz"):
            try:
                leftover.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
