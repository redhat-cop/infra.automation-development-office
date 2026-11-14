"""Grafana OIDC must use the same Keycloak target as RHBK Client / OpenShift OAuth."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "roles/grafana_install/tasks/build-grafana-oidc-config.yml"
PLAYBOOK = (
    ROOT
    / "roles/bootstrap_generate_playbook_repo/files/playbooks/grafana"
    / "ado-deploy-oidc-bootstrap.yml"
)


def test_role_prefers_rhbk_hostname_over_leftover_ocp_rhbk() -> None:
    text = BUILD.read_text(encoding="utf-8")
    assert "rhbk_hostname | default(rhbk_host" in text
    assert text.index("rhbk_hostname | default(rhbk_host") < text.index(
        "ocp_rhbk_hostname"
    )
    assert "default('rhlab'" not in text
    assert "default('keycloak.'" not in text


def test_role_announces_target_before_keycloak() -> None:
    text = BUILD.read_text(encoding="utf-8")
    assert "Show the effective Keycloak target" in text
    assert text.index("Show the effective Keycloak target") < text.index(
        "Fetch Keycloak client secret for Grafana"
    )
    announce = text[
        text.index("Show the effective Keycloak target") : text.index(
            "Fetch Keycloak client secret for Grafana"
        )
    ]
    assert "grafana_install_oidc_client_id" in announce
    assert "grafana_install_oidc_secret_hostname" in announce
    assert "grafana_install_oidc_secret_realm" in announce
    assert "ocp_rhbk_secret_hostname:" in text
    assert "ocp_rhbk_secret_realm:" in text


def test_role_tls_token_is_lowercased_and_not_bool_filtered() -> None:
    text = BUILD.read_text(encoding="utf-8")
    assert "grafana_install_oidc_verify_ssl_token:" in text
    assert "raw is boolean" in text
    assert "| string | trim | lower" in text
    start = text.index(
        "Assert the Grafana OIDC Keycloak TLS verification setting is a recognized value"
    )
    end = text.index("\n- name:", start)
    block = text[start:end]
    assert "in ['', '1', 'true', 'yes', 'on', '0', 'false', 'no', 'off']" in block
    assert "never read as false" in block


def test_playbook_prefers_rhbk_hostname_and_does_not_invent_rhlab() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")
    assert "Prefer the RHBK Keycloak connection for Grafana OIDC" in text
    assert "default('rhlab'" not in text
    assert "default('keycloak.'" not in text
    assert text.index("rhbk_hostname | default(rhbk_host") < text.index(
        "ocp_rhbk_hostname | default(hostname"
    )
