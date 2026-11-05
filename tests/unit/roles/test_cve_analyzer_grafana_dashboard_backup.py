"""Decision contracts for Grafana dashboard pre-publish backup.

Mirrors backup_grafana_dashboard.yml without calling Grafana.
"""
from __future__ import annotations

from pathlib import Path


def backup_decision(
    http_status: int,
    backup_dir: str,
    allow_ephemeral: bool = False,
) -> str:
    """Return expected backup outcome for a lookup status + dir config."""
    if http_status not in (200, 404):
        return "fail_lookup"
    if http_status == 404:
        return "new"
    if not (backup_dir or "").strip():
        return "fail_missing_dir"
    cleaned = backup_dir.strip()
    if cleaned.startswith("/tmp") and not allow_ephemeral:
        if cleaned == "/tmp" or cleaned.startswith("/tmp/"):
            return "fail_ephemeral"
    return "backup"


def test_nonexistent_dashboard_skips_backup() -> None:
    assert backup_decision(404, "") == "new"
    assert backup_decision(404, "/var/lib/cve-analyzer/grafana-backups") == "new"


def test_existing_dashboard_requires_persistent_dir() -> None:
    assert backup_decision(200, "") == "fail_missing_dir"
    assert backup_decision(200, "/tmp/backups") == "fail_ephemeral"
    assert backup_decision(200, "/tmp") == "fail_ephemeral"
    assert (
        backup_decision(200, "/tmp/backups", allow_ephemeral=True) == "backup"
    )


def test_existing_dashboard_backs_up_to_durable_path() -> None:
    assert (
        backup_decision(200, "/var/lib/cve-analyzer/grafana-backups") == "backup"
    )


def test_unexpected_api_status_fails() -> None:
    assert backup_decision(500, "/var/lib/cve-analyzer/grafana-backups") == (
        "fail_lookup"
    )
    assert backup_decision(401, "/var/lib/cve-analyzer/grafana-backups") == (
        "fail_lookup"
    )


def test_backup_path_layout() -> None:
    uid = "ado-rhacs-vuln-posture-phase0"
    root = "/var/lib/cve-analyzer/grafana-backups"
    version = 41
    stamp = "20261101T131500Z"
    path = f"{root}/{uid}/{uid}-v{version}-{stamp}.json"
    meta = f"{root}/{uid}/{uid}-v{version}-{stamp}.meta.json"
    assert path.endswith(".json")
    assert meta.endswith(".meta.json")
    assert uid in path
    assert "/tmp" not in path


def test_backup_task_file_present() -> None:
    role = Path(__file__).resolve().parents[3] / "roles/cve_analyzer"
    assert (role / "tasks/backup_grafana_dashboard.yml").is_file()
