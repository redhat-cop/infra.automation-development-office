"""OpenShift OIDC with and without RHBK in the run.

Runs the real ``overlay_preflight_component_values.py`` and
``preflight_oidc.py`` against a throwaway env dir. Covers:

* RHBK selected: Keycloak host / realm / credentials are inherited, and leftover
  ``openshift.oauth_rhbk`` connection overrides are ignored;
* external Keycloak only: ``openshift.oauth_rhbk`` supplies everything the
  existing ``ocp_oidc_auth`` role reads, and no Keycloak client is created;
* explicit client precedence, missing or conflicting inputs, dismissed clients,
  several OIDC consumers, idempotent reruns and secret handling.
"""

from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
FILES = Path(
    os.environ.get("ADO_OIDC_FILES_UNDER_TEST") or ROOT / "roles/bootstrap_generate_env_vars/files"
)
OVERLAY = FILES / "overlay_preflight_component_values.py"
VALIDATOR = FILES / "preflight_oidc.py"

RHBK_PASSWORD = "rhbk-admin-pass-9f2"
EXTERNAL_PASSWORD = "external-kc-pass-7c1"
OTHER_PASSWORD = "other-kc-pass-3d8"

GRAFANA = {
    "id": "grafana-client",
    "name": "Grafana",
    "redirect_uris": "https://grafana.apps.example.test/*",
    "web_origins": "https://grafana.apps.example.test",
}
OPENSHIFT = {
    "id": "OpenshiftDev",
    "name": "OpenShift",
    "redirect_uris": "https://oauth.apps.example.test/*",
    "web_origins": "https://oauth.apps.example.test",
}


def rhbk_form(**extra):
    return {
        "hostname": "keycloak.apps.example.test",
        "realm": "demo",
        "admin_user": "admin",
        "admin_password": RHBK_PASSWORD,
        "clients": [copy.deepcopy(GRAFANA), copy.deepcopy(OPENSHIFT)],
        **extra,
    }


def external_oauth(**extra):
    return {
        "idp_name": "Corp-SSO",
        "keycloak_hostname": "sso.corp.example.test",
        "realm": "corp",
        "client_id": "corp-openshift",
        "admin_user": "kcadmin",
        "admin_password": EXTERNAL_PASSWORD,
        **extra,
    }


def make_preflight(*, rhbk=None, oauth=None, options=None, apps=None, config=None):
    """RHBK selected when ``rhbk`` is given as the form dict, external otherwise."""
    component_config = dict(config or {})
    if rhbk is not None:
        component_config["rhbk"] = rhbk
    return {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {
            "openshift": ["rhbk"] if (rhbk is not None and apps is None) else (apps or [])
        },
        "component_options": {
            "openshift": ["oauth_rhbk"],
            "rhbk": ["client"],
            **(options or {}),
        },
        "openshift": {"apps_domain": "apps.example.test", "oauth_rhbk": oauth or {}},
        "component_config": component_config,
    }


