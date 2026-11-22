# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression guard: no embedded credentials anywhere in the collection source.

Policy
------
* Real hardcoded passwords, tokens and keys are never allowed.
* Clearly synthetic placeholders are allowed in documentation and isolated test fixtures
  (they must say so: ``synthetic``, ``example``, ``placeholder``, ``dummy``, ``fake``).
* An operation that needs a credential takes it from a supplied variable, an AAP credential,
  Ansible Vault, or generates one. It must not fall back to a shipped value.

This test scans the repository source tree (not git history) for:

A. well-known fallback passwords that earlier versions shipped;
B. secret-named keys that carry a literal value in roles, playbooks and molecule data;
C. credentials embedded in URLs;
D. token and private-key patterns;
E. files that must never be committed (vault password files, plaintext preflight exports,
   Python/cache trees).

Every exception is listed below with the reason. Add to an allow-list only with a reason that
a reviewer can check; "it is a lab password" is not one.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

SKIP_DIRS = {
    ".git",
    ".ansible",
    ".local",
    ".cache",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".tox",
    ".venv",
}
# Unit tests and changelogs legitimately name the strings they forbid.
HISTORICAL_OR_TEST_PREFIXES = ("tests/", "changelogs/", "CHANGELOG.rst")

SCAN_SUFFIXES = {".yml", ".yaml", ".j2", ".json", ".ldif", ".sh", ".py", ".md", ".rst", ".cfg", ".conf", ".txt"}
DATA_SUFFIXES = {".yml", ".yaml", ".j2", ".json", ".ldif"}
# Roles, playbooks and molecule data are executable source. Docs and fixtures get the
# synthetic-placeholder allowance.
EXECUTABLE_PREFIXES = ("roles/", "playbooks/", "extensions/", "plugins/", "scripts/")

SYNTHETIC = re.compile(
    r"synthetic|example|placeholder|dummy|fake|replace[_-]?with|<[^>]+>|not[-_ ](?:a[-_ ]real|secret)|redacted|\*{3,}",
    re.IGNORECASE,
)

# --- A. fallback passwords earlier versions shipped ---------------------------------------
BANNED_LITERALS = (
    "redhat123",
    "quaypass",
    "changeme-secret-key",
    "changeme-backend-secret",
    "changeme-db",
    "change-me-db",
    "testpassword",
    "knuckle",
    "StrongAdminPassword123",
)
# (path, literal) -> reason. The strings below appear only in text that explains the removal.
BANNED_LITERAL_ALLOWED = {
    (
        "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py",
        "redhat123",
    ): "error text and a comment explaining that there is no default",
    (
        "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py",
        "changeme-db",
    ): "rejects a supplied value of this name; never writes it",
    (
        "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py",
        "change-me-db",
    ): "rejects a supplied value of this name; never writes it",
    ("roles/install_rhbk/README.md", "changeme-db"): "documents that the old default was removed",
    (
        "roles/bootstrap_generate_playbook_repo/files/ado_credential_gate.py",
        "changeme",
    ): "not a banned literal here; synthetic-word list (kept for completeness)",
}

# --- B. secret-named keys with literal values ---------------------------------------------
SECRET_KEY_SUFFIXES = (
    "password",
    "passwd",
    "passphrase",
    "secretkey",
    "token",
    "apikey",
    "privatekey",
    "bindcredential",
    "clientsecret",
    "backendsecret",
    "secretaccesskey",
)
# Secret-named key whose value is a name, a path, a flag or a reference and not a credential.
# (path-suffix, key) -> reason.
SECRET_KEY_ALLOWED = {
    ("roles/ocp_zabbix/defaults/main.yml", "zabbix_default_admin_password"): (
        "Zabbix upstream first-login credential. Used only to sign in once and replace it; "
        "the role refuses it as a target password (see install-zabbix.yml guard)."
    ),
    (
        "roles/bootstrap_resolve_component/files/components_defaults.yml",
        "zabbix_default_admin_password",
    ): "same Zabbix first-login credential, see above",
}

# Keys that look secret by name but are module options, flags or Secret data-key names.
NON_CREDENTIAL_KEYS = {
    "update_password": "ansible user-module option (always/on_create)",
    "dm_secret_key": "name of a key inside a Kubernetes Secret, not a value",
}
# Molecule scenarios that talk to a local fake cloud (fakecloud). Any string is accepted.
FAKE_CLOUD_PATHS = (
    "extensions/molecule/integration_ec2_ami_copy/molecule.yml",
    "extensions/molecule/integration_ec2_ami_copy_keep_name/molecule.yml",
    "extensions/molecule/integration_ec2_instance/molecule.yml",
    "extensions/molecule/integration_s3_bucket_policy/molecule.yml",
)

