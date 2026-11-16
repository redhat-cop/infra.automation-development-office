"""Deploy RHBK Client must not delete Keycloak clients by omission."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROLE_MAIN = ROOT / "roles/rhbk_client/tasks/main.yml"
MANAGE_PLAYBOOK = (
    ROOT
    / "roles/bootstrap_generate_playbook_repo/files/playbooks/rhbk"
    / "ado-manage-client-bootstrap.yml"
)
DELETE_TASKS = ROOT / "roles/rhbk_client/tasks/rhbk_delete_client.yml"


def test_manage_client_playbook_never_sets_state_absent() -> None:
    text = MANAGE_PLAYBOOK.read_text(encoding="utf-8")
    assert "include_role" in text
    assert "rhbk_client" in text
    assert "state: absent" not in text
    # Work list comes only from rhbk_clients / rhbk_client; omitted ids are skipped.
    assert "rhbk_clients" in text
    assert "dict2items" in text


def test_rhbk_client_deletes_only_when_state_absent() -> None:
    text = ROLE_MAIN.read_text(encoding="utf-8")
    assert 'when: state == "absent"' in text
    delete_block = text[
        text.index("Delete RHBK client") : text.index("Delete RHBK client") + 200
    ]
    assert "rhbk_delete_client.yml" in delete_block
    assert 'state == "absent"' in delete_block
    create = text[: text.index("Delete RHBK client")]
    assert 'state == "present"' in create
    assert "rhbk_delete_client.yml" not in create


def test_delete_task_file_is_not_imported_by_manage_playbook() -> None:
    playbook = MANAGE_PLAYBOOK.read_text(encoding="utf-8")
    assert "rhbk_delete_client" not in playbook
    assert DELETE_TASKS.exists()
