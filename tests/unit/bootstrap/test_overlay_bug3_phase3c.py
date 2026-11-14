"""Bug 3 Phase 3C: OpenShift IdP callback URI and Grafana OIDC enabled."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FILES = Path(
    os.environ.get("ADO_OIDC_FILES_UNDER_TEST")
    or ROOT / "roles/bootstrap_generate_env_vars/files"
)
OVERLAY = FILES / "overlay_preflight_component_values.py"
GENERATE_ENV = ROOT / "roles/bootstrap_generate_env_vars/tasks/main.yml"
GRAFANA_MAIN = ROOT / "roles/grafana_install/tasks/main.yml"
GRAFANA_OIDC = ROOT / "roles/grafana_install/tasks/configure-grafana-oidc.yml"
GRAFANA_BUILD = ROOT / "roles/grafana_install/tasks/build-grafana-oidc-config.yml"
MINIO_KEYCLOAK = ROOT / "roles/ocp_minio/tasks/configure-keycloak-oidc.yml"
BOOKSTACK_RESOLVE = ROOT / "roles/bookstack_openshift/tasks/resolve-oidc-secret.yml"

DEFAULT_CALLBACK = (
    "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak"
)
CUSTOM_CALLBACK = (
    "https://oauth-openshift.apps.example.test/oauth2callback/Corp-SSO"
)
LEGACY_WILDCARD_CALLBACK = (
    "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak/*"
)

GRAFANA = {
    "id": "grafana-client",
    "name": "Grafana",
    "redirect_uris": "https://grafana.apps.example.test/*",
    "web_origins": "https://grafana.apps.example.test",
    "source": "grafana",
}
OPENSHIFT = {
    "id": "OpenshiftDev",
    "name": "OpenShift",
    "redirect_uris": LEGACY_WILDCARD_CALLBACK,
    "web_origins": "https://oauth-openshift.apps.example.test",
    "source": "openshift",
}
BOOKSTACK = {
    "id": "bookstack",
    "name": "BookStack",
    "redirect_uris": "https://bookstack.apps.example.test/*",
    "web_origins": "https://bookstack.apps.example.test",
    "source": "bookstack",
}
MINIO = {
    "id": "minio",
    "name": "MinIO",
    "redirect_uris": "https://minio.apps.example.test/*",
    "web_origins": "https://minio.apps.example.test",
}


def _oidc():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "preflight_oidc_phase3c", FILES / "preflight_oidc.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rhbk_form(*rows, **extra):
    return {
        "hostname": "keycloak.apps.example.test",
        "realm": "demo",
        "admin_user": "admin",
        "admin_password": "rhbk-admin-pass-9f2",
        "clients": [copy.deepcopy(row) for row in rows],
        **extra,
    }


def make_preflight(*, rhbk=None, oauth=None, apps=None, options=None, config=None):
    component_config = dict(config or {})
    if rhbk is not None:
        component_config["rhbk"] = rhbk
    opts = {"openshift": ["oauth_rhbk"], "rhbk": ["client"]}
    opts.update(options or {})
    return {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {
            "openshift": ["rhbk"] if apps is None else list(apps)
        },
        "component_options": opts,
        "openshift": {
            "apps_domain": "apps.example.test",
            "oauth_rhbk": oauth or {"client_id": "OpenshiftDev"},
        },
        "component_config": component_config,
    }


def run(tmp_path, preflight, selected):
    env_dir = tmp_path / "env"
    env_dir.mkdir(exist_ok=True)
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(OVERLAY)],
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


def test_helpers_default_and_custom_idp_callback():
    module = _oidc()
    default_pf = make_preflight(rhbk=rhbk_form(OPENSHIFT))
    custom_pf = make_preflight(
        rhbk=rhbk_form(OPENSHIFT), oauth={"client_id": "OpenshiftDev", "idp_name": "Corp-SSO"}
    )
    assert module.resolve_openshift_oidc_idp_name(default_pf) == "Keycloak"
    assert module.openshift_oauth_redirect_uri(default_pf) == DEFAULT_CALLBACK
    assert module.resolve_openshift_oidc_idp_name(custom_pf) == "Corp-SSO"
    assert module.openshift_oauth_redirect_uri(custom_pf) == CUSTOM_CALLBACK
    rewritten = module.rewrite_openshift_oauth_redirect_uris(
        [DEFAULT_CALLBACK], custom_pf
    )
    assert rewritten == [CUSTOM_CALLBACK]
    from_wildcard = module.rewrite_openshift_oauth_redirect_uris(
        [LEGACY_WILDCARD_CALLBACK], custom_pf
    )
    assert from_wildcard == [CUSTOM_CALLBACK]
    custom_kept = module.rewrite_openshift_oauth_redirect_uris(
        ["https://oauth.apps.example.test/*"], custom_pf
    )
    assert custom_kept == ["https://oauth.apps.example.test/*"]


def test_default_idp_callback_is_written_for_managed_openshift(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(rhbk=rhbk_form(OPENSHIFT)),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["openshift_oidc_auth"]["openshift_oidc_idp_name"] == "Keycloak"
    assert data["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == DEFAULT_CALLBACK
    assert data["rhbk_clients"]["OpenshiftDev"]["rhbk_redirect_uris"] == [DEFAULT_CALLBACK]


def test_custom_idp_rewrites_managed_openshift_callback(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(OPENSHIFT),
            oauth={"client_id": "OpenshiftDev", "idp_name": "Corp-SSO"},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert data["openshift_oidc_auth"]["openshift_oidc_idp_name"] == "Corp-SSO"
    assert data["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == CUSTOM_CALLBACK
    assert data["rhbk_clients"]["OpenshiftDev"]["rhbk_redirect_uris"] == [CUSTOM_CALLBACK]


def test_unmanaged_openshift_client_is_not_in_rhbk_clients(tmp_path):
    unmanaged = {**copy.deepcopy(OPENSHIFT), "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged),
            oauth={"client_id": "OpenshiftDev", "idp_name": "Corp-SSO"},
        ),
        ["rhbk", "openshift"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_rhbk.yml")
    assert "rhbk_clients" not in data
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"
    assert data["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == CUSTOM_CALLBACK
    passthrough = data.get("clients") or []
    row = next(item for item in passthrough if item.get("id") == "OpenshiftDev")
    assert row.get("create_client") is False
    assert row.get("redirect_uris") == LEGACY_WILDCARD_CALLBACK


def test_json_round_trip_preserves_idp_name_and_grafana_enabled(tmp_path):
    preflight = make_preflight(
        rhbk=rhbk_form(OPENSHIFT, GRAFANA),
        oauth={"client_id": "OpenshiftDev", "idp_name": "Corp-SSO"},
        apps=["rhbk", "grafana"],
        options={"grafana": ["oidc"]},
        config={"grafana": {"oidc": {"enabled": False, "client_id": "grafana-client"}}},
    )
    imported = json.loads(json.dumps(preflight))
    result, env_dir = run(tmp_path, imported, ["rhbk", "openshift", "grafana"])
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    grafana_vars = load(env_dir, "vars_grafana.yml")
    assert imported["openshift"]["oauth_rhbk"]["idp_name"] == "Corp-SSO"
    assert rhbk_vars["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == CUSTOM_CALLBACK
    assert grafana_vars["oidc"]["enabled"] is False
    assert "grafana-client" not in (rhbk_vars.get("rhbk_clients") or {})


def test_grafana_oidc_explicitly_enabled(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GRAFANA, OPENSHIFT),
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}}},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    grafana_vars = load(env_dir, "vars_grafana.yml")
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    assert grafana_vars["oidc"]["enabled"] is True
    assert grafana_vars["oidc"]["client_id"] == "grafana-client"
    assert "grafana-client" in rhbk_vars["rhbk_clients"]


def test_grafana_oidc_explicitly_disabled(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GRAFANA, OPENSHIFT),
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": {"oidc": {"enabled": False, "client_id": "grafana-client"}}},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    grafana_vars = load(env_dir, "vars_grafana.yml")
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    assert grafana_vars["oidc"]["enabled"] is False
    assert "grafana-client" not in (rhbk_vars.get("rhbk_clients") or {})
    assert "OpenshiftDev" in rhbk_vars["rhbk_clients"]


def test_grafana_oidc_enabled_absent_defaults_on(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GRAFANA, OPENSHIFT),
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": {"oidc": {"client_id": "grafana-client"}}},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    grafana_vars = load(env_dir, "vars_grafana.yml")
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    assert grafana_vars["oidc"]["enabled"] is True
    assert "grafana-client" in rhbk_vars["rhbk_clients"]


def test_grafana_unmanaged_client_stays_out_of_rhbk_clients_when_oidc_on(tmp_path):
    unmanaged = {**copy.deepcopy(GRAFANA), "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged, OPENSHIFT),
            apps=["rhbk", "grafana"],
            options={"grafana": ["oidc"]},
            config={"grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}}},
        ),
        ["rhbk", "openshift", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    grafana_vars = load(env_dir, "vars_grafana.yml")
    assert "grafana-client" not in rhbk_vars["rhbk_clients"]
    assert grafana_vars["oidc"]["enabled"] is True
    assert grafana_vars["oidc"]["client_id"] == "grafana-client"


def test_mixed_grafana_openshift_bookstack_minio(tmp_path):
    unmanaged_os = {**copy.deepcopy(OPENSHIFT), "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged_os, GRAFANA, BOOKSTACK, MINIO),
            oauth={"client_id": "OpenshiftDev", "idp_name": "Corp-SSO"},
            apps=["rhbk", "grafana", "bookstack", "minio"],
            options={
                "grafana": ["oidc"],
                "bookstack": ["oidc"],
                "minio": ["oidc"],
            },
            config={
                "grafana": {"oidc": {"enabled": False, "client_id": "grafana-client"}},
                "bookstack": {"oidc_enabled": True, "oidc_client_id": "bookstack"},
                "minio": {"oidc_enabled": True, "oidc_client_id": "minio"},
            },
        ),
        ["rhbk", "openshift", "grafana", "bookstack", "minio"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    grafana_vars = load(env_dir, "vars_grafana.yml")
    minio_vars = load(env_dir, "vars_minio.yml")
    clients = list(rhbk_vars["rhbk_clients"])
    assert clients == ["bookstack"]
    assert "grafana-client" not in clients
    assert "OpenshiftDev" not in clients
    assert "minio" not in clients
    assert grafana_vars["oidc"]["enabled"] is False
    assert rhbk_vars["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == CUSTOM_CALLBACK
    assert minio_vars["minio_oidc_client_id"] == "minio"
    assert minio_vars["minio_oidc_create_keycloak_client"] is True
    assert load(env_dir, "vars_bookstack.yml")["bookstack_oidc_client_id"] == "bookstack"


def test_disabled_grafana_yaml_skips_secret_fetch_and_oidc_jt():
    configure = GRAFANA_OIDC.read_text(encoding="utf-8")
    main = GRAFANA_MAIN.read_text(encoding="utf-8")
    build = GRAFANA_BUILD.read_text(encoding="utf-8")
    generate = GENERATE_ENV.read_text(encoding="utf-8")
    assert "grafana_install_oidc_enabled: true" not in configure
    assert "grafana_install_oidc_enabled | bool" in configure
    assert "(oidc | default({})).enabled" in configure
    assert "(oidc | default({})).enabled | default(false) | bool" in main
    assert "grafana_install_oidc_enabled | default(false) | bool" in build
    oidc_block = generate[generate.find("['grafana_oidc']"):]
    oidc_block = oidc_block[: oidc_block.find("['grafana_email']")]
    assert "enabled | default(true) | bool" in oidc_block


def test_phase1_3a_3b_contracts_still_hold():
    minio_text = MINIO_KEYCLOAK.read_text(encoding="utf-8")
    bookstack = BOOKSTACK_RESOLVE.read_text(encoding="utf-8")
    assert "ocp_minio_manage_keycloak | bool" in minio_text
    assert "ocp_minio_apply_policy_mapper | bool" in minio_text
    assert "ocp_rhbk_secret_optional: false" in bookstack
    module = _oidc()
    assert module.rhbk_client_is_managed({}) is True
    assert module.rhbk_client_is_managed({"create_client": False}) is False
    assert module.minio_role_owns_keycloak_client_id(
        {"component_config": {"minio": {"oidc_client_id": "minio"}}},
        ["minio"],
        "minio",
    )
    assert module.gitlab_keycloak_client_should_not_be_provisioned(
        {}, ["rhbk"], "gitlab", {"id": "gitlab", "source": "gitlab"}
    )
    grafana_disabled = {
        "component_config": {"grafana": {"oidc": {"enabled": False, "client_id": "grafana-client"}}},
        "component_options": {"grafana": ["oidc"]},
    }
    assert module.grafana_keycloak_client_should_not_be_provisioned(
        grafana_disabled, ["grafana"], "grafana-client", GRAFANA
    )
    grafana_on = {
        "component_config": {"grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}}},
        "component_options": {"grafana": ["oidc"]},
    }
    assert not module.grafana_keycloak_client_should_not_be_provisioned(
        grafana_on, ["grafana"], "grafana-client", GRAFANA
    )