# --- D. token / key patterns ---------------------------------------------------------------
TOKEN_PATTERNS = {
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "gitlab-token": re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}\b"),
    "slack-token": re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "openshift-token": re.compile(r"\bsha256~[A-Za-z0-9_\-]{30,}\b"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
}
# (path, pattern) -> reason
TOKEN_ALLOWED: dict[tuple[str, str], str] = {}

# --- E. files that must not be committed --------------------------------------------------
FORBIDDEN_FILE_PATTERNS = (
    re.compile(r"(^|/)(\.vault[_-]?pass|vault[_-]pass)[^/]*$", re.IGNORECASE),
    re.compile(r"(^|/)ado-preflight-[^/]*\.json$"),
    re.compile(r"(^|/)(id_rsa|id_ed25519)$"),
)
# Synthetic fixtures that are named like an export on purpose.
FORBIDDEN_FILE_ALLOWED_PREFIXES = ("extensions/molecule/",)
FORBIDDEN_DIRS = (".local", ".cache")

URL_CREDENTIAL = re.compile(r"[a-z][a-z0-9+.\-]*://([^\s:/@'\"{}$<>]+):([^\s@'\"{}$<>]+)@", re.IGNORECASE)
# Words that stand for "a password goes here" in a URL shape such as user:pass@host.
URL_PLACEHOLDER_WORDS = {"pass", "password", "pw", "secret", "xxx", "xxxx"}
URL_CREDENTIAL_ALLOWED: dict[tuple[str, str], str] = {}


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_files() -> list[Path]:
    """Tracked and untracked-but-not-ignored files; falls back to a walk without git."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", "replace")
        paths = [REPO_ROOT / name for name in out.split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        paths = list(REPO_ROOT.rglob("*"))
    return sorted(
        p
        for p in paths
        if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(REPO_ROOT).parts)
    )


def _files(suffixes: set[str]) -> list[Path]:
    return [p for p in _source_files() if p.suffix.lower() in suffixes]


def _scannable(suffixes: set[str]) -> list[tuple[Path, str]]:
    out = []
    for path in _files(suffixes):
        rel = _rel(path)
        if rel.startswith(HISTORICAL_OR_TEST_PREFIXES):
            continue
        try:
            out.append((path, path.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, OSError):
            continue
    return out


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_secret_key(key: str) -> bool:
    return _normalize_key(key).endswith(SECRET_KEY_SUFFIXES)


def _literal_credential(value: object) -> bool:
    """True when ``value`` looks like an embedded credential rather than a reference."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.lower() in {"true", "false", "null", "none", "~"}:
        return False
    if "{{" in text or "{%" in text or "lookup(" in text or text.startswith(("$", "<")):
        return False
    if SYNTHETIC.search(text):
        return False
    if text.startswith((">", "|")):
        return False  # YAML block scalar: the value is on the following lines
    if re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", text):
        return False  # environment-variable name used as a placeholder
    if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", text) and _is_secret_key(text):
        return False  # another variable's name (alias)
    if text.startswith(("/", "./", "~/")) or "/" in text and " " not in text and "." in text.rsplit("/", 1)[-1]:
        return False  # file path
    return True


