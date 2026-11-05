"""RHACS posture Dashboard Build / Grafana publish reliability contracts.

AAP must not report SUCCESS when Dashboard Build failed or when a static
sample would silently overwrite Grafana. Production UID stays protected.
"""
from __future__ import annotations

from pathlib import Path

ROLE = Path(__file__).resolve().parents[3] / "roles/cve_analyzer"
POSTURE = ROLE / "tasks/publish_rhacs_posture.yml"
BACKUP = ROLE / "tasks/backup_grafana_dashboard.yml"
DEFAULTS = ROLE / "defaults/main.yml"
NS_METRICS = ROLE / "tasks/publish_ns_metrics.yml"


def test_dashboard_build_captures_error_and_fails_job() -> None:
    text = POSTURE.read_text()
    assert "Capture dashboard builder failure text" in text
    assert "Fail the job when Dashboard Build failed" in text
    assert "cve_analyzer_dashboard_build_error" in text
    assert "Fall back to static RHACS posture sample" not in text
    assert "falling back to static sample" not in text


def test_never_materialize_sample_for_grafana_publish() -> None:
    text = POSTURE.read_text()
    assert "Materialize static RHACS posture sample when data.json missing" in text
    # Task kept for history but must be disabled (when: false).
    idx = text.index("Materialize static RHACS posture sample when data.json missing")
    chunk = text[idx : idx + 400]
    assert "when: false" in chunk


def test_skip_publish_without_live_dashboard_build() -> None:
    text = POSTURE.read_text()
    assert "Do not overwrite Grafana without a successful live Dashboard Build" in text
    assert "No sample fallback" in text
    assert "cve_analyzer_posture_live_ok" in text


def test_verify_grafana_uid_and_title_after_publish() -> None:
    text = POSTURE.read_text()
    assert "Verify published posture dashboard exists in Grafana" in text
    assert "Assert Grafana verify returned configured UID and title" in text
    # Prefer search probe (small JSON) over full /api/dashboards/uid body.
    assert "api/search?dashboardUIDs=" in text
    assert "cve_analyzer_vuln_dashboard_uid" in text
    assert "equalto', cve_analyzer_vuln_dashboard_uid | trim)" in text


def test_production_uid_protected_from_lite_compare() -> None:
    text = POSTURE.read_text()
    assert "Refuse Lite/compare publish to production UID" in text
    assert "ado-rhacs-vuln-posture" in text
    assert "Refusing anything that could touch production" in text


def test_publish_ns_metrics_no_recursive_require_flag() -> None:
    text = NS_METRICS.read_text()
    assert "when: cve_analyzer_require_posture_metrics is not defined" in text
    assert "cve_analyzer_require_posture_metrics\n        | default(" not in text


def test_publish_path_includes_grafana_dashboard_backup() -> None:
    text = POSTURE.read_text()
    assert "Backup existing posture dashboard before Grafana overwrite" in text
    assert "backup_grafana_dashboard.yml" in text
    # Backup runs after lookup, before the publisher stage / overwrite.
    assert text.index("Lookup existing posture dashboard by UID") < text.index(
        "Backup existing posture dashboard before Grafana overwrite"
    )
    assert text.index(
        "Backup existing posture dashboard before Grafana overwrite"
    ) < text.index("Stage Grafana dashboard publisher")


def test_backup_task_file_contracts() -> None:
    text = BACKUP.read_text()
    # Existence via search (200); missing UID normalized to 404 locally.
    assert "api/search?dashboardUIDs=" in text
    assert "status_code: [200]" in text
    assert "not in [200, 404]" in text
    assert "cve_analyzer_grafana_dashboard_backup_dir" in text
    assert "Record new Grafana dashboard (nothing to backup)" in text
    assert "Require persistent backup path for existing dashboard" in text
    assert "Fail when existing Grafana dashboard cannot be backed up" in text
    assert "/tmp" in text
    assert "cve_analyzer_grafana_dashboard_backup_allow_ephemeral" in text
    # Credentials must not be written into backup content.
    assert "GRAFANA_PASSWORD" not in text
    assert "password:" not in text.lower().split("write grafana dashboard backup")[-1]
    assert "cve_analyzer_grafana_password" not in text
    assert "to_nice_json" in text or "get_url" in text
    assert ".meta.json" in text


def test_backup_dir_defaults_documented() -> None:
    text = DEFAULTS.read_text()
    assert "cve_analyzer_grafana_dashboard_backup_dir: \"\"" in text
    assert "cve_analyzer_grafana_dashboard_backup_allow_ephemeral: false" in text
    assert "Persistent Grafana JSON backups" in text
