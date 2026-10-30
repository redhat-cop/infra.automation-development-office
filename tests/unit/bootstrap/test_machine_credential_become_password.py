"""Optional sudo password is omitted from the Machine credential when blank."""

from pathlib import Path

from jinja2 import Environment, StrictUndefined


REPO = Path(__file__).resolve().parents[3]
VAULT = (
    REPO
    / "roles/bootstrap_generate_env_vars/templates/vault_machine_cred.yml.j2"
)
CONFIG = (
    REPO
    / "roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2"
)


def render_vault(become_password):
    env = Environment(undefined=StrictUndefined, trim_blocks=False)
    template = env.from_string(VAULT.read_text())
    return template.render(
        bootstrap_generate_env_vars_preflight={
            "aap": {
                "organization": "ADO",
                "machine_credential": {
                    "name": "ADO-machine",
                    "username": "cloud-user",
                    "ssh_key_data": "",
                    "ssh_key_unlock": "",
                    "become_method": "sudo",
                    "become_username": "root",
                    "become_password": become_password,
                },
            }
        }
    )


def test_blank_sudo_password_is_omitted() -> None:
    rendered = render_vault("   ")
    assert "become_password" not in rendered
    assert "vault_machine_credential_become_username:" in rendered


def test_sudo_password_is_written_when_set() -> None:
    rendered = render_vault("sudo-secret")
    assert "vault_machine_credential_become_password: >-" in rendered
    assert "sudo-secret" in rendered


def test_controller_input_is_conditional() -> None:
    text = CONFIG.read_text()
    machine = text.split("credential_type: Machine", 1)[1].split(
        "credential_type:", 1
    )[0]
    assert "bootstrap_generate_env_vars_machine_become_password | length > 0" in machine
    assert "vault_machine_credential_become_password" in machine
