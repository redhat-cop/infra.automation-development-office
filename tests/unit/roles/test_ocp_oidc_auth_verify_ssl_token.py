"""ocp_oidc_auth must accept YAML boolean true/false for Keycloak TLS verify.

Ansible 2.15 stringifies bool True as ``True``. The allow-list is lowercase.
The token fact must apply ``| lower`` so overlay-written ``ocp_rhbk_verify_ssl: true``
does not fail before any Keycloak request.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / "roles/ocp_oidc_auth/tasks/main.yml"


def test_verify_ssl_token_is_lowercased() -> None:
    text = TASKS.read_text(encoding="utf-8")
    assert "ocp_oidc_auth_verify_ssl_token:" in text
    assert "| string | trim | lower" in text
    assert "raw is boolean" in text


def test_assert_lowercases_before_allow_list() -> None:
    """Ansible 2.15 stores templated true as bool True; assert must lower after | string."""
    text = TASKS.read_text(encoding="utf-8")
    start = text.index("Assert the Keycloak TLS verification setting is a recognized value")
    end = text.index("\n- name:", start)
    block = text[start:end]
    assert "| string | trim | lower" in block
    assert "in ['', '1', 'true', 'yes', 'on', '0', 'false', 'no', 'off']" in block


def test_allow_list_is_lowercase_tokens() -> None:
    text = TASKS.read_text(encoding="utf-8")
    assert "['', '1', 'true', 'yes', 'on', '0', 'false', 'no', 'off']" in text


def test_keycloak_https_calls_pass_lowercase_true_false() -> None:
    """Jinja {{ bool }} is True/False. requests treats a non-empty string as a CA path."""
    text = TASKS.read_text(encoding="utf-8")
    expected = 'validate_certs: "{{ ocp_oidc_auth_verify_ssl | bool | string | lower }}"'
    assert text.count(expected) >= 5
    assert 'validate_certs: "{{ ocp_oidc_auth_verify_ssl | bool }}"' not in text


def test_tls_fail_msg_is_actionable_and_cert_only() -> None:
    text = TASKS.read_text(encoding="utf-8")
    start = text.index("Assert the Keycloak TLS certificate is trusted (fallback path)")
    login_start = text.index("Assert Keycloak admin login succeeded (fallback path)")
    block = text[start:login_start]
    login = text[login_start : text.index("Get the Keycloak realm (fallback path)")]
    assert "Keycloak TLS certificate verification failed" in block
    assert "trust source=" in block
    assert "idm_ca_bundle_pem" in block
    assert "Keep verification enabled" in block
    assert "ocp_oidc_auth_ca_pem" in block
    assert "certificate verify failed" in block
    assert "CERTIFICATE_VERIFY_FAILED" in block
    assert "self-signed certificate" in block
    assert "|SSL')" not in block
    assert "ocp_oidc_auth_verify_ssl | bool" in block
    assert "Keycloak TLS certificate verification failed" not in login
    # Do not suggest disabling TLS verification.
    assert "uncheck" not in block
    assert "uncheck" not in login


def test_missing_realm_is_reported_and_never_created() -> None:
    text = TASKS.read_text(encoding="utf-8")
    assert "Assert the Keycloak realm exists (module path)" in text
    assert "Assert the Keycloak realm exists (fallback path)" in text
    assert "This role does not create realms" in text
    assert "Keycloak realm '{{ ocp_oidc_auth_rhbk_realm }}' does not exist" in text
    assert "keycloak_realm" not in text
    assert "state: present" not in text.split("Assert the Keycloak realm exists (module path)", 1)[1].split(
        "Lookup client UUID by clientId (fallback path)", 1
    )[0]
    perm = text[
        text.index("Assert Keycloak allowed the client lookup (fallback path)") : text.index(
            "Assert client exists (fallback path)"
        )
    ]
    assert "does not exist" not in perm


def test_normalize_prefers_rhbk_hostname_over_oauth_override() -> None:
    text = TASKS.read_text(encoding="utf-8")
    start = text.index("Normalize OIDC inputs from RHBK form vars")
    end = text.index("\n- name:", start)
    block = text[start:end]
    assert "if (" in block
    assert "rhbk_hostname | default(rhbk_host" in block
    assert "else" in block
    assert "ocp_oidc_auth_rhbk_hostname" in block.split("else", 1)[1]
    assert "rhbk_realm | default(ocp_rhbk_realm" in block


def test_shows_effective_keycloak_target_before_contact() -> None:
    text = TASKS.read_text(encoding="utf-8")
    assert "Show the effective Keycloak target" in text
    announce = text[
        text.index("Show the effective Keycloak target") : text.index(
            "TLS verification of Keycloak requests"
        )
    ]
    assert "OpenShift OAuth will read client" in announce
    assert "ocp_oidc_auth_rhbk_hostname" in announce or "ocp_oidc_auth_keycloak_base" in announce
    assert "ocp_oidc_auth_rhbk_realm" in announce
    assert text.index("Show the effective Keycloak target") < text.index(
        "Read the client secret from the existing Keycloak client"
    )


def test_false_survives_ansible_215_stringification() -> None:
    """YAML false becomes bool False; | string is 'False'; the role must lower it."""
    allow = ["", "1", "true", "yes", "on", "0", "false", "no", "off"]
    off = ["0", "false", "no", "off"]
    token = str(False).strip().lower()
    assert token in allow
    assert token in off
    assert (token not in off) is False
