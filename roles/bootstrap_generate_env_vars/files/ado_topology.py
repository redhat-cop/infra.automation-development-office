"""Route internal infrastructure topology out of generated group_vars into Ansible Vault.

Internal hostnames, domains, API endpoints, SMTP relays, IP addresses and LDAP
base DNs show how an environment is built. They are not passwords, but they do
not belong in a plaintext Git repository either.

``freeze`` moves each such value into a vault file of the same environment and
leaves a reference where the value was. Nothing else changes: the key keeps its
name, its place in the file and its load order, so roles need no edit::

    # vars_grafana.yml (Git, plaintext)
    hostname: "{{ vault_topology_vars_grafana__hostname }}"

    # vault_openshift.yml (Git, Ansible Vault ciphertext)
    vault_topology_vars_grafana__hostname: grafana.apps.internal.example

Reference names are unique per file and key path, so two components that both
define a top-level ``hostname`` never collide.

Where a value is stored (its "home") is the vault file that every generated
playbook already loads together with the plaintext file. That is why no
playbook edit, and no regeneration of old playbooks, is needed::

    infra_config_vars.yml, vars_<component>.yml  ->  vault_openshift.yml
    aap_config_vars.yml, onboard_keycloak.yml    ->  aap_vault.yml
    vars_satellite / idm / smtp / unifi / aws    ->  the matching vault_<name>.yml

``thaw`` is the inverse. The generator thaws first so templates and the preflight
overlay always work on real values, and freezes once at the end. ``audit``
reports what would be routed without changing a file.

Nothing here prints a topology value. Reports name files and key paths only.

The detection rules are mirrored by the credential gate
(``ado_credential_gate.py``); keep the two in step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

# The detection rules live next to the credential gate, which copies them into generated repos.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent.parent / "bootstrap_generate_playbook_repo" / "files"))
from ado_topology_rules import (  # noqa: E402  (path set up above)
    REF_PREFIX,
    REF_RE,
    is_topology_value,
    key_hints_topology,
)

VAULT_HEADER = "$ANSIBLE_VAULT"

# Generated Controller configuration (configs/controller/*.yml) keeps its topology in
# aap_vault.yml under this prefix, separate from the group_vars entries.
CFG_PREFIX = REF_PREFIX + "cfg_"
# Job template and workflow files are read as raw YAML (not templated), so they can never
# carry references. They must hold no topology at all.
RAW_CONFIG_DIRS = ("job_templates", "workflows")

HOME_OPENSHIFT = "vault_openshift.yml"
HOME_AAP = "aap_vault.yml"
STEM_HOMES = {"aap_config_vars": HOME_AAP, "onboard_keycloak": HOME_AAP}
# Components whose playbooks load their own vault file but not vault_openshift.yml.
COMPONENT_HOMES = {
    "satellite": "vault_satellite.yml",
    "idm": "vault_idm.yml",
    "smtp": "vault_smtp.yml",
    "unifi": "vault_unifi.yml",
    "aws": "vault_aws.yml",
    "ec2_instance": "vault_aws.yml",
    "s3_bucket_policy": "vault_aws.yml",
    "ec2_ami_copy": "vault_aws.yml",
}


class TopologyError(RuntimeError):
    pass


# --------------------------------------------------------------------------- YAML helpers


def _walk(node, path=(), hint=False):
    """Yield ``(path, value, hint)`` for every string leaf; a host-like key hints its subtree."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, path + (str(key),), hint or key_hints_topology(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, path + (index,), hint)
    elif isinstance(node, str):
        yield path, node, hint


def _set(node, path, value):
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def dump_yaml(data) -> str:
    return "---\n" + yaml.dump(data, Dumper=_Dumper, sort_keys=False, width=1000)


def is_encrypted(text: str) -> bool:
    return text.lstrip().startswith(VAULT_HEADER)


def ref_name(stem: str, path: tuple, taken: dict) -> str:
    """Stable variable name for ``stem`` + ``path``; ``taken`` maps name -> (stem, path)."""
    parts = [stem] + [str(part) for part in path]
    slug = "__".join(re.sub(r"[^A-Za-z0-9]+", "_", part).strip("_") for part in parts)
    name = REF_PREFIX + slug
    owner = taken.get(name)
    if owner not in (None, (stem, path)):
        digest = hashlib.sha1(json.dumps([stem, list(path)], default=str).encode()).hexdigest()[:8]
        name = f"{name}_{digest}"
    taken[name] = (stem, path)
    return name


