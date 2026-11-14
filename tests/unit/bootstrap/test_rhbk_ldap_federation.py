# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for FreeIPA-aware RHBK LDAP federation config builder."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "roles/bootstrap_generate_env_vars/files/rhbk_ldap_federation.py"
SCRIPT = Path(
    os.environ.get("ADO_OVERLAY_SCRIPT_UNDER_TEST")
    or ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"
)


def _load_helper():
    spec = importlib.util.spec_from_file_location("rhbk_ldap_federation", HELPER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_freeipa_defaults_use_ipauniqueid_not_nsuniqueid():
    mod = _load_helper()
    cfg = mod.build_rhbk_ldap_config(
        public={
            "federation_provider": "freeipa",
            "federation_ldap_url": "ldap://idm.server.lab",
            "federation_bind_dn": "uid=bind,cn=users,cn=accounts,dc=server,dc=lab",
            "federation_users_dn": "cn=users,cn=accounts,dc=server,dc=lab",
        },
        secret={"federation_bind_password": "secret"},
    )
    assert cfg["uuidLDAPAttribute"] == "ipaUniqueID"
    assert cfg["searchScope"] == "2"
    assert "posixAccount" in cfg["userObjectClasses"]
    assert cfg["vendor"] == "rhds"
    assert cfg["connectionUrl"] == "ldap://idm.server.lab"
    assert cfg["bindDn"].startswith("uid=bind")


def test_cn_accounts_users_dn_selects_freeipa_even_when_vendor_rhds():
    mod = _load_helper()
    cfg = mod.build_rhbk_ldap_config(
        public={
            "federation_provider": "ldap",
            "federation_vendor": "rhds",
            "federation_ldap_url": "ldaps://idm.server.lab",
            "federation_bind_dn": "cn=Directory Manager",
            "federation_users_dn": "cn=users,cn=accounts,dc=example,dc=com",
        },
        secret={"federation_bind_password": "x"},
        existing={
            "uuidLDAPAttribute": "nsuniqueid",
            "searchScope": "1",
            "userObjectClasses": "inetOrgPerson",
        },
    )
    assert cfg["uuidLDAPAttribute"] == "ipaUniqueID"
    assert cfg["searchScope"] == "2"
    assert "posixAccount" in cfg["userObjectClasses"]
    assert cfg["vendor"] == "rhds"


def test_empty_form_strings_do_not_wipe_existing_ldap_config():
    mod = _load_helper()
    existing = {
        "connectionUrl": "ldap://idm.server.lab",
        "bindDn": "cn=Directory Manager",
        "usersDn": "cn=users,cn=accounts,dc=server,dc=lab",
        "bindCredential": "keep-me",
        "uuidLDAPAttribute": "ipaUniqueID",
    }
    cfg = mod.build_rhbk_ldap_config(
        public={
            "federation_provider": "freeipa",
            "federation_ldap_url": "",
            "federation_bind_dn": "",
            "federation_users_dn": "",
        },
        secret={"federation_bind_password": ""},
        existing=existing,
    )
    assert cfg["connectionUrl"] == "ldap://idm.server.lab"
    assert cfg["bindDn"] == "cn=Directory Manager"
    assert cfg["bindCredential"] == "keep-me"
    assert not mod.required_ldap_fields_missing(cfg)


def test_blank_existing_connection_url_cleared_and_filled_from_form():
    mod = _load_helper()
    cfg = mod.build_rhbk_ldap_config(
        public={
            "federation_provider": "freeipa",
            "federation_ldap_url": "ldap://idm.server.lab",
            "federation_bind_dn": "cn=Directory Manager",
            "federation_users_dn": "cn=users,cn=accounts,dc=server,dc=lab",
        },
        secret={"federation_bind_password": "pw"},
        existing={
            "connectionUrl": "",
            "bindDn": "",
            "bindCredential": "old-pw",
        },
    )
    assert cfg["connectionUrl"] == "ldap://idm.server.lab"
    assert cfg["bindDn"] == "cn=Directory Manager"
    assert cfg["bindCredential"] == "pw"


def test_group_mapper_defaults_from_users_dn():
    mod = _load_helper()
    groups = mod.freeipa_ldap_group_mapper_defaults(
        "cn=users,cn=accounts,dc=server,dc=lab"
    )
    assert groups["groups.dn"] == "cn=groups,cn=accounts,dc=server,dc=lab"
    assert groups["membership.ldap.attribute"] == "member"
    assert groups["membership.attribute.type"] == "DN"


def test_merge_ldap_config_into_vault_preserves_password_and_drops_blanks():
    mod = _load_helper()
    vault = {
        "ldap_config": {
            "connectionUrl": "",
            "bindDn": "cn=Directory Manager",
            "bindCredential": "vault-pw",
        }
    }
    changed = mod.merge_ldap_config_into_vault(
        vault,
        {
            "connectionUrl": "ldap://idm.server.lab",
            "usersDn": "cn=users,cn=accounts,dc=server,dc=lab",
            "bindCredential": "",
            "uuidLDAPAttribute": "ipaUniqueID",
        },
    )
    assert changed is True
    assert vault["ldap_config"]["connectionUrl"] == "ldap://idm.server.lab"
    assert vault["ldap_config"]["bindCredential"] == "vault-pw"
    assert "" not in vault["ldap_config"].values()


def _run_overlay(tmp_path: Path, rhbk_cfg: dict) -> dict:
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    # Seed a vault with blank URL to reproduce the wipe failure mode.
    (env_dir / "vault_rhbk.yml").write_text(
        yaml.safe_dump(
            {
                "ldap_config": {
                    "connectionUrl": "",
                    "bindDn": "",
                    "bindCredential": "seed-password",
                    "usersDn": "cn=users,cn=accounts,dc=server,dc=lab",
                }
            }
        ),
        encoding="utf-8",
    )
    (env_dir / "vars_rhbk.yml").write_text("{}\n", encoding="utf-8")
    preflight = {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": ["rhbk"]},
        "component_options": {"rhbk": ["federation"]},
        "openshift": {"apps_domain": "apps.example.test"},
        "component_config": {
            "rhbk": {
                "hostname": "keycloak.apps.example.test",
                "realm": "Dev",
                **rhbk_cfg,
            }
        },
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    env = {
        **os.environ,
        "ADO_PREFLIGHT_JSON": str(preflight_path),
        "ADO_ENV_DIR": str(env_dir),
        "ADO_SELECTED_COMPONENTS": '["rhbk"]',
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    vault = yaml.safe_load((env_dir / "vault_rhbk.yml").read_text(encoding="utf-8"))
    vars_data = yaml.safe_load((env_dir / "vars_rhbk.yml").read_text(encoding="utf-8"))
    return {"vault": vault, "vars": vars_data}


def test_overlay_builds_ldap_config_without_empty_wipe(tmp_path: Path):
    out = _run_overlay(
        tmp_path,
        {
            "federation_name": "LDAP",
            "federation_provider": "freeipa",
            "federation_ldap_url": "ldap://idm.server.lab",
            "federation_bind_dn": "cn=Directory Manager",
            "federation_users_dn": "cn=users,cn=accounts,dc=server,dc=lab",
            "federation_bind_password": "new-password",
        },
    )
    ldap = out["vault"]["ldap_config"]
    assert ldap["connectionUrl"] == "ldap://idm.server.lab"
    assert ldap["bindDn"] == "cn=Directory Manager"
    assert ldap["bindCredential"] == "new-password"
    assert ldap["uuidLDAPAttribute"] == "ipaUniqueID"
    assert ldap["searchScope"] == "2"
    public = out["vars"].get("ldap_config_public") or {}
    assert public.get("connectionUrl") == "ldap://idm.server.lab"
    assert "bindCredential" not in public
    groups = out["vars"].get("ldap_group_config") or {}
    assert groups.get("groups.dn") == "cn=groups,cn=accounts,dc=server,dc=lab"


def test_overlay_empty_form_keeps_seed_password_and_fills_url(tmp_path: Path):
    # Form left password blank; URL provided - must keep seed password, fill URL.
    out = _run_overlay(
        tmp_path,
        {
            "federation_name": "LDAP",
            "federation_provider": "freeipa",
            "federation_ldap_url": "ldap://idm.server.lab",
            "federation_bind_dn": "cn=Directory Manager",
            "federation_users_dn": "cn=users,cn=accounts,dc=server,dc=lab",
            "federation_bind_password": "",
        },
    )
    ldap = out["vault"]["ldap_config"]
    assert ldap["connectionUrl"] == "ldap://idm.server.lab"
    assert ldap["bindCredential"] == "seed-password"
