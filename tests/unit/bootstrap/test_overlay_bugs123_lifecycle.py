"""Bugs 1–3 lifecycle: overlay-generated group_vars for mixed OIDC ownership."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"
MANAGE_CLIENT = ROOT / (
    "roles/bootstrap_generate_playbook_repo/files/playbooks/rhbk/"
    "ado-manage-client-bootstrap.yml"
)
MINIO_KEYCLOAK = ROOT / "roles/ocp_minio/tasks/configure-keycloak-oidc.yml"
GRAFANA_MAIN = ROOT / "roles/grafana_install/tasks/main.yml"
OAUTH_ROLE = ROOT / "roles/ocp_oidc_auth/tasks/main.yml"

EXACT_CALLBACK = (
    "https://oauth-openshift.apps.example.test/oauth2callback/Corp-SSO"
)


def rhbk_clients():
    return [
        {
            "id": "grafana-client",
            "name": "Grafana",
            "source": "grafana",
            "create_client": True,
            "redirect_uris": "https://grafana.apps.example.test/*",
            "web_origins": "https://grafana.apps.example.test",
        },
        {
            "id": "OpenshiftDev",
            "name": "OpenShift",
            "source": "openshift",
            "create_client": False,
            "redirect_uris": (
                "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak/*"
            ),
            "web_origins": "https://oauth-openshift.apps.example.test",
        },
        {
            "id": "bookstack",
            "name": "BookStack",
            "source": "bookstack",
            "create_client": True,
            "redirect_uris": "https://bookstack.apps.example.test/*",
            "web_origins": "https://bookstack.apps.example.test",
        },
        {
            "id": "netbox",
            "name": "NetBox",
            "source": "netbox",
            "create_client": True,
            "redirect_uris": "https://netbox.apps.example.test/*",
            "web_origins": "https://netbox.apps.example.test",
        },
        {
            "id": "quay",
            "name": "Quay",
            "source": "quay",
            "create_client": False,
            "redirect_uris": "https://quay.apps.example.test/*",
            "web_origins": "https://quay.apps.example.test",
        },
        {
            "id": "minio",
            "name": "MinIO",
            "source": "minio",
            "create_client": True,
            "redirect_uris": "https://minio.apps.example.test/*",
            "web_origins": "https://minio.apps.example.test",
        },
        {
            "id": "rhdh",
            "name": "Developer Hub",
            "source": "dev_hub",
            "create_client": True,
            "redirect_uris": "https://backstage.apps.example.test/*",
            "web_origins": "https://backstage.apps.example.test",
        },
        {
            "id": "gitlab",
            "name": "GitLab",
            "source": "gitlab",
            "create_client": True,
            "redirect_uris": "https://gitlab.apps.example.test/cb",
            "web_origins": "https://gitlab.apps.example.test",
        },
    ]


def make_preflight():
    return {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {
            "openshift": [
                "rhbk",
                "grafana",
                "bookstack",
                "netbox",
                "quay",
                "minio",
                "dev_hub",
                "gitlab",
            ]
        },
        "component_options": {
            "rhbk": ["client"],
            "openshift": ["oauth_rhbk"],
            "grafana": ["oidc"],
            "bookstack": ["oidc"],
            "netbox": ["oidc"],
            "quay": ["oidc"],
            "minio": ["oidc"],
        },
        "openshift": {
            "apps_domain": "apps.example.test",
            "oauth_rhbk": {
                "client_id": "OpenshiftDev",
                "idp_name": "Corp-SSO",
            },
        },
        "component_config": {
            "rhbk": {
                "hostname": "keycloak.apps.example.test",
                "realm": "demo",
                "admin_user": "admin",
                "admin_password": "rhbk-admin-pass-9f2",
                "clients": copy.deepcopy(rhbk_clients()),
            },
            "grafana": {"oidc": {"enabled": True, "client_id": "grafana-client"}},
            "bookstack": {"oidc_enabled": True, "oidc_client_id": "bookstack"},
            "netbox": {"oidc_enabled": True, "oidc_client_id": "netbox"},
            "quay": {
                "oidc_enabled": True,
                "oidc_client_id": "quay",
                "fetch_oidc_secret_from_rhbk": False,
            },
            "minio": {"oidc_enabled": True, "oidc_client_id": "minio"},
            "dev_hub": {"keycloak_client_id": "rhdh"},
            "gitlab": {"oidc_client_id": "gitlab"},
        },
    }


def run_overlay(tmp_path, preflight, selected):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
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


def test_generated_group_vars_match_ownership_and_callback(tmp_path):
    selected = [
        "rhbk",
        "openshift",
        "grafana",
        "bookstack",
        "netbox",
        "quay",
        "minio",
        "dev_hub",
        "gitlab",
    ]
    result, env_dir = run_overlay(tmp_path, make_preflight(), selected)
    assert result.returncode == 0, result.stderr
    rhbk = load(env_dir, "vars_rhbk.yml")
    grafana = load(env_dir, "vars_grafana.yml")
    bookstack = load(env_dir, "vars_bookstack.yml")
    netbox = load(env_dir, "vars_netbox.yml")
    quay = load(env_dir, "vars_quay.yml")
    minio = load(env_dir, "vars_minio.yml")
    hub = load(env_dir, "vars_dev_hub.yml")

    provisioned = set(rhbk["rhbk_clients"])
    assert provisioned == {"grafana-client", "bookstack", "netbox", "rhdh"}
    assert "OpenshiftDev" not in provisioned
    assert "minio" not in provisioned
    assert "gitlab" not in provisioned
    assert "quay" not in provisioned

    assert rhbk["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"
    assert rhbk["openshift_oidc_auth"]["openshift_oidc_idp_name"] == "Corp-SSO"
    assert rhbk["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == EXACT_CALLBACK
    assert "*" not in rhbk["openshift_oidc_auth"]["openshift_oauth_redirect_uri"]

    assert grafana["oidc"]["enabled"] is True
    assert grafana["oidc"]["client_id"] == "grafana-client"
    assert bookstack["bookstack_oidc_client_id"] == "bookstack"
    assert "vault_bookstack_oidc_client_secret" not in (bookstack or {})
    assert netbox["netbox_oidc_client_id"] == "netbox"
    assert quay["quay_oidc_client_id"] == "quay"
    assert minio["minio_oidc_client_id"] == "minio"
    assert minio["minio_oidc_create_keycloak_client"] is True
    assert hub["dev_hub_keycloak_client_id"] == "rhdh"

    manage = MANAGE_CLIENT.read_text(encoding="utf-8")
    assert "rhbk_clients | dict2items" in manage
    assert "create_client" not in manage
    assert "ocp_minio_manage_keycloak | bool" in MINIO_KEYCLOAK.read_text(encoding="utf-8")
    assert "(oidc | default({})).enabled | default(false) | bool" in GRAFANA_MAIN.read_text(
        encoding="utf-8"
    )
    assert "openshift_oidc_auth.openshift_oidc_idp_name" in OAUTH_ROLE.read_text(
        encoding="utf-8"
    )


def test_disabled_grafana_and_unmanaged_minio_generate_no_keycloak_writers(tmp_path):
    preflight = make_preflight()
    preflight["component_config"]["grafana"]["oidc"]["enabled"] = False
    for row in preflight["component_config"]["rhbk"]["clients"]:
        if row["id"] == "minio":
            row["create_client"] = False
    selected = ["rhbk", "openshift", "grafana", "minio"]
    result, env_dir = run_overlay(tmp_path, preflight, selected)
    assert result.returncode == 0, result.stderr
    rhbk = load(env_dir, "vars_rhbk.yml")
    grafana = load(env_dir, "vars_grafana.yml")
    minio = load(env_dir, "vars_minio.yml")
    assert grafana["oidc"]["enabled"] is False
    assert "grafana-client" not in (rhbk.get("rhbk_clients") or {})
    assert "minio" not in (rhbk.get("rhbk_clients") or {})
    assert minio["minio_oidc_create_keycloak_client"] is False
    assert rhbk["openshift_oidc_auth"]["openshift_oauth_redirect_uri"] == EXACT_CALLBACK