def refs_in(node) -> set[str]:
    found: set[str] = set()
    for _path, value, _hint in _walk(node):
        match = REF_RE.match(value.strip())
        if match:
            found.add(match.group(1))
    return found


def substitute_refs(node, mapping: dict):
    """Replace ``"{{ vault_topology_x }}"`` leaves with ``mapping['vault_topology_x']``."""
    count, missing = 0, []

    def go(item):
        nonlocal count
        if isinstance(item, dict):
            return {key: go(value) for key, value in item.items()}
        if isinstance(item, list):
            return [go(value) for value in item]
        if isinstance(item, str):
            match = REF_RE.match(item.strip())
            if match:
                name = match.group(1)
                if name in mapping:
                    count += 1
                    return mapping[name]
                missing.append(name)
        return item

    return go(node), count, missing


# --------------------------------------------------------------------------- files


def home_for(stem: str, present=None) -> str:
    """Vault file that stores topology for the plaintext file ``<stem>.yml``."""
    if stem in STEM_HOMES:
        return STEM_HOMES[stem]
    if stem.startswith("vars_"):
        home = COMPONENT_HOMES.get(stem[len("vars_"):])
        if home and (present is None or home in present):
            return home
    return HOME_OPENSHIFT


def is_vault_name(name: str) -> bool:
    return name.startswith("vault") or name.endswith(("_vault.yml", "_vault.yaml"))


def plaintext_group_files(env_dir: Path):
    """Plaintext YAML files in ``env_dir`` that may carry topology (never vault files)."""
    for path in sorted(Path(env_dir).iterdir()):
        name = path.name
        if path.is_file() and name.endswith((".yml", ".yaml")) and not is_vault_name(name):
            yield path


def vault_file_names(env_dir: Path) -> set[str]:
    return {p.name for p in Path(env_dir).iterdir() if p.is_file() and is_vault_name(p.name) and p.suffix in (".yml", ".yaml")}


def _vault_view(path: Path, vault_password_file: str | None) -> str:
    text = path.read_text()
    if not is_encrypted(text):
        return text
    if not vault_password_file:
        raise TopologyError(
            f"{path.name} is Ansible Vault ciphertext. Provide the vault password file "
            "(--vault-password-file, ANSIBLE_VAULT_PASSWORD_FILE or the preflight vault password) "
            "so existing topology can be read."
        )
    env = {k: v for k, v in os.environ.items() if k != "ANSIBLE_VAULT_PASSWORD_FILE"}
    result = subprocess.run(
        ["ansible-vault", "view", str(path), "--vault-password-file", vault_password_file],
        capture_output=True, text=True, check=False, env=env,
    )
    if result.returncode != 0:
        raise TopologyError(f"could not decrypt {path.name}: the vault password does not match or ansible-vault failed")
    return result.stdout


def read_vault_mapping(path: Path, vault_password_file: str | None) -> dict:
    try:
        data = yaml.safe_load(_vault_view(path, vault_password_file)) or {}
    except yaml.YAMLError as exc:
        raise TopologyError(f"{path.name} is not plain YAML ({type(exc).__name__})") from exc
    if not isinstance(data, dict):
        raise TopologyError(f"{path.name} must be a YAML mapping")
    return data


def _topology_subset(mapping: dict) -> dict:
    """Group_vars topology entries. Controller-config entries (``vault_topology_cfg_*``) are separate."""
    return {k: v for k, v in mapping.items() if str(k).startswith(REF_PREFIX) and not str(k).startswith(CFG_PREFIX)}


def gather_topology(env_dir: Path, wanted: dict[str, set[str]], vault_password_file: str | None) -> dict:
    """Read topology entries for ``wanted`` (plaintext file name -> reference names).

    Looks in each file's home first and only scans the other vault files when a
    reference is not found there, for example after a home mapping changed.
    """
    env_dir = Path(env_dir)
    present = vault_file_names(env_dir)
    mapping: dict = {}
    seen: set[str] = set()

    def load(name: str) -> None:
        if name in seen or name not in present:
            return
        seen.add(name)
        mapping.update(_topology_subset(read_vault_mapping(env_dir / name, vault_password_file)))

    for file_name, names in wanted.items():
        if names:
            load(home_for(Path(file_name).stem, present))
    needed = set().union(*wanted.values()) if wanted else set()
    if needed - set(mapping):
        for name in sorted(present):
            load(name)
    return mapping