def run(tmp_path, preflight, selected, *, script=OVERLAY, env_name="env", rerun=False):
    env_dir = tmp_path / env_name
    env_dir.mkdir(exist_ok=True)
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        env={
            **os.environ,
            "ADO_PREFLIGHT_JSON": str(preflight_path),
            "ADO_ENV_DIR": str(env_dir),
            "ADO_SELECTED_COMPONENTS": json.dumps(selected),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, env_dir


def load(env_dir, name):
    path = env_dir / name
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def tree_text(env_dir):
    return {
        str(p.relative_to(env_dir)): p.read_text(encoding="utf-8")
        for p in sorted(env_dir.rglob("*"))
        if p.is_file()
    }


# 1. OpenShift OIDC with RHBK selected ---------------------------------------


def test_rhbk_selected_inherits_host_realm_and_credentials(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(rhbk=rhbk_form(), oauth={"client_id": "OpenshiftDev"}),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    oidc = data["openshift_oidc_auth"]
    assert oidc["keycloak_client_id"] == "OpenshiftDev"
    assert oidc["issuer"] == "https://keycloak.apps.example.test/realms/demo"
    assert oidc["openshift_oidc_idp_name"] == "Keycloak"
    assert oidc["openshift_oidc_mapping_method"] == "add"
    # Nothing OpenShift-specific is written for inherited values: the role falls
    # back to RHBK's own rhbk_hostname / rhbk_realm / rhbk_admin_*.
    for key in (
        "ocp_oidc_auth_rhbk_hostname",
        "ocp_oidc_auth_rhbk_realm",
        "ocp_oidc_auth_rhbk_admin_user",
        "ocp_oidc_auth_rhbk_admin_password",
    ):
        assert key not in data
    assert data["rhbk_hostname"] == "keycloak.apps.example.test"
    assert data["rhbk_realm"] == "demo"
    vault = load(env_dir, "vault_rhbk.yml")
    assert vault["vault_rhbk_admin_password"] == RHBK_PASSWORD
    assert "vault_ocp_oidc_auth_rhbk_admin_password" not in vault


def test_rhbk_admin_user_is_not_overridden_by_the_vault_default(tmp_path):
    """vault_rhbk.yml loads after vars_rhbk.yml, so both must carry the form's user."""
    # component_vault.yml.j2 writes this before the overlay runs.
    seeded = tmp_path / "env"
    seeded.mkdir()
    (seeded / "vault_rhbk.yml").write_text(
        "---\nrhbk_admin_user: admin\nrhbk_admin_password: redhat123\n"
        "ocp_rhbk_admin_user: admin\nocp_rhbk_admin_password: redhat123\n",
        encoding="utf-8",
    )
    result, env_dir = run(
        tmp_path,
        make_preflight(rhbk=rhbk_form(admin_user="kcroot"), oauth={"client_id": "OpenshiftDev"}),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    # Ansible loads group_vars files alphabetically; vault_ wins over vars_.
    effective = {}
    for name in ("vars_rhbk.yml", "vault_rhbk.yml"):
        effective.update(
            {k: v for k, v in load(env_dir, name).items() if not isinstance(v, (dict, list))}
        )
    assert effective["rhbk_admin_user"] == "kcroot"
    assert effective["ocp_rhbk_admin_user"] == "kcroot"
    assert effective["vault_rhbk_admin_password"] == RHBK_PASSWORD


def test_rhbk_selected_leftover_openshift_connection_overrides_are_ignored(tmp_path):
    oauth = {
        "client_id": "OpenshiftDev",
        "keycloak_hostname": "kc2.example.test",
        "realm": "other",
        "mapping_method": "lookup",
        "extra_scopes": "groups, roles",
        "idp_name": "KC2",
        "admin_user": "otheradmin",
        "admin_password": OTHER_PASSWORD,
        "verify_ssl": True,
    }
    result, env_dir = run(
        tmp_path, make_preflight(rhbk=rhbk_form(), oauth=oauth), ["rhbk", "openshift"]
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    for key in (
        "ocp_oidc_auth_rhbk_hostname",
        "ocp_oidc_auth_rhbk_realm",
        "ocp_oidc_auth_rhbk_admin_user",
        "ocp_oidc_auth_rhbk_admin_password",
    ):
        assert key not in data
    assert data["ocp_rhbk_verify_ssl"] is True
    oidc = data["openshift_oidc_auth"]
    assert oidc["issuer"] == "https://keycloak.apps.example.test/realms/demo"
    assert oidc["openshift_oidc_mapping_method"] == "lookup"
    assert oidc["extra_scopes"] == ["groups", "roles"]
    assert oidc["openshift_oidc_idp_name"] == "KC2"
    assert data["components_env"]["rhbk"]["openshift_oidc_auth"] == oidc
    # RHBK's own settings and credentials are not rewritten by the OpenShift section.
    assert data["rhbk_hostname"] == "keycloak.apps.example.test"
    assert data["rhbk_realm"] == "demo"
    vault = load(env_dir, "vault_rhbk.yml")
    assert vault["vault_rhbk_admin_password"] == RHBK_PASSWORD
    assert "vault_ocp_oidc_auth_rhbk_admin_password" not in vault


def test_rhbk_selected_does_not_create_or_change_keycloak_clients(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(clients=[copy.deepcopy(GRAFANA)], client=GRAFANA["id"]),
            oauth={"client_id": "ExistingExternalClient"},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert set(data["rhbk_clients"]) == {GRAFANA["id"]}
    assert data["rhbk_client"] == GRAFANA["id"]
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "ExistingExternalClient"


# 2. External Keycloak only ------------------------------------------------


def test_external_keycloak_generates_what_the_existing_role_reads(tmp_path):
    result, env_dir = run(tmp_path, make_preflight(oauth=external_oauth()), ["openshift"])
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["ocp_oidc_auth_rhbk_hostname"] == "sso.corp.example.test"
    assert data["ocp_oidc_auth_rhbk_realm"] == "corp"
    assert data["ocp_oidc_auth_rhbk_admin_user"] == "kcadmin"
    assert data["ocp_oidc_auth_rhbk_admin_password"] == (
        "{{ vault_ocp_oidc_auth_rhbk_admin_password }}"
    )
    assert "ocp_rhbk_verify_ssl" not in data  # absent: the role verifies by default
    assert data["openshift_oidc_client_id"] == "corp-openshift"
    assert data["openshift_oidc_idp_name"] == "Corp-SSO"
    assert data["openshift_oidc_auth"] == {
        "enabled": True,
        "openshift_oidc_idp_name": "Corp-SSO",
        "keycloak_client_id": "corp-openshift",
        "openshift_oidc_mapping_method": "add",
        "openshift_oauth_resource_name": "cluster",
        "extra_scopes": ["groups"],
        "issuer": "https://sso.corp.example.test/realms/corp",
        "openshift_oauth_redirect_uri": (
            "https://oauth-openshift.apps.example.test/oauth2callback/Corp-SSO"
        ),
    }
    vault = load(env_dir, "vault_rhbk.yml")
    assert vault == {"vault_ocp_oidc_auth_rhbk_admin_password": EXTERNAL_PASSWORD}
    assert stat.S_IMODE((env_dir / "vault_rhbk.yml").stat().st_mode) == 0o600


def test_external_keycloak_never_creates_a_keycloak_client(tmp_path):
    result, env_dir = run(tmp_path, make_preflight(oauth=external_oauth()), ["openshift"])
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    for key in ("rhbk_client", "rhbk_clients", "clients", "client", "install_rhbk_platform"):
        assert key not in data


def test_external_keycloak_ignores_a_deselected_rhbk_form(tmp_path):
    """A leftover RHBK form (component deselected) must not leak into OpenShift OIDC."""
    leftover = rhbk_form(hostname="keycloak.stale.example.test", realm="stale")
    result, env_dir = run(
        tmp_path,
        make_preflight(oauth=external_oauth(), config={"rhbk": leftover}, apps=[]),
        ["openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["ocp_oidc_auth_rhbk_hostname"] == "sso.corp.example.test"
    assert "stale" not in json.dumps(data)


# 3. Explicit OpenShift client ID precedence ----------------------------------


@pytest.mark.parametrize(
    ("oauth_id", "rhbk_id", "expected"),
    [
        ("FromOauth", "FromRhbk", "FromOauth"),
        ("", "FromRhbk", "FromRhbk"),
        ("", "", "OpenshiftDev"),
    ],
)
def test_client_id_precedence(tmp_path, oauth_id, rhbk_id, expected):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(openshift_oidc_client_id=rhbk_id),
            oauth={"client_id": oauth_id},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml")["openshift_oidc_auth"]["keycloak_client_id"] == expected


# 4. Missing host, realm, client ID or credential -----------------------------


@pytest.mark.parametrize(
    ("missing", "fragment"),
    [
        ("keycloak_hostname", "set the Keycloak hostname"),
        ("realm", "set the Keycloak realm"),
        ("client_id", "externally managed Keycloak client but no client ID"),
        ("admin_user", "set the Keycloak admin user"),
        ("admin_password", "set the Keycloak admin password"),
    ],
)
def test_external_mode_requires_every_input(tmp_path, missing, fragment):
    oauth = external_oauth()
    oauth[missing] = ""
    result, env_dir = run(tmp_path, make_preflight(oauth=oauth), ["openshift"])
    assert result.returncode != 0
    assert fragment in result.stderr
    # Fails before anything is generated.
    assert tree_text(env_dir) == {}


def test_rhbk_mode_requires_an_admin_password_from_somewhere(tmp_path):
    result, _unused = run(
        tmp_path,
        make_preflight(rhbk=rhbk_form(admin_password=""), oauth={"client_id": "OpenshiftDev"}),
        ["rhbk", "openshift"],
    )
    assert result.returncode != 0
    assert "no Keycloak admin password" in result.stderr


def test_explicit_claim_mapping_method_is_kept(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev", "mapping_method": "claim"},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml")["openshift_oidc_auth"][
        "openshift_oidc_mapping_method"
    ] == "claim"


def test_leftover_oauth_hostname_does_not_replace_the_rhbk_host(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev", "keycloak_hostname": "kc2.example.test"},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["openshift_oidc_auth"]["issuer"] == (
        "https://keycloak.apps.example.test/realms/demo"
    )
    assert "ocp_oidc_auth_rhbk_hostname" not in data


def test_client_and_oauth_jobs_share_rhbk_target_when_json_has_two_hosts(tmp_path):
    """RHBK Client vars and OpenShift OAuth issuer must resolve to the same Keycloak."""
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(
                hostname="keycloak.apps.ocp-dev.example.test",
                realm="rhlab",
            ),
            oauth={
                "client_id": "OpenshiftDev",
                "keycloak_hostname": "keycloak.apps.ocp.prod.example.test",
                "realm": "other",
                "admin_user": "otheradmin",
                "admin_password": OTHER_PASSWORD,
            },
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    expected_host = "keycloak.apps.ocp-dev.example.test"
    expected_realm = "rhlab"
    assert data["rhbk_hostname"] == expected_host
    assert data["rhbk_realm"] == expected_realm
    assert data["ocp_rhbk_hostname"] == expected_host
    assert data["ocp_rhbk_realm"] == expected_realm
    assert data["openshift_oidc_auth"]["issuer"] == (
        f"https://{expected_host}/realms/{expected_realm}"
    )
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"
    for leftover in (
        "ocp_oidc_auth_rhbk_hostname",
        "ocp_oidc_auth_rhbk_realm",
        "ocp_oidc_auth_rhbk_admin_user",
    ):
        assert leftover not in data


def test_blank_rhbk_realm_fails_for_client_only_before_generation(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(realm=""),
            oauth={
                "client_id": "OpenshiftDev",
                "keycloak_hostname": "keycloak.apps.ocp.prod.example.test",
                "realm": "rhlab",
            },
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode != 0
    assert "existing realm name" in result.stderr
    assert tree_text(env_dir) == {}


def test_leftover_oauth_hostname_url_is_ignored_when_rhbk_is_selected(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={
                "client_id": "OpenshiftDev",
                "keycloak_hostname": "https://Keycloak.apps.example.test/auth",
            },
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["openshift_oidc_auth"]["issuer"] == (
        "https://keycloak.apps.example.test/realms/demo"
    )


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"mapping_method": "bogus"}, 'mapping method "bogus"'),
        ({"keycloak_hostname": "sso corp"}, "is not a valid host"),
        (
            {"keycloak_hostname": "https://sso.corp.example.test/"},
            "http:// or https://",
        ),
        (
            {"keycloak_hostname": "HTTP://sso.corp.example.test"},
            "http:// or https://",
        ),
        (
            {"keycloak_hostname": "sso.corp.example.test/"},
            "trailing /",
        ),
    ],
)
def test_invalid_openshift_oidc_inputs_are_rejected(tmp_path, override, fragment):
    result, _unused = run(tmp_path, make_preflight(oauth=external_oauth(**override)), ["openshift"])
    assert result.returncode != 0
    assert fragment in result.stderr


def test_oidc_not_requested_needs_none_of_it(tmp_path):
    preflight = make_preflight(rhbk=rhbk_form(), oauth={})
    preflight["component_options"]["openshift"] = []
    result, env_dir = run(tmp_path, preflight, ["rhbk", "openshift"])
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert not [key for key in data if key.startswith("ocp_oidc_auth_rhbk_")]
    assert "ocp_rhbk_verify_ssl" not in data
    assert "vault_ocp_oidc_auth_rhbk_admin_password" not in load(env_dir, "vault_rhbk.yml")


# 5. Several OIDC consumers (Grafana and OpenShift) ---------------------------


def test_grafana_and_openshift_keep_their_own_clients(tmp_path):
    grafana = {"oidc": {"enabled": True, "client_id": "grafana-client"}}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"
    assert set(data["rhbk_clients"]) == {"grafana-client", "OpenshiftDev"}


def test_mixed_ownership_provisions_grafana_only_and_keeps_openshift_oidc(tmp_path):
    """ADO manages Grafana; OpenShift uses an existing client in the same realm."""
    grafana = {"oidc": {"enabled": True, "client_id": "grafana-client"}}
    rhbk = rhbk_form(
        client="OpenshiftDev",
        clients=[
            {**copy.deepcopy(OPENSHIFT), "create_client": False, "source": "openshift"},
            {**copy.deepcopy(GRAFANA), "create_client": True, "source": "grafana"},
        ],
    )
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk,
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    grafana_vars = load(env_dir, "vars_grafana.yml")
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert "OpenshiftDev" not in rhbk_vars["rhbk_clients"]
    assert rhbk_vars["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"
    assert grafana_vars["oidc"]["client_id"] == "grafana-client"
    assert grafana_vars["oidc"]["enabled"] is True
    assert grafana_vars["oidc"]["issuer"] == "https://keycloak.apps.example.test/realms/demo"


def test_grafana_oidc_issuer_ignores_leftover_when_rhbk_is_selected(tmp_path):
    grafana = {
        "oidc": {
            "enabled": True,
            "client_id": "grafana-client",
            "issuer": "https://kc2.example.test/realms/other",
        }
    }
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    grafana_vars = load(env_dir, "vars_grafana.yml")
    assert grafana_vars["oidc"]["issuer"] == "https://keycloak.apps.example.test/realms/demo"
    assert "issuer_manual" not in grafana_vars["oidc"]


def test_grafana_oidc_manual_issuer_is_kept(tmp_path):
    grafana = {
        "oidc": {
            "enabled": True,
            "client_id": "grafana-client",
            "issuer": "https://kc2.example.test/realms/other",
            "issuer_manual": True,
        }
    }
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    grafana_vars = load(env_dir, "vars_grafana.yml")
    assert grafana_vars["oidc"]["issuer"] == "https://kc2.example.test/realms/other"


def test_grafana_oidc_blank_rhbk_realm_fails_and_does_not_invent(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(realm=""),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}}},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode != 0
    assert "Grafana OIDC: no Keycloak realm" in result.stderr
    assert "rhlab" not in result.stderr.lower()
    assert tree_text(env_dir) == {}


def test_unmanaged_openshift_client_still_configures_oauth(tmp_path):
    rhbk = rhbk_form(
        clients=[{**copy.deepcopy(OPENSHIFT), "create_client": False, "source": "openshift"}],
        client="OpenshiftDev",
    )
    result, env_dir = run(
        tmp_path,
        make_preflight(rhbk=rhbk, oauth={"client_id": "OpenshiftDev"}),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert "rhbk_clients" not in data
    assert data.get("rhbk_client") != "OpenshiftDev"
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"


# 6. Removed / dismissed clients -----------------------------------------


def test_active_integration_pointing_at_removed_client_blocks_generation(tmp_path):
    grafana = {"oidc": {"enabled": True, "client_id": "grafana-client"}}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(
                clients=[copy.deepcopy(OPENSHIFT)],
                clients_dismissed=["grafana-client"],
            ),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode != 0
    assert 'Grafana OIDC still uses Keycloak client "grafana-client"' in result.stderr
    assert tree_text(env_dir) == {}


def test_removed_client_is_fine_when_the_integration_is_disabled(tmp_path):
    grafana = {"oidc": {"enabled": False, "client_id": "grafana-client"}}
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(
                clients=[copy.deepcopy(OPENSHIFT)],
                clients_dismissed=["grafana-client"],
            ),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr


def test_removed_openshift_client_blocks_when_rhbk_manages_clients(tmp_path):
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(clients=[copy.deepcopy(GRAFANA)], clients_dismissed=["OpenshiftDev"]),
            oauth={"client_id": "OpenshiftDev"},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode != 0
    assert 'OpenShift OIDC still uses Keycloak client "OpenshiftDev"' in result.stderr


def test_dismissed_name_does_not_block_an_external_client(tmp_path):
    """No RHBK in this run: the client list is not consulted."""
    result, _unused = run(
        tmp_path,
        make_preflight(
            oauth=external_oauth(client_id="OpenshiftDev"),
            config={"rhbk": rhbk_form(clients_dismissed=["OpenshiftDev"])},
            apps=[],
        ),
        ["openshift"],
    )
    assert result.returncode == 0, result.stderr


def test_client_managed_elsewhere_flag_skips_the_client_list(tmp_path):
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(clients=[], clients_dismissed=["OpenshiftDev"]),
            oauth={"client_id": "OpenshiftDev", "fetch_client_secret": False},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr


def test_integrations_that_are_not_selected_are_not_checked(tmp_path):
    grafana = {"oidc": {"enabled": True, "client_id": "gone"}}
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(clients_dismissed=["gone"]),
            oauth={"client_id": "OpenshiftDev"},
            options={"grafana": ["oidc"]},
            config={"grafana": grafana},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr


# 7. JSON export / import and reruns ------------------------------------------


def test_json_round_trip_and_rerun_generate_identical_files(tmp_path):
    preflight = make_preflight(oauth=external_oauth(verify_ssl=True))
    imported = json.loads(json.dumps(preflight))
    first, env_dir = run(tmp_path, preflight, ["openshift"])
    assert first.returncode == 0, first.stderr
    before = tree_text(env_dir)
    second, _unused = run(tmp_path, imported, ["openshift"])
    assert second.returncode == 0, second.stderr
    assert tree_text(env_dir) == before
    assert load(env_dir, "vars_rhbk.yml")["ocp_rhbk_verify_ssl"] is True


def test_leftover_openshift_connection_overrides_are_ignored_on_first_run(tmp_path):
    oauth = {
        "client_id": "OpenshiftDev",
        "keycloak_hostname": "kc2.example.test",
        "realm": "other",
        "admin_user": "otheradmin",
        "admin_password": OTHER_PASSWORD,
    }
    result, env_dir = run(
        tmp_path, make_preflight(rhbk=rhbk_form(), oauth=oauth), ["rhbk", "openshift"]
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert "ocp_oidc_auth_rhbk_hostname" not in data
    assert data["openshift_oidc_auth"]["issuer"] == (
        "https://keycloak.apps.example.test/realms/demo"
    )
    result, _unused = run(
        tmp_path,
        make_preflight(rhbk=rhbk_form(), oauth={"client_id": "OpenshiftDev"}),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert not [key for key in data if key.startswith("ocp_oidc_auth_rhbk_")]
    assert "vault_ocp_oidc_auth_rhbk_admin_password" not in load(env_dir, "vault_rhbk.yml")
    assert data["openshift_oidc_auth"]["issuer"] == (
        "https://keycloak.apps.example.test/realms/demo"
    )


# 9. No plaintext secret leakage -----------------------------------------


@pytest.mark.parametrize("mode", ["external", "rhbk"])
def test_admin_password_only_ever_lands_in_the_vault_file(tmp_path, mode):
    if mode == "external":
        preflight = make_preflight(oauth=external_oauth())
        selected = ["openshift"]
        password = EXTERNAL_PASSWORD
    else:
        preflight = make_preflight(
            rhbk=rhbk_form(),
            oauth={
                "client_id": "OpenshiftDev",
                "keycloak_hostname": "kc2.example.test",
                "admin_user": "otheradmin",
                "admin_password": OTHER_PASSWORD,
            },
        )
        selected = ["rhbk", "openshift"]
        password = RHBK_PASSWORD
    result, env_dir = run(tmp_path, preflight, selected)
    assert result.returncode == 0, result.stderr
    assert password not in result.stdout + result.stderr
    holders = [name for name, body in tree_text(env_dir).items() if password in body]
    assert holders == ["vault_rhbk.yml"]
    assert stat.S_IMODE((env_dir / "vault_rhbk.yml").stat().st_mode) == 0o600


def test_validation_errors_never_echo_secrets(tmp_path):
    oauth = external_oauth(realm="")
    result, _unused = run(tmp_path, make_preflight(oauth=oauth), ["openshift"])
    assert result.returncode != 0
    assert EXTERNAL_PASSWORD not in result.stdout + result.stderr


# Shared validator, run before any vars are generated -----------------------


def test_standalone_validator_matches_the_overlay(tmp_path):
    bad = make_preflight(oauth=external_oauth(client_id=""))
    result, env_dir = run(tmp_path, bad, ["openshift"], script=VALIDATOR)
    assert result.returncode != 0
    assert "nothing was generated" in result.stderr
    assert "externally managed Keycloak client but no client ID" in result.stderr
    assert tree_text(env_dir) == {}

    good = make_preflight(oauth=external_oauth())
    result, env_dir = run(tmp_path, good, ["openshift"], script=VALIDATOR)
    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout
    assert tree_text(env_dir) == {}


def test_validator_flags_bypassed_ui_guard_for_other_components(tmp_path):
    """A hand-edited JSON that skips the form is caught like the form would."""
    bookstack = {"oidc_enabled": True, "oidc_client_id": "bookstack-gone"}
    preflight = make_preflight(
        rhbk=rhbk_form(clients_dismissed=["bookstack-gone"]),
        oauth={"client_id": "OpenshiftDev"},
        apps=["rhbk", "bookstack"],
        config={"bookstack": bookstack},
    )
    result, _unused = run(tmp_path, preflight, ["rhbk", "openshift", "bookstack"], script=VALIDATOR)
    assert result.returncode != 0
    assert 'BookStack OIDC still uses Keycloak client "bookstack-gone"' in result.stderr


def test_blank_client_id_means_the_framework_default_client(tmp_path):
    """Quay with OIDC on and no client ID uses the default ``quay`` client."""
    quay = {"oidc_enabled": True}
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "quay"],
            options={"quay": ["oidc"]},
            config={"quay": quay},
        ),
        ["rhbk", "openshift", "quay"],
    )
    assert result.returncode == 0, result.stderr


def test_blank_client_id_is_blocked_when_the_default_client_was_removed(tmp_path):
    quay = {"oidc_enabled": True}
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(clients_dismissed=["quay"]),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "quay"],
            options={"quay": ["oidc"]},
            config={"quay": quay},
        ),
        ["rhbk", "openshift", "quay"],
        script=VALIDATOR,
    )
    assert result.returncode != 0
    assert 'Quay OIDC still uses Keycloak client "quay"' in result.stderr


def _defaults_module():
    sys.path.insert(0, str(FILES))
    try:
        import preflight_oidc

        return preflight_oidc
    finally:
        sys.path.remove(str(FILES))


DEFAULTED = ["grafana", "bookstack", "netbox", "quay", "minio", "dev_hub"]
DEFAULT_OPTIONS = {c: ["oidc"] for c in DEFAULTED}
DEFAULT_ENABLED = {
    "grafana": {"oidc": {"enabled": True}},
    "bookstack": {"oidc_enabled": True},
    "netbox": {"oidc_enabled": True},
    "quay": {"oidc_enabled": True},
    "minio": {"oidc_enabled": True},
    "dev_hub": {},
}


def _blank_default_run(tmp_path, component, rhbk):
    return run(
        tmp_path,
        make_preflight(
            rhbk=rhbk,
            oauth=external_oauth() if rhbk is None else {"client_id": "OpenshiftDev"},
            apps=["rhbk", component] if rhbk is not None else [component],
            options={component: ["oidc"]},
            config={component: DEFAULT_ENABLED[component]},
        ),
        ["rhbk", "openshift", component] if rhbk is not None else ["openshift", component],
        script=VALIDATOR,
    )


def test_default_client_ids_are_read_from_components_defaults_yml():
    module = _defaults_module()
    found = module.load_default_client_ids()
    assert sorted(found) == sorted(DEFAULTED)
    defaults = yaml.safe_load(module.components_defaults_path().read_text(encoding="utf-8"))
    table = defaults["components_defaults"]
    assert found["grafana"] == table["grafana"]["oidc"]["client_id"]
    assert found["quay"] == table["quay"]["quay_oidc_client_id"]
    assert found["dev_hub"] == table["dev_hub"]["dev_hub_keycloak_client_id"]
    for name in ("bookstack", "netbox", "minio"):
        assert found[name] == table[name][f"{name}_oidc_client_id"]


def test_changing_the_defaults_file_changes_the_resolved_client(tmp_path, monkeypatch):
    """No second mapping: the validator follows components_defaults.yml."""
    module = _defaults_module()
    changed = tmp_path / "components_defaults.yml"
    changed.write_text(
        module.components_defaults_path()
        .read_text(encoding="utf-8")
        .replace("quay_oidc_client_id: quay\n", "quay_oidc_client_id: quay-renamed\n"),
        encoding="utf-8",
    )
    monkeypatch.setenv("ADO_COMPONENTS_DEFAULTS", str(changed))
    # the old default is no longer referenced when blank; the new one is
    result, _unused = _blank_default_run(tmp_path, "quay", rhbk_form(clients_dismissed=["quay"]))
    assert result.returncode == 0, result.stderr
    result, _unused = _blank_default_run(tmp_path, "quay", rhbk_form(clients_dismissed=["quay-renamed"]))
    assert result.returncode != 0
    assert 'Quay OIDC still uses Keycloak client "quay-renamed"' in result.stderr


@pytest.mark.parametrize("component", DEFAULTED)
def test_blank_client_id_resolves_the_default_for_every_defaulted_component(tmp_path, component):
    result, _unused = _blank_default_run(tmp_path, component, rhbk_form())
    assert result.returncode == 0, result.stderr
    # external Keycloak (no RHBK in this run) accepts it too
    result, _unused = _blank_default_run(tmp_path, component, None)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("component", DEFAULTED)
def test_removed_default_client_is_not_silently_referenced(tmp_path, component):
    default = _defaults_module().load_default_client_ids()[component]
    removed = rhbk_form(clients=[copy.deepcopy(OPENSHIFT)], clients_dismissed=[default])
    result, _unused = _blank_default_run(tmp_path, component, removed)
    assert result.returncode != 0
    assert f'still uses Keycloak client "{default}"' in result.stderr
    # operator put it back: valid again
    restored = rhbk_form(
        clients_dismissed=[default],
        clients=[
            copy.deepcopy(OPENSHIFT),
            {"id": default, "name": default, "redirect_uris": "", "web_origins": ""},
        ],
    )
    result, _unused = _blank_default_run(tmp_path, component, restored)
    assert result.returncode == 0, result.stderr


def test_gitlab_has_no_default_client_and_needs_an_explicit_one(tmp_path):
    result, _unused = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(),
            oauth={"client_id": "OpenshiftDev"},
            apps=["rhbk", "gitlab"],
            options={"gitlab": ["oidc"]},
            config={"gitlab": {"oidc_enabled": True}},
        ),
        ["rhbk", "openshift", "gitlab"],
        script=VALIDATOR,
    )
    assert result.returncode != 0
    assert "GitLab OIDC is enabled but has no Keycloak client" in result.stderr


