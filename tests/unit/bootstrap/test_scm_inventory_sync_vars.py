"""Project inventory sync must not require a manual vault credential."""

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
TASKS = REPO / "roles/bootstrap_controller/tasks"
TEMPLATE = (
    REPO / "roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2"
)
PATCH_JT = (
    REPO
    / "roles/bootstrap_controller/files/job_templates"
    / "ado-rhel-patch-host-bootstrap.jt.yml"
)


def source_vars_for_sync(current, source):
    """Return updated vars and whether a PATCH is required."""
    if source != "scm":
        return dict(current or {}), False
    data = dict(current or {})
    if "ANSIBLE_VARS_ENABLED" in data:
        return data, False
    data["ANSIBLE_VARS_ENABLED"] = ""
    return data, True


def vault_credential_name(org, raw=""):
    """Match the form and aap_config_vars org prefix rule."""
    prefix = (org or "ADO").strip() or "ADO"
    value = (raw or f"{prefix}-vault").strip() or f"{prefix}-vault"
    value = "-".join(value.split())
    if not value.startswith(prefix + "-"):
        value = prefix + "-" + value
    return value


def test_only_scm_sources_without_the_setting_are_patched() -> None:
    updated, changed = source_vars_for_sync({}, "scm")
    assert changed is True
    assert updated["ANSIBLE_VARS_ENABLED"] == ""

    again, changed_again = source_vars_for_sync(updated, "scm")
    assert changed_again is False
    assert again == updated

    satellite, satellite_changed = source_vars_for_sync(
        {"ansible_port": "22"},
        "satellite6",
    )
    assert satellite_changed is False
    assert "ANSIBLE_VARS_ENABLED" not in satellite

    custom, custom_changed = source_vars_for_sync(
        {"ANSIBLE_VARS_ENABLED": "host_group_vars"},
        "scm",
    )
    assert custom_changed is False
    assert custom["ANSIBLE_VARS_ENABLED"] == "host_group_vars"


def test_vault_credential_name_follows_the_organization() -> None:
    assert vault_credential_name("ADO") == "ADO-vault"
    assert vault_credential_name("DEV") == "DEV-vault"
    assert vault_credential_name("CKTEST") == "CKTEST-vault"
    assert vault_credential_name("DEV", "custom-vault") == "DEV-custom-vault"
    template = TEMPLATE.read_text()
    cred_line = template.split("controller_bootstrap_creds:", 1)[1].split("\n", 1)[0]
    assert "bootstrap_generate_env_vars_aap_cred" in cred_line
    assert "ADO-vault" not in cred_line
    assert "bootstrap_generate_env_vars_aap_org ~ '-vault'" in template


def test_direct_inventory_path_does_not_create_an_scm_source() -> None:
    template = TEMPLATE.read_text()
    sources = template.split(
        "controller_bootstrap_controller_inventory_sources:", 1
    )[1]
    sources = sources.split(
        "controller_bootstrap_controller_execution_environments:", 1
    )[0]
    assert "source: scm" not in sources
    assert "source: satellite6" in sources


def test_job_templates_still_receive_the_vault_credential() -> None:
    text = PATCH_JT.read_text()
    assert "credentials:" in text
    assert "{{ bootstrap_controller_creds }}" in text
    assert "become_enabled: true" in text
    playbook = (
        REPO
        / "roles/bootstrap_generate_playbook_repo/files/playbooks/rhel"
        / "ado-patch-host-bootstrap.yml"
    ).read_text()
    assert "become: true" in playbook


def test_scm_sync_task_patches_source_vars_only() -> None:
    ensure = (TASKS / "ensure_scm_inventory_sync_vars.yml").read_text()
    listing = (TASKS / "list_scm_inventory_sources.yml").read_text()
    attach = (TASKS / "attach_scm_inventory_sync_vars.yml").read_text()
    apply_text = (TASKS / "apply_aap_25_plus.yml").read_text()
    assert "method: PATCH" in ensure
    assert "ANSIBLE_VARS_ENABLED" in ensure
    assert "ADO-vault" not in ensure
    assert "credential:" not in ensure
    assert "source_path" not in ensure
    assert "overwrite:" not in ensure
    assert "== 'scm'" in listing
    assert "state: present" not in attach
    assert "attach_scm_inventory_sync_vars.yml" in apply_text