def thaw(env_dir: Path, vault_password_file: str | None = None, write: bool = True) -> dict:
    """Put real values back into plaintext files. The report names counts, never values."""
    env_dir = Path(env_dir)
    loaded: dict[Path, object] = {}
    wanted: dict[str, set[str]] = {}
    for path in plaintext_group_files(env_dir):
        text = path.read_text()
        if is_encrypted(text):
            continue
        data = yaml.safe_load(text)
        refs = refs_in(data)
        if refs:
            loaded[path] = data
            wanted[path.name] = refs
    report: dict = {"restored": {}}
    if not loaded:
        return report
    mapping = gather_topology(env_dir, wanted, vault_password_file)
    for path, data in loaded.items():
        restored, count, missing = substitute_refs(data, mapping)
        if missing:
            raise TopologyError(
                f"{path.name} references {len(set(missing))} topology entr{'y' if len(set(missing)) == 1 else 'ies'} "
                "that no vault file in this environment contains. Restore the vault file from Git or regenerate the environment."
            )
        report["restored"][path.name] = count
        if write:
            path.write_text(dump_yaml(restored))
    return report


def classify(env_dir: Path) -> list[tuple[str, tuple]]:
    """Plaintext topology leaves as ``(file, key path)``; no values."""
    found = []
    for path in plaintext_group_files(Path(env_dir)):
        text = path.read_text()
        if is_encrypted(text):
            continue
        for leaf_path, value, hint in _walk(yaml.safe_load(text)):
            if is_topology_value(value, hint):
                found.append((path.name, leaf_path))
    return found


def status(env_dir: Path) -> dict:
    refs = 0
    for path in plaintext_group_files(Path(env_dir)):
        text = path.read_text()
        if not is_encrypted(text):
            refs += len(refs_in(yaml.safe_load(text)))
    return {"references": refs, "plaintext_topology_values": len(classify(env_dir))}


def freeze(env_dir: Path, vault_password_file: str | None = None, write: bool = True) -> dict:
    """Route every topology value into the vault files; return a report (no values).

    Existing references are resolved first, so the result is the complete set and a
    second run changes nothing. An encrypted vault file whose topology entries are
    already correct is left untouched, so Git shows no ciphertext churn. Files
    written here are plaintext; the generator's normal pass encrypts them.
    """
    env_dir = Path(env_dir)
    present = vault_file_names(env_dir)
    parsed: dict[Path, object] = {}
    wanted: dict[str, set[str]] = {}
    for path in plaintext_group_files(env_dir):
        text = path.read_text()
        if is_encrypted(text):
            continue
        data = yaml.safe_load(text)
        if not data:
            continue
        parsed[path] = data
        wanted[path.name] = refs_in(data)
    existing = gather_topology(env_dir, wanted, vault_password_file) if any(wanted.values()) else {}

    taken: dict[str, tuple] = {}
    by_home: dict[str, dict] = {}
    rewrites: dict[Path, object] = {}
    report: dict = {"files": {}, "routed": 0, "vault_files": {}}
    for path, data in parsed.items():
        data, _count, missing = substitute_refs(data, existing)
        if missing:
            raise TopologyError(
                f"{path.name} references topology entries missing from the vault files: {', '.join(sorted(set(missing)))}"
            )
        leaves = [(p, v, h) for p, v, h in _walk(data) if is_topology_value(v, h)]
        if not leaves:
            continue
        home = home_for(path.stem, present)
        for leaf_path, value, _hint in leaves:
            name = ref_name(path.stem, leaf_path, taken)
            by_home.setdefault(home, {})[name] = value.strip()
            _set(data, leaf_path, "{{ " + name + " }}")
        report["files"][path.name] = len(leaves)
        rewrites[path] = data
    report["routed"] = sum(len(v) for v in by_home.values())

    # Plaintext vault files that still hold topology no file references any more.
    for name in sorted(present):
        path = env_dir / name
        if name not in by_home and not is_encrypted(path.read_text()):
            if _topology_subset(read_vault_mapping(path, None)):
                by_home[name] = {}

    written: list[str] = []
    for home, entries in sorted(by_home.items()):
        path = env_dir / home
        current = read_vault_mapping(path, vault_password_file) if path.exists() else {}
        encrypted = path.exists() and is_encrypted(path.read_text())
        if encrypted and _topology_subset(current) == entries:
            continue  # unchanged: keep the existing ciphertext byte for byte
        old = _topology_subset(current)
        desired = {k: v for k, v in current.items() if k not in old}
        desired.update(entries)
        report["vault_files"][home] = len(entries)
        written.append(home)
        if write:
            path.write_text(dump_yaml(desired))
            path.chmod(0o600)
    report["written"] = written
    if write:
        for path, data in rewrites.items():
            path.write_text(dump_yaml(data))
    return report