def test_openshift_never_gets_a_default_client(tmp_path):
    assert "openshift" not in _defaults_module().load_default_client_ids()
    result, _unused = run(
        tmp_path,
        make_preflight(rhbk=rhbk_form(clients=[copy.deepcopy(GRAFANA)])),
        ["rhbk", "openshift"],
        script=VALIDATOR,
    )
    assert result.returncode != 0
    assert "OpenShift OIDC" in result.stderr


def test_preflight_ui_generated_defaults_match_components_defaults():
    """The form resolves blank IDs from a file generated from the same source."""
    generated = ROOT.parent / "ado-preflight-ui" / "src" / "oidcClientDefaults.generated.mjs"
    if not generated.is_file():
        pytest.skip("ado-preflight-ui checkout not present")
    import re

    ui = dict(re.findall(r'^\s+(\w+): "([^"]+)"', generated.read_text(encoding="utf-8"), re.M))
    assert ui == _defaults_module().load_default_client_ids()


# 8. Keycloak TLS verification defaults to ON ----------------------------------
#
# The role (``ocp_oidc_auth``) verifies the Keycloak certificate unless
# ``ocp_rhbk_verify_ssl`` is explicitly false. Generation therefore writes that
# variable only when the preflight sets it, and never clears one that is
# already there (existing bootstrap configurations keep working).


