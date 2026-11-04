#!/usr/bin/env python3
"""Regression contracts for Findings over time metrics publish path."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROLE = Path(__file__).resolve().parents[2]
TASKS = ROLE / "tasks"


def _load(name: str) -> str:
    return (TASKS / name).read_text(encoding="utf-8")


class MetricsPipelineContractTests(unittest.TestCase):
    def test_posture_reuses_publish_ns_metrics(self) -> None:
        text = _load("publish_rhacs_posture.yml")
        self.assertIn("publish_ns_metrics.yml", text)
        self.assertNotIn("Not creating a second metrics workload", text)
        self.assertIn("cve_analyzer_require_posture_metrics: true", text)

    def test_metrics_failure_blocks_grafana_publish(self) -> None:
        text = _load("publish_rhacs_posture.yml")
        self.assertIn("Fail before Grafana when metrics publish failed", text)
        self.assertIn(
            "Refuse Grafana publish when metrics status is METRICS_FAILED",
            text,
        )
        # Metrics block must appear before Grafana Publish start.
        metrics_idx = text.index("Publish posture gauges via metrics scrape stack")
        grafana_idx = text.index("Start Grafana Publish")
        refuse_idx = text.index(
            "Refuse Grafana publish when metrics status is METRICS_FAILED"
        )
        self.assertLess(metrics_idx, refuse_idx)
        self.assertLess(refuse_idx, grafana_idx)

    def test_publish_ns_metrics_creates_full_stack(self) -> None:
        publish = _load("publish_ns_metrics.yml")
        workload = _load("ensure_ns_metrics_workload.yml")
        for needle in (
            "ensure_posture_metrics_gauges.yml",
            "ensure_ns_metrics_workload.yml",
            "cve_posture.prom",
            "cve_posture_findings{",
            "cve_posture_findings_by_cluster{",
            "cve_posture_findings_by_ns{",
            "METRICS_PUBLISHED",
        ):
            self.assertIn(needle, publish, msg=f"missing {needle}")
        for needle in (
            "kind: ConfigMap",
            "kind: Deployment",
            "kind: Service",
            "kind: ServiceMonitor",
        ):
            self.assertIn(needle, workload, msg=f"missing {needle} in workload")

    def test_handoff_restores_from_configmap_or_scrubbed_csv(self) -> None:
        text = _load("ensure_posture_metrics_gauges.yml")
        self.assertIn("Restore posture gauges from ConfigMap handoff key", text)
        self.assertIn("Rebuild posture gauges from scrubbed CSV", text)
        self.assertIn("shared /tmp", text)
        self.assertIn("Do not assume a prior Contoller job left files under /tmp", text)

    def test_datasource_resolve_no_silent_guess(self) -> None:
        text = _load("resolve_prometheus_datasource_uid.yml")
        self.assertIn("Auto-select the only Prometheus datasource UID", text)
        self.assertIn("Fail when multiple Prometheus datasources", text)
        self.assertIn("Fail when Grafana has no Prometheus datasource", text)
        # Comment may name Openshift-Prod as the UID we refuse to invent.
        self.assertIn("Never invent Openshift-Prod", text)
        self.assertNotRegex(text, r"default\(['\"]Openshift-Prod['\"]\)")

    def test_builder_uses_resolved_datasource_uid(self) -> None:
        text = _load("publish_rhacs_posture.yml")
        self.assertIn("resolve_prometheus_datasource_uid.yml", text)
        self.assertGreaterEqual(
            text.count("cve_analyzer_prometheus_datasource_uid_resolved"),
            2,
        )
        # Empty configured UID must not be passed straight to argv.
        self.assertNotIn(
            '- "{{ cve_analyzer_prometheus_datasource_uid }}"',
            text,
        )

    def test_yaml_parses(self) -> None:
        for name in (
            "publish_ns_metrics.yml",
            "ensure_posture_metrics_gauges.yml",
            "resolve_prometheus_datasource_uid.yml",
            "publish_rhacs_posture.yml",
        ):
            with self.subTest(name=name):
                docs = list(yaml.safe_load_all(_load(name)))
                self.assertTrue(docs)


if __name__ == "__main__":
    unittest.main()