def _walk_mapping(node: object, trail: str = ""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else str(key)
            if isinstance(key, str) and _is_secret_key(key) and isinstance(value, (str, int, float)):
                yield key, value, here
            yield from _walk_mapping(value, here)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk_mapping(item, f"{trail}[{index}]")


def _data_documents(path: Path, text: str):
    """Yield parsed documents. Templates are parsed after neutralising Jinja."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            yield json.loads(text)
        elif suffix in {".yml", ".yaml"}:
            yield from yaml.safe_load_all(text)
    except (yaml.YAMLError, json.JSONDecodeError):
        return


_TEMPLATE_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*:\s*(.+?)\s*$")


def _template_pairs(text: str):
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = _TEMPLATE_LINE.match(line)
        if match and _is_secret_key(match.group(1)):
            value = match.group(2).strip().strip("'\"")
            yield match.group(1), value


def _allowed(table: dict, rel: str, key: str) -> bool:
    return any(rel == path and key == name for (path, name) in table)


# --------------------------------------------------------------------------------------------


def test_no_known_fallback_passwords_are_shipped() -> None:
    hits = []
    for path, text in _scannable(SCAN_SUFFIXES):
        rel = _rel(path)
        for literal in BANNED_LITERALS:
            if literal in text and (rel, literal) not in BANNED_LITERAL_ALLOWED:
                hits.append(f"{rel}: contains the retired fallback '{literal}'")
    assert not hits, "Retired fallback credentials found:\n" + "\n".join(hits)


def test_secret_named_keys_carry_no_literal_values() -> None:
    hits = []
    for path, text in _scannable(DATA_SUFFIXES):
        rel = _rel(path)
        if not rel.startswith(EXECUTABLE_PREFIXES):
            continue
        pairs: list[tuple[str, object]] = []
        if path.suffix.lower() == ".j2":
            pairs.extend(_template_pairs(text))
        else:
            for doc in _data_documents(path, text):
                pairs.extend((key, value) for key, value, _trail in _walk_mapping(doc))
        if path.suffix.lower() == ".ldif":
            pairs.extend(
                (m.group(1), m.group(2))
                for m in re.finditer(r"^(userPassword):\s*(\S+)\s*$", text, re.MULTILINE)
            )
        for key, value in pairs:
            if _allowed(SECRET_KEY_ALLOWED, rel, key) or key in NON_CREDENTIAL_KEYS:
                continue
            if key == "AWS_SECRET_ACCESS_KEY" and rel in FAKE_CLOUD_PATHS:
                continue  # fakecloud accepts any value; endpoint is local
            if _literal_credential(value if isinstance(value, str) else str(value)):
                hits.append(f"{rel}: key '{key}' has a literal value")
    assert not hits, (
        "Secret-named keys with embedded values. Use a supplied variable, a Vault reference "
        "or generate one:\n" + "\n".join(sorted(set(hits)))
    )


def test_no_credentials_embedded_in_urls() -> None:
    hits = []
    for path, text in _scannable(SCAN_SUFFIXES):
        rel = _rel(path)
        for match in URL_CREDENTIAL.finditer(text):
            user, password = match.group(1), match.group(2)
            if (
                SYNTHETIC.search(password)
                or password.lower() in URL_PLACEHOLDER_WORDS
                or (rel, user) in URL_CREDENTIAL_ALLOWED
            ):
                continue
            hits.append(f"{rel}: URL carries a literal password for user '{user}'")
    assert not hits, "Credentials embedded in URLs:\n" + "\n".join(sorted(set(hits)))


def test_no_token_or_private_key_patterns() -> None:
    hits = []
    for path, text in _scannable(SCAN_SUFFIXES | {".pem", ".key", ".crt"}):
        rel = _rel(path)
        for name, pattern in TOKEN_PATTERNS.items():
            if pattern.search(text) and (rel, name) not in TOKEN_ALLOWED:
                hits.append(f"{rel}: matches the {name} pattern")
    assert not hits, "Token or key material in source:\n" + "\n".join(hits)


def test_no_vault_password_files_or_plaintext_exports_are_committed() -> None:
    hits = []
    for path in _source_files():
        rel = _rel(path)
        if rel.startswith("tests/"):
            continue
        if any(part in FORBIDDEN_DIRS for part in Path(rel).parts):
            hits.append(f"{rel}: lives under a local cache directory")
            continue
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if pattern.search(rel) and not rel.startswith(FORBIDDEN_FILE_ALLOWED_PREFIXES):
                hits.append(f"{rel}: file name marks a secret or export")
    assert not hits, "Files that must stay out of the repository:\n" + "\n".join(hits)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", False),
        ("{{ vault_x }}", False),
        ("{{ lookup('ansible.builtin.env', 'X') }}", False),
        ("SYNTHETIC-fixture-password", False),
        ("<supplied-at-run-time>", False),
        ("/var/run/secrets/token", False),
        ("hunter2hunter2", True),
        ("changeme", True),
    ],
)
def test_literal_credential_heuristic(value: str, expected: bool) -> None:
    assert _literal_credential(value) is expected


def test_secret_key_detection_handles_camel_case_and_prefixes() -> None:
    for key in ("userPassword", "DATABASE_SECRET_KEY", "dev_hub_backend_secret", "aws_secret_access_key"):
        assert _is_secret_key(key), key
    assert _is_secret_key("bindCredential")
    assert not _is_secret_key("password_policy_enabled")


def test_scanners_flag_the_shapes_that_used_to_ship() -> None:
    """The guard itself must catch each shape of embedded credential."""
    # Jinja template key with a literal (Quay DATABASE_SECRET_KEY / dev hub backend secret).
    assert dict(_template_pairs("DATABASE_SECRET_KEY: hunter2hunter2\n")) == {"DATABASE_SECRET_KEY": "hunter2hunter2"}
    # Structured defaults file.
    found = [
        (key, value)
        for doc in _data_documents(Path("x.yml"), "---\nsome_admin_password: hunter2hunter2\n")
        for key, value, _trail in _walk_mapping(doc)
    ]
    assert found == [("some_admin_password", "hunter2hunter2")]
    # Credential embedded in a URL.
    assert URL_CREDENTIAL.search("postgresql://quay:hunter2hunter2@postgres-db:5432/quay")
    assert not URL_CREDENTIAL.search("postgresql://quay:{{ pw }}@postgres-db:5432/quay")
    # Token shapes.
    assert TOKEN_PATTERNS["gitlab-token"].search("glpat-" + "a" * 20)
    assert TOKEN_PATTERNS["private-key"].search("-----BEGIN PRIVATE KEY-----")
    # A reference is not a literal.
    assert not _literal_credential("{{ vault_ocp_quay_admin_password | default('') }}")