def _validator_settings(preflight, selected):
    sys.path.insert(0, str(FILES))
    try:
        import importlib

        module = importlib.import_module("preflight_oidc")
        module = importlib.reload(module)
        return module.resolve_openshift_oauth_settings(preflight, selected)
    finally:
        sys.path.remove(str(FILES))


MODE_A = (
    lambda **kw: make_preflight(rhbk=rhbk_form(), oauth={"client_id": "OpenshiftDev", **kw}),
    ["rhbk", "openshift"],
)
MODE_B = (lambda **kw: make_preflight(oauth=external_oauth(**kw)), ["openshift"])


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
def test_tls_verification_is_on_by_default(tmp_path, mode):
    build, selected = mode
    preflight = build()
    result, env_dir = run(tmp_path, preflight, selected)
    assert result.returncode == 0, result.stderr
    # Not written: the role default (verify) applies. Nothing disables it.
    assert "ocp_rhbk_verify_ssl" not in load(env_dir, "vars_rhbk.yml")
    assert _validator_settings(preflight, selected)["verifySsl"] is True


@pytest.mark.parametrize("blank", ["", None], ids=["blank", "null"])
@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
def test_blank_verify_ssl_means_verify(tmp_path, mode, blank):
    build, selected = mode
    preflight = build(verify_ssl=blank)
    result, env_dir = run(tmp_path, preflight, selected)
    assert result.returncode == 0, result.stderr
    assert "ocp_rhbk_verify_ssl" not in load(env_dir, "vars_rhbk.yml")
    assert _validator_settings(preflight, selected)["verifySsl"] is True


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
def test_explicit_false_is_preserved(tmp_path, mode):
    build, selected = mode
    preflight = build(verify_ssl=False)
    result, env_dir = run(tmp_path, preflight, selected)
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml")["ocp_rhbk_verify_ssl"] is False
    assert _validator_settings(preflight, selected)["verifySsl"] is False
    text = (env_dir / "vars_rhbk.yml").read_text(encoding="utf-8")
    assert "ocp_rhbk_verify_ssl: false" in text
    assert "ocp_rhbk_verify_ssl: False" not in text
    assert 'ocp_rhbk_verify_ssl: "false"' not in text
    assert "ocp_rhbk_verify_ssl: 'False'" not in text


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
def test_explicit_true_is_written(tmp_path, mode):
    build, selected = mode
    result, env_dir = run(tmp_path, build(verify_ssl=True), selected)
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml")["ocp_rhbk_verify_ssl"] is True


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
def test_existing_false_in_vars_survives_regeneration(tmp_path, mode):
    """A bootstrap repo with a hand-set ``ocp_rhbk_verify_ssl: false`` keeps working
    when the preflight does not mention verify_ssl."""
    build, selected = mode
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vars_rhbk.yml").write_text("ocp_rhbk_verify_ssl: false\n", encoding="utf-8")
    result, env_dir = run(tmp_path, build(), selected)
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml")["ocp_rhbk_verify_ssl"] is False
    again, _unused = run(tmp_path, build(), selected)
    assert again.returncode == 0, again.stderr
    assert load(env_dir, "vars_rhbk.yml")["ocp_rhbk_verify_ssl"] is False


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
def test_explicit_true_replaces_an_old_false(tmp_path, mode):
    build, selected = mode
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vars_rhbk.yml").write_text("ocp_rhbk_verify_ssl: false\n", encoding="utf-8")
    result, env_dir = run(tmp_path, build(verify_ssl=True), selected)
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml")["ocp_rhbk_verify_ssl"] is True


