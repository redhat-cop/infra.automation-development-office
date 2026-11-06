"""Phase 3B: BookStack OIDC secret handling and GitLab unused-client skip."""

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
BOOKSTACK_RESOLVE = ROOT / "roles/bookstack_openshift/tasks/resolve-oidc-secret.yml"
BOOKSTACK_CONFIGURE = ROOT / "roles/bookstack_openshift/tasks/configure-oidc.yml"
BOOKSTACK_SECRETS = ROOT / "roles/bookstack_openshift/tasks/secrets.yml"
RHBK_SECRETS = ROOT / "roles/ocp_rhbk_client_secrets/tasks/main.yml"
MINIO_KEYCLOAK = ROOT / "roles/ocp_minio/tasks/configure-keycloak-oidc.yml"

GRAFANA = {
    "id": "grafana-client",
    "name": "Grafana",
    "redirect_uris": "https://grafana.apps.example.test/*",
    "web_origins": "https://grafana.apps.example.test",
}
BOOKSTACK = {
    "id": "bookstack",
    "name": "BookStack",
    "redirect_uris": "https://bookstack.apps.example.test/*",
    "web_origins": "https://bookstack.apps.example.test",
    "source": "bookstack",
}
NETBOX = {
    "id": "netbox",
    "name": "NetBox",
    "redirect_uris": "https://netbox.apps.example.test/*",
    "web_origins": "https://netbox.apps.example.test",
    "source": "netbox",
}
GITLAB = {
    "id": "gitlab",
    "name": "GitLab",
    "redirect_uris": "https://gitlab.apps.example.test/users/auth/openid_connect/callback",
    "web_origins": "https://gitlab.apps.example.test",
    "source": "gitlab",
}
MINIO = {
    "id": "minio",
    "name": "MinIO",
    "redirect_uris": "https://minio.apps.example.test/*",
    "web_origins": "https://minio.apps.example.test",
}


def _defaults_module():
    sys.path.insert(0, str(FILES))
    try:
        import preflight_oidc

        return preflight_oidc
    finally:
        sys.path.remove(str(FILES))


def rhbk_form(*rows, **extra):
    clients = [copy.deepcopy(row) for row in rows]
    return {
        "hostname": "keycloak.apps.example.test",
        "realm": "demo",
        "admin_user": "admin",
        "admin_password": "rhbk-admin-pass-9f2",
        "clients": clients,
        **extra,
    }


