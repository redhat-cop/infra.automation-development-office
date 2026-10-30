"""Optional workflow membership and the system-role catalog."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
CATALOG = (
    REPO
    / "roles/bootstrap_generate_playbook_repo/files/rhel_system_roles_catalog.yml"
)
WORKFLOW = (
    REPO
    / "roles/bootstrap_controller/files/workflows"
    / "ado-openshift-workflow-bootstrap.wf.yml"
)
PRUNE = REPO / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"
README = (
    REPO
    / "roles/bootstrap_generate_playbook_repo/files/playbooks"
    / "rhel_system_roles/README.md"
)
RHEL_WF = (
    REPO
    / "roles/bootstrap_controller/files/workflows"
    / "ado-rhel-workflow-bootstrap.wf.yml"
)


def test_profiles_only_use_catalog_apps() -> None:
    data = yaml.safe_load(CATALOG.read_text())
    apps = {item["app"] for item in data["rhel_system_roles_catalog"]}
    assert len(apps) == 34
    profiles = data["rhel_system_role_profiles"]
    assert set(profiles) == {"minimal", "standard", "security", "custom"}
    assert profiles["custom"] == []
    for name, selected in profiles.items():
        assert set(selected) <= apps, name
    assert "system_role_firewall" in profiles["standard"]
    assert "system_role_firewall" in profiles["security"]
    assert "system_role_network" not in profiles["minimal"]


def test_storage_and_pull_secret_nodes_are_optional() -> None:
    text = WORKFLOW.read_text()
    assert "ADO | Install NFS CSI Storage" in text
    assert "ADO | Install Synology iSCSI CSI Storage" in text
    assert "ADO | Update pull secret" in text
    prune = PRUNE.read_text()
    assert "Install NFS CSI" in prune
    assert "bootstrap_controller_nfs_workflow_flag" in prune
    assert "bootstrap_controller_pull_secret_workflow_flag" in prune
    assert 'optional_flags.get(node.get("identifier"), "true") == "true"' in prune


def test_system_roles_join_rhel_workflow_only_when_flagged() -> None:
    prune = PRUNE.read_text()
    assert 'workflow.get("name") == "ADO | RHEL Workflow"' in prune
    assert "bootstrap_controller_system_roles_workflow_flag" in prune
    assert "ADO | RHEL System Role |" in prune
    assert "RHEL STIG Hardening" in RHEL_WF.read_text()
    readme = README.read_text()
    assert "ansible-playbook" in readme
    assert "does not require" in readme
    assert "job template" in readme