def test_the_old_default_of_off_is_gone(tmp_path):
    """Regression: external Keycloak used to get ``ocp_rhbk_verify_ssl: false`` written
    with no preflight value at all."""
    result, env_dir = run(tmp_path, make_preflight(oauth=external_oauth()), ["openshift"])
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_rhbk.yml").get("ocp_rhbk_verify_ssl") is not False


# 9. Strict verify_ssl parsing ---------------------------------------------------
#
# Only the listed spellings are accepted. Anything else is a validation error and is
# never read as "false" (that would silently turn certificate verification off).

VERIFY_VALUES = [
    # (value in the preflight, expected ocp_rhbk_verify_ssl written, or "absent")
    (True, True),
    ("true", True),
    ("TRUE", True),
    (" Yes ", True),
    ("on", True),
    ("ON", True),
    ("1", True),
    (1, True),
    (1.0, True),
    (False, False),
    ("false", False),
    ("FALSE", False),
    ("no", False),
    ("No", False),
    ("off", False),
    (" off ", False),
    ("0", False),
    (0, False),
    (0.0, False),
    (None, "absent"),
    ("", "absent"),
    ("   ", "absent"),
]

INVALID_VERIFY_VALUES = [
    "garbage",
    "tru",
    "flase",
    "ture",
    "fals",
    "yess",
    "of",
    "enabled",
    "disabled",
    "none",
    "null",
    "2",
    "-1",
    "01",
    "1.0",
    "0.0",
    "true false",
    2,
    -1,
    10,
    0.5,
    1.5,
    [],
    [True],
    {},
    {"verify": True},
]


