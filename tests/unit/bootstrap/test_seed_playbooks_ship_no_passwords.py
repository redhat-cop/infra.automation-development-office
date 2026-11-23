"""Seed playbooks and the vault template must not ship a working password.

A secret-named play variable is either empty or a Jinja reference to Vault. An
operator who forgets to set the Vault value gets a clear failure, never a default
credential that works on someone's lab.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SEEDS = ROOT / "roles/bootstrap_generate_playbook_repo/files"
VAULT_TEMPLATE = ROOT / "roles/bootstrap_generate_env_vars/templates/component_vault.yml.j2"

SECRET_KEY = re.compile(r"(password|passwd|secret|token|credential|bind_pw|api_key)$", re.I)
# Values that carry no secret: flags, sizes, file paths, names of other variables.
NOT_A_SECRET = re.compile(r"^(true|false|yes|no|none|null|always|on_create|\d+|\[\]|\{\})$", re.I)
# Documented role-default placeholder (ocp_dev_hub defaults, README). Tracked as an open item,
# not part of the VPN/LDAP clean-up. Remove this entry when the role generates the value.
KNOWN_PLACEHOLDERS: set[str] = set()


def literal_secrets(node, trail=""):
    """Yield (path, value) for secret-named keys holding a non-empty literal."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else str(key)
            if isinstance(value, str) and SECRET_KEY.search(str(key)):
                text = value.strip()
                if text and "{{" not in text and "{%" not in text and not NOT_A_SECRET.match(text):
                    yield here, text
            else:
                yield from literal_secrets(value, here)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from literal_secrets(item, f"{trail}[{index}]")


def seed_playbooks():
    return sorted(
        path for path in SEEDS.rglob("*.yml")
        if "playbooks" in path.relative_to(SEEDS).parts
    )


@pytest.mark.parametrize("path", seed_playbooks(), ids=lambda p: str(p.relative_to(SEEDS)))
def test_seed_playbook_defines_no_literal_secret(path):
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except yaml.YAMLError:
        pytest.skip("template, not plain YAML")
    found = []
    for document in documents:
        for play in document if isinstance(document, list) else [document]:
            if isinstance(play, dict):
                found += [name for name, _value in literal_secrets(play.get("vars") or {})]
    assert found == [], f"{path.relative_to(ROOT)} ships literal secret values for: {found}"


def test_vault_template_defines_no_literal_secret():
    offenders = []
    for number, line in enumerate(VAULT_TEMPLATE.read_text(encoding="utf-8").splitlines(), 1):
        match = re.match(r"\s*([A-Za-z0-9_.-]*(?:password|passwd|secret|credential|token)[A-Za-z0-9_.-]*)\s*:\s*(.+?)\s*$", line, re.I)
        if not match or match.group(2).startswith("#") or match.group(1) in KNOWN_PLACEHOLDERS:
            continue
        value = match.group(2).strip("'\"")
        if value and "{{" not in value and "{%" not in value and not NOT_A_SECRET.match(value):
            offenders.append(f"line {number}: {match.group(1)}")
    assert offenders == [], offenders


def test_scanner_flags_literals_and_accepts_references():
    sample = {
        "vpn_access_default_password": "not-a-real-one",
        "ldap_bind_password": "{{ vault_ldap_bind_password | default('') }}",
        "smtp_password": "",
        "nested": {"api_token": "abc123", "enabled": "true"},
    }
    assert [name for name, _value in literal_secrets(sample)] == ["vpn_access_default_password", "nested.api_token"]