def make_preflight(*, rhbk=None, apps=None, options=None, config=None):
    component_config = dict(config or {})
    if rhbk is not None:
        component_config["rhbk"] = rhbk
    opts = {"rhbk": ["client"]}
    opts.update(options or {})
    return {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": list(apps or [])},
        "component_options": opts,
        "openshift": {"apps_domain": "apps.example.test"},
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


def test_gitlab_helper_skips_source_and_selected_default():
    module = _defaults_module()
    row = {"id": "gitlab", "source": "gitlab"}
    selected_gitlab = {
        "component_config": {"gitlab": {"oidc_client_id": "corp-gitlab"}}
    }
    assert module.gitlab_keycloak_client_should_not_be_provisioned(
        {}, ["rhbk"], "gitlab", row
    )
    assert module.gitlab_keycloak_client_should_not_be_provisioned(
        selected_gitlab, ["gitlab", "rhbk"], "corp-gitlab", {"id": "corp-gitlab"}
    )
    assert module.gitlab_keycloak_client_should_not_be_provisioned(
        {"component_config": {"gitlab": {}}}, ["gitlab"], "gitlab", {"id": "gitlab"}
    )
    assert not module.gitlab_keycloak_client_should_not_be_provisioned(
        {}, ["rhbk"], "grafana-client", GRAFANA
    )
    assert not module.gitlab_keycloak_client_should_not_be_provisioned(
        {}, ["rhbk"], "gitlab", {"id": "gitlab"}
    )


def test_bookstack_role_fetches_secret_before_oidc_apply():
    resolve = BOOKSTACK_RESOLVE.read_text(encoding="utf-8")
    configure = BOOKSTACK_CONFIGURE.read_text(encoding="utf-8")
    secrets = BOOKSTACK_SECRETS.read_text(encoding="utf-8")
    fetch = RHBK_SECRETS.read_text(encoding="utf-8")
    assert "ocp_rhbk_client_secrets" in resolve
    assert "ocp_rhbk_secret_optional: false" in resolve
    assert "bookstack_openshift_oidc_client_secret_effective" in resolve
    assert "no_log: true" in resolve
    assert "An empty secret is not written to BookStack" in resolve
    assert "bookstack_openshift_existing_oidc_client_id" in resolve
    assert "oidc-client-id matches this client" in resolve
    assert "== (bookstack_oidc_client_id | default('bookstack') | trim)" in resolve
    assert "include_tasks: resolve-oidc-secret.yml" in configure
    assert configure.find("include_tasks: resolve-oidc-secret.yml") < configure.find(
        "Patch BookStack app secret"
    )
    assert "bookstack_openshift_oidc_client_secret_effective" in configure
    assert "bookstack_oidc_client_secret | default('')" not in configure.split(
        "Patch BookStack app secret"
    )[-1]
    assert "include_tasks: resolve-oidc-secret.yml" in secrets
    assert "bookstack_openshift_oidc_client_secret_effective" in secrets
    assert "infra.automation_development_office.rhbk_client" not in (
        configure + secrets + resolve
    )
    assert "Could not find Keycloak client" in fetch
    assert "Keycloak admin token (password grant) failed" in fetch
    assert "Keycloak client secret was not returned" in fetch
    fail = resolve.split("fail_msg:", 1)[1]
    assert "{{ bookstack_openshift_oidc_client_secret_effective }}" not in fail
    assert "{{ ocp_rhbk_client_secrets__value }}" not in fail
    assert "{{ ocp_rhbk_secret_value }}" not in fail


def test_bookstack_secret_tasks_use_no_log():
    resolve = BOOKSTACK_RESOLVE.read_text(encoding="utf-8")
    for name in (
        "Fetch BookStack OIDC client secret from Keycloak when unset",
        "Resolve BookStack OIDC client secret",
        "Decode existing BookStack OIDC client identity",
    ):
        block = resolve.split("- name: " + name, 1)[1].split("- name:", 1)[0]
        assert "no_log: true" in block


def test_bookstack_explicit_secret_reaches_vault(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(BOOKSTACK, GRAFANA),
            apps=["rhbk", "bookstack"],
            options={"bookstack": ["oidc"]},
            config={
                "bookstack": {
                    "oidc_enabled": True,
                    "oidc_client_id": "bookstack",
                    "oidc_client_secret": "supplied-secret",
                }
            },
        ),
        ["rhbk", "bookstack"],
    )
    assert result.returncode == 0, result.stderr
    bookstack_vars = load(env_dir, "vars_bookstack.yml")
    vault = load(env_dir, "vault_bookstack.yml")
    assert bookstack_vars["bookstack_oidc_client_id"] == "bookstack"
    assert "vault_bookstack_oidc_client_secret" in str(
        bookstack_vars["bookstack_oidc_client_secret"]
    )
    assert vault["vault_bookstack_oidc_client_secret"] == "supplied-secret"


def test_bookstack_empty_secret_is_not_written(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(BOOKSTACK, GRAFANA),
            apps=["rhbk", "bookstack"],
            options={"bookstack": ["oidc"]},
            config={
                "bookstack": {
                    "oidc_enabled": True,
                    "oidc_client_id": "bookstack",
                }
            },
        ),
        ["rhbk", "bookstack"],
    )
    assert result.returncode == 0, result.stderr
    bookstack_vars = load(env_dir, "vars_bookstack.yml")
    vault = load(env_dir, "vault_bookstack.yml") or {}
    assert bookstack_vars["bookstack_oidc_enabled"] is True
    assert bookstack_vars["bookstack_oidc_client_id"] == "bookstack"
    assert "bookstack_oidc_client_secret" not in bookstack_vars
    assert "vault_bookstack_oidc_client_secret" not in vault