def _id(value):
    return json.dumps(value)


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
@pytest.mark.parametrize(
    "value, expected",
    VERIFY_VALUES,
    ids=[_id(v) for v, _unused in VERIFY_VALUES],
)
def test_accepted_verify_ssl_spellings(tmp_path, mode, value, expected):
    build, selected = mode
    preflight = build(verify_ssl=value)
    result, env_dir = run(tmp_path, preflight, selected)
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    if expected == "absent":
        assert "ocp_rhbk_verify_ssl" not in data
        assert _validator_settings(preflight, selected)["verifySsl"] is True
    else:
        assert data["ocp_rhbk_verify_ssl"] is expected
        assert _validator_settings(preflight, selected)["verifySsl"] is expected


@pytest.mark.parametrize("mode", [MODE_A, MODE_B], ids=["mode-a-rhbk", "mode-b-external"])
@pytest.mark.parametrize(
    "value", INVALID_VERIFY_VALUES, ids=[_id(v) for v in INVALID_VERIFY_VALUES]
)
def test_unrecognized_verify_ssl_is_rejected_before_anything_is_generated(tmp_path, mode, value):
    build, selected = mode
    preflight = build(verify_ssl=value)
    result, env_dir = run(tmp_path, preflight, selected)
    assert result.returncode != 0
    assert "verify_ssl" in result.stderr
    assert "not a recognized value" in result.stderr
    assert "never read as false" in result.stderr
    # Nothing generated: no vars/vault file carries the setting, in particular not "false".
    assert "ocp_rhbk_verify_ssl" not in tree_text(env_dir)
    assert not (env_dir / "vars_rhbk.yml").exists()
    # The same check, run on its own before generation (what the role task runs).
    standalone, _unused = run(tmp_path, preflight, selected, script=VALIDATOR)
    assert standalone.returncode != 0
    assert "not a recognized value" in standalone.stderr
    settings = _validator_settings(preflight, selected)
    assert settings["verifySslValid"] is False
    assert settings["verifySsl"] is True  # a caller that ignores the error still verifies


