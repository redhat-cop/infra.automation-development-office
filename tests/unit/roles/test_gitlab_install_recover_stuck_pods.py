"""gitlab_install recovers pods stuck Terminating on NotReady nodes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECOVER = ROOT / "roles/gitlab_install/tasks/recover-stuck-pods.yml"
MAIN = ROOT / "roles/gitlab_install/tasks/main.yml"
DEFAULTS = ROOT / "roles/gitlab_install/defaults/main.yml"


def test_present_imports_recover_stuck_pods() -> None:
    text = MAIN.read_text(encoding="utf-8")
    assert "recover-stuck-pods.yml" in text
    assert "gitlab_install_recover_stuck_pods" in text


def test_recover_force_deletes_terminating_pods_on_notready_nodes() -> None:
    text = RECOVER.read_text(encoding="utf-8")
    assert "deletionTimestamp" in text
    assert "node.kubernetes.io/unreachable" in text
    assert "grace_period_seconds: 0" in text
    assert "kind: Pod" in text
    assert "gitlab_install_stuck_pod_names" in text
    assert ").deployment | default({})" not in text


def test_recover_stuck_pods_defaults_on() -> None:
    text = DEFAULTS.read_text(encoding="utf-8")
    assert "gitlab_install_recover_stuck_pods: true" in text
