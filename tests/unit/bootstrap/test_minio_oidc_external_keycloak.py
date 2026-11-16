"""MinIO OIDC Keycloak inherit vs external (no RHBK component)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = Path(
    os.environ.get("ADO_OIDC_FILES_UNDER_TEST")
    or ROOT / "roles/bootstrap_generate_env_vars/files"
)
sys.path.insert(0, str(FILES))
import preflight_oidc  # noqa: E402


def base_preflight(*, rhbk=False, minio=None):
    components = ["minio"]
    apps = ["minio"]
    config = {
        "minio": {
            "oidc_enabled": True,
            "oidc_client_id": "minio",
            "keycloak_realm": "rhlab",
            "fetch_oidc_secret_from_rhbk": True,
            **(minio or {}),
        }
    }
    if rhbk:
        components.append("rhbk")
        apps.append("rhbk")
        config["rhbk"] = {
            "hostname": "keycloak.apps.example.test",
            "realm": "demo",
            "admin_user": "admin",
            "admin_password": "rhbk-pass",
        }
    return {
        "components": components,
        "component_apps": {"openshift": apps},
        "component_options": {"minio": ["oidc"]},
        "openshift": {"apps_domain": "apps.example.test"},
        "component_config": config,
    }


def test_oidc_disabled_skips_validation():
    pf = base_preflight(minio={"oidc_enabled": False})
    assert preflight_oidc.minio_oidc_requested(pf, {"minio"}) is False
    assert preflight_oidc.validate_minio_keycloak_settings(pf, {"minio"}) == []


def test_rhbk_selected_inherits_without_minio_connection_fields():
    pf = base_preflight(rhbk=True)
    selected = {"minio", "rhbk"}
    settings = preflight_oidc.resolve_minio_keycloak_settings(pf, selected)
    assert settings["mode"] == "rhbk"
    assert settings["hostname"] == "keycloak.apps.example.test"
    assert settings["realm"] == "demo"
    assert settings["adminPasswordSource"] == "rhbk"
    assert preflight_oidc.validate_minio_keycloak_settings(pf, selected) == []


def test_external_keycloak_requires_minio_form_credentials():
    pf = base_preflight()
    selected = {"minio"}
    errors = preflight_oidc.validate_minio_keycloak_settings(pf, selected)
    kinds = {e["kind"] for e in errors}
    assert "missing-hostname" in kinds
    assert "missing-admin-password" in kinds
    assert all("RHBK separately" not in e["message"] for e in errors)

    pf["component_config"]["minio"].update(
        {
            "keycloak_hostname": "keycloak.lab.example",
            "keycloak_realm": "lab",
            "keycloak_admin_user": "admin",
            "keycloak_admin_password": "kc-pass",
        }
    )
    settings = preflight_oidc.resolve_minio_keycloak_settings(pf, selected)
    assert settings["mode"] == "external"
    assert settings["hostname"] == "keycloak.lab.example"
    assert settings["adminPasswordSource"] == "minio"
    assert preflight_oidc.validate_minio_keycloak_settings(pf, selected) == []


def test_validate_preflight_oidc_includes_minio():
    pf = base_preflight()
    errors = preflight_oidc.validate_preflight_oidc(pf, {"minio"})
    assert any(e["component"] == "minio" for e in errors)


def test_minio_verify_ssl_defaults_to_skip_when_unset():
    pf = base_preflight(
        minio={
            "keycloak_hostname": "keycloak.lab.example",
            "keycloak_admin_user": "admin",
            "keycloak_admin_password": "kc-pass",
        }
    )
    settings = preflight_oidc.resolve_minio_keycloak_settings(pf, {"minio"})
    assert settings["verifySsl"] is False
    assert settings["verifySslValid"] is True
    assert settings["verifySslExplicit"] is True


def test_minio_verify_ssl_explicit_true_and_false():
    for value, expected in ((False, False), (True, True), ("false", False), ("true", True)):
        pf = base_preflight(
            minio={
                "keycloak_hostname": "keycloak.lab.example",
                "keycloak_admin_user": "admin",
                "keycloak_admin_password": "kc-pass",
                "keycloak_verify_ssl": value,
            }
        )
        settings = preflight_oidc.resolve_minio_keycloak_settings(pf, {"minio"})
        assert settings["verifySsl"] is expected
        assert settings["verifySslValid"] is True


def test_minio_verify_ssl_not_taken_from_openshift_oauth_when_rhbk_selected():
    pf = base_preflight(rhbk=True, minio={"keycloak_verify_ssl": False})
    pf["openshift"] = {
        "apps_domain": "apps.example.test",
        "oauth_rhbk": {"verify_ssl": True},
    }
    settings = preflight_oidc.resolve_minio_keycloak_settings(pf, {"minio", "rhbk"})
    assert settings["mode"] == "rhbk"
    assert settings["verifySsl"] is False


def test_discovery_url_from_hostname_and_custom_realm():
    pf = base_preflight(
        minio={
            "keycloak_hostname": "keycloak.apps.ocp-dev.dev.rhlab",
            "keycloak_realm": "Dev",
            "keycloak_admin_user": "admin",
            "keycloak_admin_password": "kc-pass",
            "oidc_config_url": "",
            "oidc_issuer": "",
        }
    )
    settings = preflight_oidc.resolve_minio_keycloak_settings(pf, {"minio"})
    expected = (
        "https://keycloak.apps.ocp-dev.dev.rhlab/realms/Dev"
        "/.well-known/openid-configuration"
    )
    assert settings["discoveryUrl"] == expected
    assert settings["issuer"] == "https://keycloak.apps.ocp-dev.dev.rhlab/realms/Dev"
    assert preflight_oidc.resolve_minio_oidc_discovery_url(pf, {"minio"}) == expected
    assert preflight_oidc.validate_minio_keycloak_settings(pf, {"minio"}) == []


def test_empty_imported_config_url_does_not_block_derived_discovery():
    """Imported blanks must not wipe hostname+realm derivation."""
    pf = base_preflight(
        minio={
            "keycloak_hostname": "keycloak.lab.example",
            "keycloak_realm": "lab",
            "keycloak_admin_user": "admin",
            "keycloak_admin_password": "kc-pass",
            "oidc_config_url": "",
            "minio_oidc_config_url": "",
            "oidc_issuer": "",
        }
    )
    url = preflight_oidc.resolve_minio_oidc_discovery_url(pf, {"minio"})
    assert url.startswith("https://keycloak.lab.example/realms/lab/")
    assert url.endswith("/.well-known/openid-configuration")


def test_explicit_discovery_url_wins():
    explicit = (
        "https://sso.corp.example/realms/corp/.well-known/openid-configuration"
    )
    pf = base_preflight(
        minio={
            "keycloak_hostname": "ignored.example",
            "keycloak_realm": "ignored",
            "keycloak_admin_user": "admin",
            "keycloak_admin_password": "kc-pass",
            "oidc_config_url": explicit,
        }
    )
    assert preflight_oidc.resolve_minio_oidc_discovery_url(pf, {"minio"}) == explicit