# --------------------------------------------------------------------------- Controller configs


def _config_files(configs_dir: Path):
    for path in sorted(Path(configs_dir).rglob("*.yml")):
        yield path.relative_to(configs_dir), path


def _is_raw_config(rel: Path) -> bool:
    return len(rel.parts) > 1 and rel.parts[0] in RAW_CONFIG_DIRS


def _config_leaves(path: Path):
    text = path.read_text()
    if is_encrypted(text):
        return None, []
    data = yaml.safe_load(text)
    if not isinstance(data, (dict, list)):
        return None, []
    return data, [(p, v, h) for p, v, h in _walk(data) if is_topology_value(v, h)]


def audit_configs(configs_dir: Path) -> list[tuple[str, tuple, bool]]:
    """Plaintext topology in generated configs as ``(file, key path, raw)``; never values."""
    found = []
    for rel, path in _config_files(configs_dir):
        _data, leaves = _config_leaves(path)
        found.extend((rel.as_posix(), leaf[0], _is_raw_config(rel)) for leaf in leaves)
    return found


def freeze_configs(configs_dir: Path, env_dir: Path, vault_password_file: str | None = None, write: bool = True) -> dict:
    """Route topology in generated Controller configs into ``aap_vault.yml``; return a report.

    ``configs/controller/*.yml`` are loaded with ``include_vars``, so a reference resolves from the
    vault files the Controller role already loads. Job template and workflow files are read as raw
    YAML and cannot hold references, so topology there is an error (the generator must not put it
    there). Entries use the ``vault_topology_cfg_`` prefix; stale ones are removed, and an encrypted
    ``aap_vault.yml`` whose entries are already correct is left byte-for-byte untouched.
    """
    configs_dir, env_dir = Path(configs_dir), Path(env_dir)
    taken: dict[str, tuple] = {}
    entries: dict[str, str] = {}
    rewrites: dict[Path, object] = {}
    report: dict = {"files": {}, "routed": 0, "written": []}
    unresolvable: list[str] = []
    for rel, path in _config_files(configs_dir):
        data, leaves = _config_leaves(path)
        if not leaves:
            continue
        if _is_raw_config(rel):
            unresolvable.extend(f"{rel.as_posix()}:{'.'.join(str(p) for p in leaf[0])}" for leaf in leaves)
            continue
        stem = "cfg_" + "_".join(rel.with_suffix("").parts)
        for leaf_path, value, _hint in leaves:
            name = ref_name(stem, leaf_path, taken)
            entries[name] = value.strip()
            _set(data, leaf_path, "{{ " + name + " }}")
        report["files"][rel.as_posix()] = len(leaves)
        rewrites[path] = data
    if unresolvable:
        raise TopologyError(
            "generated job template or workflow files contain internal topology, which cannot be "
            "Vault-encrypted because they are read as raw YAML: " + ", ".join(sorted(unresolvable))
        )
    report["routed"] = len(entries)

    home = env_dir / HOME_AAP
    current = read_vault_mapping(home, vault_password_file) if home.exists() else {}
    encrypted = home.exists() and is_encrypted(home.read_text())
    stored = {k: v for k, v in current.items() if str(k).startswith(CFG_PREFIX)}
    if not (encrypted and stored == entries) and (entries or stored):
        desired = {k: v for k, v in current.items() if k not in stored}
        desired.update(entries)
        report["written"].append(HOME_AAP)
        if write:
            env_dir.mkdir(parents=True, exist_ok=True)
            home.write_text(dump_yaml(desired))
            home.chmod(0o600)
    if write:
        for path, data in rewrites.items():
            path.write_text(dump_yaml(data))
    return report