@pytest.mark.parametrize("value", ["garbage", "flase", 2])
def test_invalid_verify_ssl_does_not_clobber_an_existing_explicit_false(tmp_path, value):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vars_rhbk.yml").write_text("ocp_rhbk_verify_ssl: false\n", encoding="utf-8")
    result, env_dir = run(
        tmp_path, make_preflight(oauth=external_oauth(verify_ssl=value)), ["openshift"]
    )
    assert result.returncode != 0
    assert load(env_dir, "vars_rhbk.yml") == {"ocp_rhbk_verify_ssl": False}


def test_invalid_verify_ssl_is_ignored_when_openshift_oidc_is_not_requested(tmp_path):
    preflight = make_preflight(oauth=external_oauth(verify_ssl="garbage"))
    preflight["component_options"]["openshift"] = []
    result, env_dir = run(tmp_path, preflight, ["openshift"])
    assert result.returncode == 0, result.stderr
    assert "ocp_rhbk_verify_ssl" not in tree_text(env_dir)


def test_error_text_names_the_field_and_the_accepted_values(tmp_path):
    result, _unused = run(
        tmp_path, make_preflight(oauth=external_oauth(verify_ssl="flase")), ["openshift"]
    )
    assert result.returncode != 0
    for needle in ('verify_ssl "flase"', "true, yes, on or 1", "false, no, off or 0", "blank"):
        assert needle in result.stderr, result.stderr


