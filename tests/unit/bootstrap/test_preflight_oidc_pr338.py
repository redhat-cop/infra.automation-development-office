"""PR 338 review regressions: client match, ownership merge, mapping preserve."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "roles/bootstrap_generate_env_vars/files/preflight_oidc.py"


def _load():
    spec = importlib.util.spec_from_file_location("preflight_oidc_pr338", MODULE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


oidc = _load()


def test_openshift_client_id_does_not_match_gitops_prefix():
    preflight = {
        "openshift": {"oauth_rhbk": {}},
        "component_config": {
            "rhbk": {
                "clients": [
                    {
                        "id": "openshift-gitops",
                        "name": "GitOps",
                        "redirect_uris": ["https://example/cb"],
                    },
                    {
                        "id": "OpenshiftDev",
                        "name": "OpenShift",
                        "source": "openshift",
                        "redirect_uris": ["https://oauth.example/cb"],
                    },
                ]
            }
        },
    }
    assert oidc.resolve_openshift_oidc_client_id(preflight) == "OpenshiftDev"
    assert not oidc.row_is_openshift_oidc_client(
        preflight, "openshift-gitops", preflight["component_config"]["rhbk"]["clients"][0]
    )
    assert oidc.row_is_openshift_oidc_client(
        preflight, "OpenshiftDev", preflight["component_config"]["rhbk"]["clients"][1]
    )


def test_openshift_prod_exact_legacy_fallback_only():
    preflight = {
        "openshift": {"oauth_rhbk": {}},
        "component_config": {
            "rhbk": {
                "clients": [
                    {"id": "openshift-production", "name": "No"},
                    {"id": "openshift-prod", "name": "Legacy"},
                ]
            }
        },
    }
    assert oidc.resolve_openshift_oidc_client_id(preflight) == "openshift-prod"
    assert not oidc.row_is_openshift_oidc_client(preflight, "openshift-production")


def test_explicit_oauth_client_id_wins_over_prefixish_rows():
    preflight = {
        "openshift": {"oauth_rhbk": {"client_id": "my-ocp-oauth"}},
        "component_config": {
            "rhbk": {
                "clients": [
                    {"id": "openshift-gitops", "name": "GitOps"},
                    {"id": "openshift-prod", "name": "Legacy"},
                ]
            }
        },
    }
    assert oidc.resolve_openshift_oidc_client_id(preflight) == "my-ocp-oauth"
    assert oidc.row_is_openshift_oidc_client(preflight, "my-ocp-oauth")
    assert not oidc.row_is_openshift_oidc_client(preflight, "openshift-prod")


def test_merge_preserves_user_managed_and_drops_ado_owned():
    prior = {
        "custom-app": {"rhbk_client_name": "Custom"},
        "grafana-client": {
            "rhbk_client_name": "Grafana",
            "ado_owner": "grafana",
            "rhbk_redirect_uris": ["https://old/"],
        },
    }
    newly = {
        "grafana-client": {
            "rhbk_client_name": "Grafana",
            "ado_owner": "grafana",
            "rhbk_redirect_uris": ["https://new/"],
        }
    }
    merged = oidc.merge_rhbk_clients_for_regen(prior, newly, drop_ids=set())
    assert set(merged) == {"custom-app", "grafana-client"}
    assert merged["grafana-client"]["rhbk_redirect_uris"] == ["https://new/"]
    assert merged["custom-app"]["rhbk_client_name"] == "Custom"

    dropped = oidc.merge_rhbk_clients_for_regen(prior, {}, drop_ids=set())
    assert list(dropped) == ["custom-app"]


def test_merge_force_drops_minio_and_unmanaged_ids():
    prior = {
        "minio": {"rhbk_client_name": "MinIO"},
        "custom-app": {"rhbk_client_name": "Custom"},
    }
    merged = oidc.merge_rhbk_clients_for_regen(
        prior, {"grafana-client": {"ado_owner": "grafana"}}, drop_ids={"minio"}
    )
    assert "minio" not in merged
    assert "custom-app" in merged
    assert "grafana-client" in merged


def test_mapping_method_preserves_existing_claim_on_regen():
    preflight = {"openshift": {"oauth_rhbk": {}}}
    existing = {"openshift_oidc_mapping_method": "claim"}
    assert (
        oidc.resolve_openshift_oidc_mapping_method(preflight, existing) == "claim"
    )


def test_mapping_method_explicit_preflight_wins():
    preflight = {"openshift": {"oauth_rhbk": {"mapping_method": "lookup"}}}
    existing = {"openshift_oidc_mapping_method": "claim"}
    assert (
        oidc.resolve_openshift_oidc_mapping_method(preflight, existing) == "lookup"
    )


def test_mapping_method_defaults_to_add_for_new_configs():
    preflight = {"openshift": {"oauth_rhbk": {}}}
    assert oidc.resolve_openshift_oidc_mapping_method(preflight, None) == "add"


def test_rewrite_uris_only_for_openshift_oauth_client():
    preflight = {
        "openshift": {
            "apps_domain": "apps.example.test",
            "oauth_rhbk": {"client_id": "OpenshiftDev", "idp_name": "Keycloak"},
        },
        "component_config": {"rhbk": {"clients": []}},
    }
    gitops = {
        "id": "openshift-gitops",
        "redirect_uris": ["https://console.apps.example.test/"],
    }
    assert not oidc.row_is_openshift_oidc_client(preflight, "openshift-gitops", gitops)
    # Unrelated client URIs must not be rewritten by OpenShift callback logic
    # when the row is not the configured OpenShift OAuth client.
    # When called for the real OpenShift client, callback is enforced.
    rewritten = oidc.rewrite_openshift_oauth_redirect_uris(
        ["https://oauth-openshift.apps.example.test/oauth2callback/Keycloak/*"],
        preflight,
    )
    assert rewritten == [
        "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak"
    ]


def test_deselecting_owner_drops_ado_row_but_keeps_custom():
    prior = {
        "grafana-client": {"ado_owner": "grafana", "rhbk_client_name": "Grafana"},
        "custom-app": {"rhbk_client_name": "Custom"},
        "OpenshiftDev": {
            "ado_owner": "openshift",
            "rhbk_redirect_uris": [
                "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak"
            ],
        },
    }
    newly = {
        "OpenshiftDev": {
            "ado_owner": "openshift",
            "rhbk_redirect_uris": [
                "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak"
            ],
        }
    }
    merged = oidc.merge_rhbk_clients_for_regen(
        prior, newly, drop_ids={"grafana-client"}
    )
    assert "custom-app" in merged
    assert "OpenshiftDev" in merged
    assert "grafana-client" not in merged
    assert merged["OpenshiftDev"]["rhbk_redirect_uris"] == [
        "https://oauth-openshift.apps.example.test/oauth2callback/Keycloak"
    ]
