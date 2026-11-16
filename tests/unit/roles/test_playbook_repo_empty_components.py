"""Empty selected_components must not dump the full playbook catalog."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / "roles/bootstrap_generate_playbook_repo/tasks/main.yml"


def test_empty_selected_components_is_not_full_catalog() -> None:
    text = TASKS.read_text(encoding="utf-8")
    dump_start = text.find("bootstrap_generate_playbook_repo_dump_catalog:")
    dump_block = text[dump_start:text.find("bootstrap_generate_playbook_repo_empty_selection:")]
    assert "length == 0" not in dump_block
    assert "is not defined" in dump_block
    assert "'all' in bootstrap_generate_playbook_repo_selected_components" in dump_block
    assert "bootstrap_generate_playbook_repo_empty_selection" in text
    select = text[text.find("Generate playbook repo | Select playbooks by component") :]
    select = select[: select.find("Generate playbook repo | Resolve cert_manager")]
    assert "bootstrap_generate_playbook_repo_empty_selection | bool" in select
    assert "[]" in select


def test_cert_manager_gate_follows_dump_catalog() -> None:
    text = TASKS.read_text(encoding="utf-8")
    gate = text[text.find("bootstrap_generate_playbook_repo_cert_manager_gate:"):]
    gate = gate[: gate.find("Generate playbook repo | Drop IdM ACME")]
    assert "dump_catalog" in gate
    assert "length == 0" not in gate


def test_ingress_gate_falls_back_to_preflight_when_controller_flag_unset() -> None:
    text = TASKS.read_text(encoding="utf-8")
    resolve = text[
        text.find("Generate playbook repo | Resolve cert_manager mode and ingress flag") :
    ]
    resolve = resolve[: resolve.find("Generate playbook repo | Drop IdM ACME")]
    assert "bootstrap_controller_update_default_ingress" in resolve
    assert "bootstrap_generate_env_vars_preflight.component_config.cert_manager" in resolve
    assert "bootstrap_generate_playbook_repo_cert_manager_deploy" in resolve
    assert "Drop cert-manager deploy unless explicitly selected" in text