def test_create_client_missing_defaults_to_managed():
    import importlib.util

    spec = importlib.util.spec_from_file_location("preflight_oidc", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.rhbk_client_is_managed({}) is True
    assert module.rhbk_client_is_managed({"create_client": True}) is True
    assert module.rhbk_client_is_managed({"create_client": False}) is False
    assert module.rhbk_client_is_managed({"create_client": "no"}) is False
    assert module.rhbk_client_is_managed({"create_client": "yes"}) is True
    assert module.rhbk_client_is_managed({"create_client": ""}) is True
    assert module.rhbk_client_is_managed("grafana-client") is True


def _parse_verify_ssl():
    sys.path.insert(0, str(FILES))
    try:
        import importlib

        module = importlib.import_module("preflight_oidc")
        return importlib.reload(module).parse_verify_ssl
    finally:
        sys.path.remove(str(FILES))


def test_typos_are_never_read_as_false():
    """Ansible's bool filter treats unrecognized strings as false. The parser
    must not: a typo has to stay 'verify' and be reported as invalid."""
    parse = _parse_verify_ssl()
    for value in ("garbage", "tru", "flase", "ture", "2", 2, -1, "enabled", "1.0"):
        verify, valid, explicit = parse(value)
        assert valid is False, value
        assert verify is True, value
        assert explicit is True, value
    # The values Ansible's bool filter *does* accept still work.
    assert parse("yes") == (True, True, True)
    assert parse("off") == (False, True, True)
    assert parse(None) == (True, True, False)
