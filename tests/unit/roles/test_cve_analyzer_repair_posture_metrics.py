"""Regression: standalone repair_posture_metrics action contracts."""
from __future__ import annotations

from pathlib import Path

ROLE = Path(__file__).resolve().parents[3] / "roles/cve_analyzer"
PREFLIGHT = ROLE / "tasks/preflight.yml"
MAIN = ROLE / "tasks/main.yml"
REPAIR = ROLE / "tasks/repair_posture_metrics.yml"
VERIFY = ROLE / "tasks/verify_ns_metrics_pipeline.yml"
DISCOVER = ROLE / "tasks/discover_ns_metrics_resources.yml"
ENSURE_GAUGES = ROLE / "tasks/ensure_posture_metrics_gauges.yml"
DEFAULTS = ROLE / "defaults/main.yml"
JT = (
    Path(__file__).resolve().parents[3]
    / "roles/bootstrap_controller/files/job_templates"
    / "ado-cve-analyzer-repair-posture-metrics-bootstrap.jt.yml"
)
WF = (
    Path(__file__).resolve().parents[3]
    / "roles/bootstrap_controller/files/workflows"
    / "ado-cve-analyzer-workflow-bootstrap.wf.yml"
)


def test_preflight_allows_repair_action() -> None:
    text = PREFLIGHT.read_text()
    assert "'repair_posture_metrics'" in text
    assert "cve_analyzer_repair_mode" in text


def test_defaults_include_repair_mode_and_input_dir() -> None:
    text = DEFAULTS.read_text()
    assert "cve_analyzer_repair_mode: repair" in text
    assert "cve_analyzer_metrics_input_dir" in text


def test_main_wires_repair_phase_not_acs_export() -> None:
    text = MAIN.read_text()
    assert "repair_posture_metrics.yml" in text
    assert "Repair Posture Metrics" in text
    # Repair must not be gated with fetch/auth export lists.
    auth = text.split("RHACS Authentication")[1].split("Skip RHACS Authentication")[0]
    assert "repair_posture_metrics" not in auth


def test_repair_reuses_shared_tasks() -> None:
    text = REPAIR.read_text()
    assert "discover_ns_metrics_resources.yml" in text
    assert "publish_ns_metrics.yml" in text
    assert "resolve_prometheus_datasource_uid.yml" in text
    assert "verify_ns_metrics_pipeline.yml" in text
    assert "get_url" not in text
    assert "fetch_export" not in text
    assert "ACS export" in text


def test_repair_never_publishes_grafana_dashboard() -> None:
    text = REPAIR.read_text()
    assert "publish_grafana_dashboard" not in text
    assert "publish_rhacs_posture" not in text
    assert "rhacs-vuln-dashboard.json" not in text


def test_repair_supports_durable_input_dir() -> None:
    text = REPAIR.read_text()
    assert "cve_analyzer_metrics_input_dir" in text
    assert "do not share /tmp" in text.lower() or "do not share /tmp" in text


def test_repair_fails_without_gauge_source_message() -> None:
    text = REPAIR.read_text()
    assert "Prerequisite" in text or "prerequisite" in text.lower()
    gauges = ENSURE_GAUGES.read_text()
    assert "Refusing empty posture metrics SUCCESS" in gauges


def test_verify_checks_four_resources_and_endpoint() -> None:
    text = VERIFY.read_text()
    assert "ConfigMap" in text
    assert "Deployment" in text
    assert "ServiceMonitor" in text
    assert "cve_posture_findings" in text
    assert "k8s_exec" in text
    assert "api/ds/query" in text


def test_discover_covers_four_kinds() -> None:
    text = DISCOVER.read_text()
    assert "kind: ConfigMap" in text
    assert "kind: Deployment" in text
    assert "kind: Service" in text
    assert "kind: ServiceMonitor" in text


def test_jt_seed_and_not_in_workflow() -> None:
    jt = JT.read_text()
    assert "cve_analyzer_action: repair_posture_metrics" in jt
    assert "cve_analyzer_repair_mode" in jt
    assert "cve_analyzer_metrics_input_dir" in jt
    assert "Not part of the CVE Analyzer workflow" in jt
    assert "repair_posture_metrics" not in WF.read_text()
    assert "Repair Posture Metrics" not in WF.read_text()


def test_modes_repair_and_verify() -> None:
    text = REPAIR.read_text()
    assert "cve_analyzer_repair_mode_effective == 'repair'" in text
    assert "'verify'" in text