def encrypt_files(env_dir: Path, names, vault_password_file: str) -> list[str]:
    done = []
    env = {k: v for k, v in os.environ.items() if k != "ANSIBLE_VAULT_PASSWORD_FILE"}
    for name in names:
        path = Path(env_dir) / name
        if not path.exists() or is_encrypted(path.read_text()):
            continue
        result = subprocess.run(
            ["ansible-vault", "encrypt", str(path), "--encrypt-vault-id", "default", "--vault-password-file", vault_password_file],
            capture_output=True, text=True, check=False, env=env,
        )
        if result.returncode != 0:
            raise TopologyError(f"ansible-vault could not encrypt {name}")
        done.append(name)
    return done


# --------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("command", choices=("audit", "status", "thaw", "freeze", "migrate", "audit-configs", "freeze-configs"))
    parser.add_argument("--env-dir", help="group_vars/all/<env> directory (not needed for audit-configs)")
    parser.add_argument(
        "--vault-password-file",
        default=os.environ.get("ADO_VAULT_PASSWORD_FILE") or os.environ.get("ANSIBLE_VAULT_PASSWORD_FILE"),
        help="needed to read or write encrypted vault files; a path, never the password itself",
    )
    parser.add_argument("--configs-dir", help="audit-configs/freeze-configs: the generated configs/ directory")
    parser.add_argument("--encrypt", action="store_true", help="freeze/migrate: encrypt the vault files it wrote")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command != "audit-configs" and not args.env_dir:
        print("ado_topology: --env-dir is required", file=sys.stderr)
        return 2
    env_dir = Path(args.env_dir or ".")
    if args.command != "audit-configs" and not env_dir.is_dir():
        print(f"ado_topology: {env_dir} is not a directory", file=sys.stderr)
        return 2
    try:
        if args.command in ("audit-configs", "freeze-configs"):
            if not args.configs_dir or not Path(args.configs_dir).is_dir():
                print("ado_topology: --configs-dir must be an existing directory", file=sys.stderr)
                return 2
            if args.command == "audit-configs":
                found = audit_configs(Path(args.configs_dir))
                report = {"plaintext_topology_values": len(found), "raw": sum(1 for f in found if f[2])}
                if args.json:
                    print(json.dumps(report, indent=2))
                else:
                    print(f"plaintext topology values in configs: {len(found)}")
                    for name, leaf, raw in found:
                        print(f"  {name}: {'.'.join(str(p) for p in leaf)}{' (raw YAML, cannot hold references)' if raw else ''}")
                return 3 if found else 0
            report = freeze_configs(Path(args.configs_dir), env_dir, args.vault_password_file)
            if args.encrypt:
                if not args.vault_password_file:
                    raise TopologyError("--vault-password-file is required to encrypt vault files")
                report["encrypted"] = encrypt_files(env_dir, report["written"], args.vault_password_file)
            print(json.dumps(report, indent=2) if args.json else "\n".join(f"{k}: {v}" for k, v in report.items()))
            return 0
        if args.command in ("audit", "status"):
            found = classify(env_dir)
            report = status(env_dir)
            report["files"] = {}
            for name, _leaf in found:
                report["files"][name] = report["files"].get(name, 0) + 1
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"references: {report['references']}  plaintext topology values: {report['plaintext_topology_values']}")
                for name, leaf in found:
                    print(f"  {name}: {'.'.join(str(p) for p in leaf)}")
            return 3 if args.command == "audit" and found else 0
        if args.command == "thaw":
            report = thaw(env_dir, args.vault_password_file)
        else:
            report = freeze(env_dir, args.vault_password_file)
            if args.command == "migrate" or args.encrypt:
                if not args.vault_password_file:
                    raise TopologyError("--vault-password-file is required to encrypt vault files")
                report["encrypted"] = encrypt_files(env_dir, report["written"], args.vault_password_file)
        print(json.dumps(report, indent=2) if args.json else "\n".join(f"{k}: {v}" for k, v in report.items()))
        return 0
    except TopologyError as exc:
        print(f"ado_topology: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
