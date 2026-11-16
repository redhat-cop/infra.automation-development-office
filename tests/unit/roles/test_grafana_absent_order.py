"""Grafana absent must remove the instance before the namespace."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAYBOOK = (
    ROOT
    / "roles/bootstrap_generate_playbook_repo/files/playbooks/grafana"
    / "ado-deploy-install-bootstrap.yml"
)
DELETE = ROOT / "roles/grafana_install/tasks/delete-grafana-operator.yml"
NAMESPACE = ROOT / "roles/ocp_namespace/tasks/main.yml"


def test_absent_removes_instance_before_namespace() -> None:
    text = PLAYBOOK.read_text(encoding="utf-8")
    assert "ADO | Remove Grafana instance" in text
    assert "ADO | Delete Grafana namespace" in text
    assert text.index("ADO | Remove Grafana instance") < text.index(
        "ADO | Unsubscribe Grafana operator"
    )
    assert text.index("ADO | Unsubscribe Grafana operator") < text.index(
        "ADO | Delete Grafana OperatorGroup"
    )
    assert text.index("ADO | Delete Grafana OperatorGroup") < text.index(
        "ADO | Delete Grafana namespace"
    )
    present = text.index("ADO | Ensure Grafana namespace exists")
    absent = text.index("ADO | Remove Grafana instance")
    assert present < absent
    assert "ocp_namespace_advanced_cleanup" not in text


def test_grafana_absent_waits_for_cr() -> None:
    text = DELETE.read_text(encoding="utf-8")
    assert "Wait until Grafana custom resource is gone" in text
    assert text.index("Delete Grafana instance using Operator") < text.index(
        "Wait until Grafana custom resource is gone"
    )
    assert text.index("Wait until Grafana custom resource is gone") < text.index(
        "Fail if Grafana custom resource is still present"
    )
    assert "grafana_install_cr_delete_retries" in text


def test_ocp_namespace_waits_until_gone_after_delete() -> None:
    text = NAMESPACE.read_text(encoding="utf-8")
    assert "Wait for namespace to finish deleting" in text
    assert "Brief settle after delete before presence check" not in text
    assert "ocp_namespace_terminating_retries" in text
    wait = text.index("Wait for namespace to finish deleting")
    fail = text.index("Fail when namespace remains after delete")
    assert wait < fail
