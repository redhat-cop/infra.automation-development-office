"""Regression: Findings over time metrics scrape stack + handoff contracts.

Covers the Preprod failure mode: Dashboard Build wrote cve_posture.prom but
Metrics Publish required a pre-existing ConfigMap and soft-failed, so
ConfigMap/Deployment/Service/ServiceMonitor never appeared.
"""
from __future__ import annotations

from pathlib import Path

ROLE = Path(__file__).resolve().parents[3] / "roles/cve_analyzer"
POSTURE = ROLE / "tasks/publish_rhacs_posture.yml"
NS_METRICS = ROLE / "tasks/publish_ns_metrics.yml"
ENSURE = ROLE / "tasks/ensure_ns_metrics_workload.yml"
ENSURE_GAUGES = ROLE / "tasks/ensure_posture_metrics_gauges.yml"
RESOLVE_DS = ROLE / "tasks/resolve_prometheus_datasource_uid.yml"
MAIN = ROLE / "tasks/main.yml"
DEFAULTS = ROLE / "defaults/main.yml"
WF = (
    Path(__file__).resolve().parents[3]
    / "roles/bootstrap_controller/files/workflows"
    / "ado-cve-analyzer-workflow-bootstrap.wf.yml"
)


def test_ensure_workload_defines_all_four_resources() -> None:
    text = ENSURE.read_text()
    assert "kind: ConfigMap" in text
    assert "kind: Deployment" in text
    assert "kind: Service" in text
    assert "kind: ServiceMonitor" in text
    assert "state: present" in text
    assert "cve_analyzer_ns_metrics_textfile" in text
    assert "cve_posture.prom" in text  # durable handoff key


def test_posture_reuses_publish_ns_metrics_not_update_only() -> None:
    text = POSTURE.read_text()
    assert "include_tasks: publish_ns_metrics.yml" in text
    assert "Not creating a second metrics workload" not in text
    assert "Fail metrics publish when ConfigMap is missing" not in text


def test_posture_resolves_prometheus_datasource_uid() -> None:
    text = POSTURE.read_text()
    assert "resolve_prometheus_datasource_uid.yml" in text
    assert "cve_analyzer_prometheus_datasource_uid_resolved" in text
    resolve = RESOLVE_DS.read_text()
    assert "Openshift-Prod" in resolve  # mentioned only as what we refuse to invent
    assert "refusing to guess" in resolve.lower() or "refusing to" in resolve.lower()
    assert "exactly one" in resolve.lower() or "only Prometheus" in resolve


def test_posture_fails_controller_job_on_metrics_failed() -> None:
    text = POSTURE.read_text()
    assert "METRICS_FAILED" in text
    assert "Refusing SUCCESS" in text or "Fail Contoller job when metrics" in text
    assert "ansible.builtin.fail:" in text


def test_publish_ns_metrics_preserves_configmap_across_jobs() -> None:
    text = NS_METRICS.read_text()
    assert "Lookup existing metrics ConfigMap (preserve prior gauges)" in text
    assert "include_tasks: ensure_posture_metrics_gauges.yml" in text
    assert "include_tasks: ensure_ns_metrics_workload.yml" in text
    assert "cve_posture_findings{" in text
    assert "cve_posture_findings_by_cluster{" in text
    assert "cve_posture_findings_by_ns{" in text
    assert "METRICS_PUBLISHED" in text


def test_gauge_handoff_order_local_cm_csv() -> None:
    text = ENSURE_GAUGES.read_text()
    assert "Restore posture gauges from ConfigMap handoff key" in text
    assert "Rebuild posture gauges from scrubbed CSV" in text
    assert "get_url" not in text
    assert "shared /tmp" in text
    assert "Refusing empty posture metrics SUCCESS" in text


def test_workflow_documents_tmp_handoff() -> None:
    text = WF.read_text()
    assert "do not share /tmp" in text
    assert "ConfigMap" in text
    assert "scrubbed CSV" in text


def test_main_skips_duplicate_ns_metrics_after_posture_publish() -> None:
    text = MAIN.read_text()
    assert "METRICS_PUBLISHED" in text
    assert "!= 'METRICS_PUBLISHED'" in text


def test_merge_script_still_covers_three_metric_families() -> None:
    merge = (ROLE / "files/merge_posture_metrics.py").read_text()
    assert 'METRIC = "cve_posture_findings"' in merge
    assert "cve_posture_findings_by_cluster" in merge
    assert "cve_posture_findings_by_ns" in merge


def test_no_promql_contract_change_in_builder() -> None:
    builder = (ROLE / "files/build_rhacs_vuln_dashboard.py").read_text()
    assert 'job="cve-analyzer-ns-metrics"' in builder
    assert "last_over_time(" in builder
    assert 'POSTURE_METRIC = "cve_posture_findings"' in builder
    assert "def legacy_findings_trend_expr" in builder


def test_phase0_uid_and_title_defaults_untouched() -> None:
    text = DEFAULTS.read_text()
    assert 'cve_analyzer_vuln_dashboard_uid: ""' in text
    assert "RHACS Vulnerability Posture (ADO)" in text
