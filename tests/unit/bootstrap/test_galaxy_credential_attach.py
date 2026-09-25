"""Unit tests for Galaxy org-attach selection rules.

Mirrors the Contoller organization ``galaxy_credentials`` filter in
``roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2`` so the
``integration_galaxy_sources`` Molecule scenario can stay focused on the
generate-env-vars role path.
"""
from __future__ import annotations


def org_galaxy_credential_names(
    *,
    galaxy_setup_enabled: bool,
    hub_token: str,
    credentials: list[dict],
) -> list[str]:
    """Return org-attached Galaxy credential names in Contoller search order.

    Keep in sync with aap_config_vars.yml.j2 organization galaxy_credentials
    loop (enabled + attach_to_org + hub token + non-empty name, sorted by
    ``order``).
    """
    if not galaxy_setup_enabled:
        return []
    if not str(hub_token or "").strip():
        return []

    ordered = sorted(
        credentials,
        key=lambda item: item.get("order", 0),
    )
    selected = []
    for credential in ordered:
        enabled = credential.get("enabled", True)
        attach = credential.get("attach_to_org", True)
        name = str(credential.get("name") or "").strip()
        if enabled and attach and name:
            selected.append(name)
    return selected


FIXTURE_CREDENTIALS = [
    {
        "name": "Local Hub",
        "enabled": True,
        "attach_to_org": True,
        "order": 1,
    },
    {
        "name": "Ansible Galaxy",
        "enabled": False,
        "attach_to_org": True,
        "order": 2,
    },
    {
        "name": "Unattached Hub",
        "enabled": True,
        "attach_to_org": False,
        "order": 3,
    },
]


def test_molecule_fixture_attaches_only_local_hub() -> None:
    assert org_galaxy_credential_names(
        galaxy_setup_enabled=True,
        hub_token="fixture-not-a-secret",
        credentials=FIXTURE_CREDENTIALS,
    ) == ["Local Hub"]


def test_disabled_galaxy_setup_attaches_nothing() -> None:
    assert org_galaxy_credential_names(
        galaxy_setup_enabled=False,
        hub_token="token",
        credentials=FIXTURE_CREDENTIALS,
    ) == []


def test_missing_hub_token_attaches_nothing() -> None:
    assert org_galaxy_credential_names(
        galaxy_setup_enabled=True,
        hub_token="  ",
        credentials=FIXTURE_CREDENTIALS,
    ) == []


def test_order_controls_search_sequence() -> None:
    credentials = [
        {"name": "Second", "enabled": True, "attach_to_org": True, "order": 20},
        {"name": "First", "enabled": True, "attach_to_org": True, "order": 10},
    ]
    assert org_galaxy_credential_names(
        galaxy_setup_enabled=True,
        hub_token="token",
        credentials=credentials,
    ) == ["First", "Second"]
