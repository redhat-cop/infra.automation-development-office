"""rhbk_client must announce and require the same Keycloak target OAuth inherits."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / "roles/rhbk_client/tasks/rhbk_create_client.yml"
PLAYBOOK = (
    ROOT
    / "roles/bootstrap_generate_playbook_repo/files/playbooks/openshift"
    / "ado-configure-oauth-with-rhbk-bootstrap.yml"
)


def test_create_client_announces_hostname_realm_and_client() -> None:
    text = TASKS.read_text(encoding="utf-8")
    assert "Show the effective Keycloak target" in text
    assert text.index("Show the effective Keycloak target") < text.index(
        "Create or update Keycloak client"
    )
    announce = text[
        text.index("Show the effective Keycloak target") : text.index(
            "Create or update Keycloak client"
        )
    ]
    assert "rhbk_client" in announce
    assert "rhbk_client_kc_url" in announce
    assert "rhbk_realm" in announce


def test_missing_connection_fails_before_keycloak() -> None:
    text = TASKS.read_text(encoding="utf-8")
    assert "Set rhbk_hostname, rhbk_admin_user, rhbk_admin_password, rhbk_realm, rhbk_client." not in text
    assert "before contacting Keycloak" in text
    assert "existing Keycloak hostname and realm" in text


def test_oauth_playbook_prefers_rhbk_hostname_and_does_not_invent_rhlab() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")
    assert "default('rhlab'" not in text
    assert "default('keycloak.'" not in text
    assert "if (" in text
    assert "rhbk_hostname | default(rhbk_host" in text
    assert text.index("rhbk_hostname | default(rhbk_host") < text.index(
        "ocp_rhbk_hostname | default(hostname"
    )