def test_bookstack_unmanaged_client_still_writes_oidc_id(tmp_path):
    unmanaged = {**copy.deepcopy(BOOKSTACK), "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged, GRAFANA),
            apps=["rhbk", "bookstack"],
            options={"bookstack": ["oidc"]},
            config={
                "bookstack": {"oidc_enabled": True, "oidc_client_id": "bookstack"}
            },
        ),
        ["rhbk", "bookstack"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    bookstack_vars = load(env_dir, "vars_bookstack.yml")
    assert "bookstack" not in (rhbk_vars.get("rhbk_clients") or {})
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert bookstack_vars["bookstack_oidc_client_id"] == "bookstack"
    assert bookstack_vars["bookstack_oidc_enabled"] is True


def test_gitlab_selected_does_not_provision_unused_client(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GITLAB, GRAFANA),
            apps=["rhbk", "gitlab", "grafana"],
            options={"grafana": ["oidc"]},
            config={
                "gitlab": {"oidc_client_id": "gitlab"},
                "grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}},
            },
        ),
        ["rhbk", "gitlab", "grafana"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    gitlab_vars = load(env_dir, "vars_gitlab.yml")
    assert "gitlab" not in (rhbk_vars.get("rhbk_clients") or {})
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert gitlab_vars is not None
    clients = rhbk_vars.get("clients") or []
    assert any(
        isinstance(row, dict) and row.get("id") == "gitlab" for row in clients
    )


def test_gitlab_selected_without_oidc_does_not_require_a_client(tmp_path):
    result, _env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GRAFANA),
            apps=["rhbk", "gitlab", "grafana"],
            options={"grafana": ["oidc"]},
            config={
                "gitlab": {},
                "grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}},
            },
        ),
        ["rhbk", "gitlab", "grafana"],
    )
    assert result.returncode == 0, result.stderr


def test_legacy_gitlab_oidc_flag_still_needs_an_explicit_client(tmp_path):
    result, _env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GRAFANA),
            apps=["rhbk", "gitlab"],
            options={"gitlab": ["oidc"]},
            config={"gitlab": {"oidc_enabled": True}},
        ),
        ["rhbk", "gitlab"],
    )
    assert result.returncode != 0
    assert "GitLab OIDC is enabled but has no Keycloak client" in result.stderr


def test_mixed_grafana_bookstack_netbox_gitlab(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(GRAFANA, BOOKSTACK, NETBOX, GITLAB),
            apps=["rhbk", "grafana", "bookstack", "netbox", "gitlab"],
            options={
                "grafana": ["oidc"],
                "bookstack": ["oidc"],
                "netbox": ["oidc"],
            },
            config={
                "grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}},
                "bookstack": {"oidc_enabled": True, "oidc_client_id": "bookstack"},
                "netbox": {"oidc_enabled": True, "oidc_client_id": "netbox"},
                "gitlab": {"oidc_client_id": "gitlab"},
            },
        ),
        ["rhbk", "grafana", "bookstack", "netbox", "gitlab"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    clients = list(rhbk_vars["rhbk_clients"])
    assert "grafana-client" in clients
    assert "bookstack" in clients
    assert "netbox" in clients
    assert "gitlab" not in clients
    assert load(env_dir, "vars_bookstack.yml")["bookstack_oidc_client_id"] == "bookstack"
    assert load(env_dir, "vars_netbox.yml")["netbox_oidc_client_id"] == "netbox"


def test_phase1_ownership_and_phase3a_minio_still_hold(tmp_path):
    unmanaged_os = {
        "id": "OpenshiftDev",
        "name": "OpenShift",
        "redirect_uris": "https://oauth.apps.example.test/*",
        "web_origins": "https://oauth.apps.example.test",
        "create_client": False,
        "source": "openshift",
    }
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged_os, GRAFANA, MINIO, GITLAB),
            apps=["rhbk", "grafana", "minio", "gitlab"],
            options={"grafana": ["oidc"], "minio": ["oidc"]},
            config={
                "grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}},
                "minio": {"oidc_enabled": True, "oidc_client_id": "minio"},
                "gitlab": {"oidc_client_id": "gitlab"},
            },
        ),
        ["rhbk", "grafana", "minio", "gitlab"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    minio_vars = load(env_dir, "vars_minio.yml")
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert "OpenshiftDev" not in rhbk_vars["rhbk_clients"]
    assert "minio" not in rhbk_vars["rhbk_clients"]
    assert "gitlab" not in rhbk_vars["rhbk_clients"]
    assert minio_vars["minio_oidc_client_id"] == "minio"
    assert minio_vars["minio_oidc_create_keycloak_client"] is True
    text = MINIO_KEYCLOAK.read_text(encoding="utf-8")
    assert "ocp_minio_manage_keycloak | bool" in text
    assert "ocp_minio_apply_policy_mapper | bool" in text
