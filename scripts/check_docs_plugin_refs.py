#!/usr/bin/env python3
"""Fail if shipped docs reference plugins/roles missing from the collection artifact.

Builds (or reuses) the collection tarball, then compares ``:ansplugin:`` FQCNs and
antsibull plugin RST basenames under ``docs/`` against plugins and roles that
actually ship in the artifact. Prevents collection-template stubs from returning.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

NS_COLL = "infra.automation_development_office"

# :ansplugin:`infra.automation_development_office.name#type`
# :ansplugin:`label <infra.automation_development_office.name#type>`
ANSPLUGIN_RE = re.compile(
    rf":ansplugin:`(?:[^`<]*<)?{re.escape(NS_COLL)}\.([a-z0-9_]+)#([a-z]+)>?`"
)

# antsibull filenames: <name>_<type>.rst (module, filter, lookup, test, role, …)
ANTSIBULL_DOC_RE = re.compile(
    r"^(?P<name>[a-z0-9_]+)_(?P<type>module|filter|lookup|test|role)\.rst$"
)

# Top-level legacy stubs: docs/infra.automation_development_office.<name>_<type>.rst
LEGACY_DOC_RE = re.compile(
    rf"^{re.escape(NS_COLL)}\.(?P<name>[a-z0-9_]+)_(?P<type>module|filter|lookup|test|role)\.rst$"
)

# antsibull index pages are not plugin docs
SKIP_ANTSIBULL_DOC_NAMES = frozenset(
    {
        "index",
        "deprecations",
        "environment_variables",
    }
)

PLUGIN_TYPE_DIRS = {
    "module": "plugins/modules",
    "filter": "plugins/filter",
    "lookup": "plugins/lookup",
    "test": "plugins/test",
    "action": "plugins/action",
}


def build_collection(repo: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ansible-galaxy", "collection", "build", "--output-path", str(out_dir)],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    tarballs = sorted(out_dir.glob("*.tar.gz"))
    if not tarballs:
        raise SystemExit("ansible-galaxy collection build produced no tarball")
    return tarballs[-1]


def list_artifact_members(tarball: Path) -> tuple[str, list[str]]:
    """Return (archive_prefix, member_paths_relative_to_collection_root)."""
    with tarfile.open(tarball, "r:gz") as tar:
        names = tar.getnames()
    # ansible-galaxy may emit flat roots (MANIFEST.json at top) or a
    # ``<namespace>-<name>-<version>/`` prefix depending on tooling version.
    if "MANIFEST.json" in names or "./MANIFEST.json" in names:
        prefix = ""
        members = [n[2:] if n.startswith("./") else n for n in names]
        return prefix, members
    # Prefixed layout: take the shared first component.
    top = names[0].split("/", 1)[0]
    prefix = top + "/"
    members = []
    for name in names:
        if name.startswith(prefix):
            members.append(name[len(prefix) :])
        elif name == top:
            continue
    return prefix, members


def _filter_names_from_python(source: str) -> set[str]:
    """Return filter entrypoint names declared in a FilterModule.filters() dict."""
    names: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        if isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.add(key.value)
    return names


def existing_plugins(
    members: list[str], tar: tarfile.TarFile, prefix: str
) -> dict[str, set[str]]:
    """Map plugin type -> set of plugin names present in the artifact."""
    found: dict[str, set[str]] = defaultdict(set)

    for member in members:
        role_match = re.match(r"^roles/([^/]+)/", member)
        if role_match:
            found["role"].add(role_match.group(1))

        for ptype, directory in PLUGIN_TYPE_DIRS.items():
            dir_prefix = directory.rstrip("/") + "/"
            if not member.startswith(dir_prefix) or member.endswith("/"):
                continue
            rel = member[len(dir_prefix) :]
            if "/" in rel:
                continue
            stem = Path(rel).stem
            if not stem or stem.startswith("_"):
                continue
            suffix = Path(rel).suffix
            if suffix in {".py", ".yml", ".yaml"}:
                found[ptype].add(stem)
            # Multi-filter Python modules expose several FQCNs from one file.
            if ptype == "filter" and suffix == ".py":
                extracted = tar.extractfile(prefix + member)
                if extracted is not None:
                    found[ptype].update(
                        _filter_names_from_python(
                            extracted.read().decode("utf-8", errors="replace")
                        )
                    )

    return found


def docs_references(
    members: list[str], tar: tarfile.TarFile, prefix: str
) -> set[tuple[str, str, str]]:
    """Return {(name, type, source)} referenced from shipped docs."""
    refs: set[tuple[str, str, str]] = set()
    for member in members:
        if not member.startswith("docs/") or not member.endswith(".rst"):
            continue
        f = tar.extractfile(prefix + member)
        if f is None:
            continue
        text = f.read().decode("utf-8", errors="replace")
        for match in ANSPLUGIN_RE.finditer(text):
            refs.add((match.group(1), match.group(2), member))

        base = Path(member).name
        m = ANTSIBULL_DOC_RE.match(base) or LEGACY_DOC_RE.match(base)
        if m and m.group("name") not in SKIP_ANTSIBULL_DOC_NAMES:
            refs.add((m.group("name"), m.group("type"), member))
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Collection repository root (default: cwd)",
    )
    parser.add_argument(
        "--tarball",
        type=Path,
        default=None,
        help="Existing collection tarball (default: build one)",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()

    with tempfile.TemporaryDirectory(prefix="ado-docs-plugin-refs-") as tmp:
        tarball = args.tarball
        if tarball is None:
            tarball = build_collection(repo, Path(tmp) / "dist")
        else:
            tarball = tarball.resolve()

        prefix, members = list_artifact_members(tarball)

        with tarfile.open(tarball, "r:gz") as tar:
            plugins = existing_plugins(members, tar, prefix)
            refs = docs_references(members, tar, prefix)

        missing = []
        for name, ptype, source in sorted(refs):
            if name not in plugins.get(ptype, set()):
                missing.append(f"{NS_COLL}.{name}#{ptype}  (from {source})")

        print(f"Checked tarball: {tarball}")
        print(
            "Artifact content: "
            + ", ".join(f"{k}={len(v)}" for k, v in sorted(plugins.items()))
        )
        print(f"Docs references: {len(refs)}")
        if missing:
            print("ERROR: docs reference plugins/roles missing from the artifact:")
            for line in missing:
                print(f"  - {line}")
            return 1
        print("OK: all docs plugin/role references exist in the collection artifact.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
