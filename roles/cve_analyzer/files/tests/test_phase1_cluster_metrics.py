"""Phase 1: cve_posture_findings_by_cluster + filterable Panel 11 on test UIDs."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import merge_posture_metrics as merge_mod  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402
from tests.test_filterable_rollups import CFG, ROWS  # noqa: E402

PHASE0 = "ado-rhacs-vuln-posture-phase0"
PROD = "ado-rhacs-vuln-posture"
LITE = "ado-lite"
DEV = "ado-dev"

FILTERABLE_EXPR = builder.filterable_findings_trend_expr()
HYBRID_EXPR = builder.hybrid_findings_trend_expr()
LOCKED_EXPR = builder.legacy_findings_trend_expr()


def _analysis_with_metrics():
    rows = [dict(r) for r in ROWS]
    analytics.classify_rows(rows, CFG)
    analysis = analytics.build_analysis(
        rows, datetime.now(timezone.utc), CFG, "test"
    )
    by_cluster = analytics.severity_counts_by_cluster(rows)
    by_ns = analytics.severity_counts_by_ns(rows)
    analysis["metrics_severity_by_cluster"] = by_cluster
    analysis["metrics_severity_by_ns"] = by_ns
    analysis["metrics_severity_all_clusters"] = {
        "Critical": sum(c["Critical"] for c in by_cluster.values()),
        "Important": sum(c["Important"] for c in by_cluster.values()),
        "Moderate": sum(c["Moderate"] for c in by_cluster.values()),
        "Low": sum(c["Low"] for c in by_cluster.values()),
        "Total": sum(c["Total"] for c in by_cluster.values()),
    }
    analysis["cluster_scope"] = {
        "all_clusters": True,
        "available": ["ocp-dev", "prod-cluster"],
        "selected": [],
        "rows_before": len(rows),
        "rows_after": len(rows),
    }
    return analysis, rows, by_cluster, by_ns


class Phase1ClusterMetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis, cls.rows, cls.by_cluster, cls.by_ns = _analysis_with_metrics()
        cls.phase0 = builder.build_dashboard(
            cls.analysis, "Phase 0", PHASE0, lite=False
        )
        cls.prod = builder.build_dashboard(
            cls.analysis, "Production", PROD, lite=False
        )
        cls.lite = builder.build_dashboard(
            cls.analysis, "Lite", LITE, lite=True
        )
        cls.dev = builder.build_dashboard(
            cls.analysis, "Dev", DEV, lite=False
        )

    def test_unknown_cluster_label_not_dropped(self):
        rows = [
            {
                "cluster": "",
                "severity": "Critical",
                "namespace": "ns",
                "cve": "CVE-1",
            },
            {
                "cluster": None,
                "severity": "Important",
                "namespace": "ns",
                "cve": "CVE-2",
            },
            {
                "cluster": "prod-cluster",
                "severity": "Low",
                "namespace": "ns",
                "cve": "CVE-3",
            },
        ]
        counts = analytics.severity_counts_by_cluster(rows)
        self.assertIn("unknown", counts)
        self.assertEqual(counts["unknown"]["Critical"], 1)
        self.assertEqual(counts["unknown"]["Important"], 1)
        self.assertEqual(counts["unknown"]["Total"], 2)
        self.assertEqual(counts["prod-cluster"]["Low"], 1)

    def test_by_cluster_sums_to_all_cluster_total(self):
        total = self.analysis["metrics_severity_all_clusters"]["Total"]
        by_sum = sum(c["Total"] for c in self.by_cluster.values())
        self.assertEqual(by_sum, total)
        self.assertEqual(total, 4)
        self.assertEqual(self.by_cluster["prod-cluster"]["Total"], 3)
        self.assertEqual(self.by_cluster["ocp-dev"]["Total"], 1)

    def test_by_ns_sums_to_by_cluster_per_severity(self):
        for sev in builder.POSTURE_SEVERITIES:
            rolled = {}
            for (cluster, _ns), counts in self.by_ns.items():
                rolled[cluster] = rolled.get(cluster, 0) + int(counts.get(sev, 0))
            for cluster, expected in self.by_cluster.items():
                self.assertEqual(
                    rolled.get(cluster, 0),
                    int(expected.get(sev, 0)),
                    f"{cluster}/{sev}",
                )
        self.assertEqual(
            sum(c["Total"] for c in self.by_ns.values()),
            self.analysis["metrics_severity_all_clusters"]["Total"],
        )

    def test_unknown_namespace_label_not_dropped(self):
        rows = [
            {
                "cluster": "prod-cluster",
                "severity": "Critical",
                "namespace": "",
                "cve": "CVE-1",
            },
            {
                "cluster": "prod-cluster",
                "severity": "Important",
                "namespace": None,
                "cve": "CVE-2",
            },
            {
                "cluster": "prod-cluster",
                "severity": "Low",
                "namespace": "aap",
                "cve": "CVE-3",
            },
        ]
        counts = analytics.severity_counts_by_ns(rows)
        self.assertIn(("prod-cluster", "unknown"), counts)
        self.assertEqual(counts[("prod-cluster", "unknown")]["Critical"], 1)
        self.assertEqual(counts[("prod-cluster", "unknown")]["Important"], 1)
        self.assertEqual(counts[("prod-cluster", "unknown")]["Total"], 2)
        self.assertEqual(counts[("prod-cluster", "aap")]["Low"], 1)

    def test_posture_metrics_text_emits_both(self):
        text = builder.posture_metrics_text(
            self.analysis["metrics_severity_all_clusters"],
            by_cluster=self.by_cluster,
            by_ns=self.by_ns,
        )
        self.assertIn('cve_posture_findings{severity="Total"} 4', text)
        self.assertIn(
            'cve_posture_findings_by_cluster{cluster="prod-cluster",severity="Total"} 3',
            text,
        )
        self.assertIn(
            'cve_posture_findings_by_cluster{cluster="ocp-dev",severity="Total"} 1',
            text,
        )
        self.assertIn("cve_posture_findings_by_ns{", text)
        self.assertIn('rhacs_namespace="aap"', text)
        self.assertNotIn(',namespace="', text)
        self.assertNotIn('{namespace="', text)
        # Legacy-only call still works (no by_cluster / by_ns block).
        legacy_only = builder.posture_metrics_text(
            self.analysis["metrics_severity_all_clusters"]
        )
        self.assertIn("cve_posture_findings{", legacy_only)
        self.assertNotIn("cve_posture_findings_by_cluster", legacy_only)
        self.assertNotIn("cve_posture_findings_by_ns", legacy_only)

    def test_merge_strips_both_metrics(self):
        existing = (
            "# HELP other keep\n"
            "other_metric 1\n"
            "# BEGIN cve_posture\n"
            'cve_posture_findings{severity="Total"} 99\n'
            'cve_posture_findings_by_cluster{cluster="x",severity="Total"} 1\n'
            'cve_posture_findings_by_ns{cluster="x",rhacs_namespace="old",severity="Total"} 1\n'
            "# END cve_posture\n"
            'cve_posture_findings{severity="Total"} 77\n'
            'cve_posture_findings_by_cluster{cluster="y",severity="Total"} 2\n'
            'cve_posture_findings_by_ns{cluster="y",rhacs_namespace="z",severity="Total"} 2\n'
        )
        block = builder.posture_metrics_text(
            {"Total": 4, "Critical": 2, "Important": 1, "Moderate": 1, "Low": 0},
            by_cluster={
                "prod-cluster": {
                    "Total": 3,
                    "Critical": 2,
                    "Important": 1,
                    "Moderate": 0,
                    "Low": 0,
                },
                "ocp-dev": {
                    "Total": 1,
                    "Critical": 0,
                    "Important": 0,
                    "Moderate": 1,
                    "Low": 0,
                },
            },
            by_ns={
                ("prod-cluster", "aap"): {
                    "Total": 3,
                    "Critical": 2,
                    "Important": 1,
                    "Moderate": 0,
                    "Low": 0,
                },
                ("ocp-dev", "openshift-gitops"): {
                    "Total": 1,
                    "Critical": 0,
                    "Important": 0,
                    "Moderate": 1,
                    "Low": 0,
                },
            },
        )
        for merge_fn in (builder.merge_posture_metrics, merge_mod.merge):
            out = merge_fn(existing, block)
            self.assertIn("other_metric 1", out)
            self.assertIn('cve_posture_findings{severity="Total"} 4', out)
            self.assertIn('cluster="prod-cluster"', out)
            self.assertIn('rhacs_namespace="aap"', out)
            self.assertNotIn("99", out)
            self.assertNotIn("77", out)
            self.assertNotIn('rhacs_namespace="old"', out)
            self.assertEqual(out.count("cve_posture_findings{severity="), 5)
            self.assertEqual(out.count("cve_posture_findings_by_ns{"), 10)

    def test_phase0_filterable_and_legacy_panels(self):
        trends = [
            p
            for p in self.phase0["panels"]
            if p.get("type") == "timeseries"
        ]
        self.assertEqual(len(trends), 2)
        filt, legacy = trends[0], trends[1]
        self.assertIn("filterable", filt["title"].lower())
        self.assertEqual(filt["targets"][0]["expr"], HYBRID_EXPR)
        self.assertEqual(filt["targets"][0]["expr"], builder.hybrid_findings_trend_expr())
        expr = filt["targets"][0]["expr"]
        self.assertIn("${cluster:pipe}", expr)
        self.assertIn("${cluster:text}", expr)
        self.assertIn("${namespace:pipe}", expr)
        self.assertIn("${namespace:text}", expr)
        self.assertIn("${namespace_match}", expr)
        self.assertNotIn("${severity:pipe}", expr)
        self.assertIn(builder.TREND_SEVERITY_FILTER, expr)
        self.assertIn("cve_posture_findings_by_ns{", expr)
        self.assertIn("August 2, 2026", filt.get("description") or "")
        self.assertIn("October 28, 2026", filt.get("description") or "")
        # Hybrid inherits 90d; fine step + higher maxDataPoints for new scrapes.
        self.assertFalse(filt.get("timeFrom"))
        self.assertEqual(filt.get("maxDataPoints"), 5000)
        self.assertEqual(filt["targets"][0].get("interval"), "1m")
        self.assertIn("legacy", legacy["title"].lower())
        self.assertEqual(legacy["targets"][0]["expr"], LOCKED_EXPR)
        self.assertEqual(legacy["targets"][0].get("interval"), "1h")
        self.assertFalse(legacy.get("timeFrom"))
        # Component still not on trend PromQL; namespace is.
        blob = json.dumps(filt)
        self.assertIn("${namespace", blob)
        self.assertNotIn("${component", blob)
        # Legacy path must stay gated behind unrestricted namespace.
        self.assertIn(builder.hybrid_namespace_unrestricted_gate_expr(), expr)

    def test_production_has_filterable_and_legacy_panels(self):
        """Production ships Panel 11 filterable + Panel 12 legacy reference."""
        trends = [
            p
            for p in self.prod["panels"]
            if p.get("type") == "timeseries"
        ]
        self.assertEqual(len(trends), 2)
        filt, legacy = trends[0], trends[1]
        self.assertIn("filterable", filt["title"].lower())
        self.assertIn("legacy", legacy["title"].lower())
        # Production is not hybrid — filterable panel never falls back to
        # all-RHACS legacy history (panel 12 owns that).
        self.assertEqual(filt["targets"][0]["expr"], FILTERABLE_EXPR)
        self.assertIn("cve_posture_findings_by_cluster", filt["targets"][0]["expr"])
        self.assertIn("cve_posture_findings_by_ns", filt["targets"][0]["expr"])
        self.assertIn("${cluster:pipe}", filt["targets"][0]["expr"])
        self.assertNotIn("${severity:pipe}", filt["targets"][0]["expr"])
        self.assertIn(builder.TREND_SEVERITY_FILTER, filt["targets"][0]["expr"])
        self.assertEqual(legacy["targets"][0]["expr"], LOCKED_EXPR)
        self.assertNotIn("${cluster:pipe}", legacy["targets"][0]["expr"])
        self.assertEqual(self.prod["uid"], PROD)
        self.assertNotEqual(self.prod["uid"], PHASE0)
        self.assertTrue(builder.phase1_filterable_trend(PROD))
        self.assertFalse(builder.phase1_hybrid_trend(PROD))

    def test_lite_hybrid_dev_by_cluster_only(self):
        lite_filt = next(
            p
            for p in self.lite["panels"]
            if "filterable" in (p.get("title") or "").lower()
        )
        self.assertEqual(lite_filt["targets"][0]["expr"], HYBRID_EXPR)
        self.assertEqual(lite_filt.get("maxDataPoints"), 5000)
        self.assertFalse(lite_filt.get("timeFrom"))
        dev_filt = next(
            p
            for p in self.dev["panels"]
            if "filterable" in (p.get("title") or "").lower()
        )
        # Dev All ≠ all RHACS — never enable legacy history branch.
        self.assertEqual(dev_filt["targets"][0]["expr"], FILTERABLE_EXPR)
        self.assertNotIn("cve_posture_findings{", dev_filt["targets"][0]["expr"])
        self.assertNotIn("${cluster:text}", dev_filt["targets"][0]["expr"])
        self.assertIn("cve_posture_findings_by_ns{", dev_filt["targets"][0]["expr"])
        self.assertIn("${namespace_match}", dev_filt["targets"][0]["expr"])
        self.assertEqual(dev_filt.get("timeFrom"), "now-7d")
        for dash in (self.lite, self.dev):
            legacy = next(
                p
                for p in dash["panels"]
                if "legacy" in (p.get("title") or "").lower()
            )
            self.assertEqual(legacy["targets"][0]["expr"], LOCKED_EXPR)

    def test_cluster_all_value_scoped(self):
        cluster = next(
            v for v in self.phase0["templating"]["list"] if v["name"] == "cluster"
        )
        # Combined / all-cluster board → both clusters + table rollup token.
        self.assertEqual(
            cluster.get("allValue"),
            "ocp-dev|prod-cluster|__ALL__",
        )
        prom = builder.prom_cluster_all_matcher(cluster["allValue"])
        self.assertEqual(prom, "ocp-dev|prod-cluster")
        self.assertNotEqual(prom, "__ALL__")
        self.assertNotIn("__ALL__", prom.split("|") if prom else [])
        prod_cluster = next(
            v for v in self.prod["templating"]["list"] if v["name"] == "cluster"
        )
        # Same All token as Phase 0 — required for additive KPI stats.
        self.assertEqual(
            prod_cluster.get("allValue"),
            "ocp-dev|prod-cluster|__ALL__",
        )

    def test_all_value_per_dashboard_scope(self):
        """All = dashboard scope only — Dev must not include prod-cluster."""
        # Dev-like: filtered to ocp-dev (tables only have ocp-dev rows).
        rows = [dict(r) for r in ROWS if r["cluster"] == "ocp-dev"]
        analytics.classify_rows(rows, CFG)
        analysis = analytics.build_analysis(
            rows, datetime.now(timezone.utc), CFG, "dev"
        )
        analysis["cluster_scope"] = {
            "all_clusters": False,
            "available": ["ocp-dev", "prod-cluster"],
            "selected": ["ocp-dev"],
            "rows_before": 4,
            "rows_after": 1,
        }
        # Full-report metrics still list both — must not leak into Grafana All.
        analysis["metrics_severity_by_cluster"] = self.by_cluster
        analysis["metrics_severity_all_clusters"] = self.analysis[
            "metrics_severity_all_clusters"
        ]
        dev = builder.build_dashboard(analysis, "Dev", DEV)
        all_value = next(
            v for v in dev["templating"]["list"] if v["name"] == "cluster"
        )["allValue"]
        self.assertEqual(all_value, "ocp-dev|__ALL__")
        self.assertEqual(builder.prom_cluster_all_matcher(all_value), "ocp-dev")
        self.assertNotIn("prod-cluster", all_value)

        # Phase 0 / Lite style with cve_analyzer_clusters=[prod-cluster].
        rows_p = [dict(r) for r in ROWS if r["cluster"] == "prod-cluster"]
        analytics.classify_rows(rows_p, CFG)
        analysis_p = analytics.build_analysis(
            rows_p, datetime.now(timezone.utc), CFG, "prod-only"
        )
        analysis_p["cluster_scope"] = {
            "all_clusters": False,
            "available": ["ocp-dev", "prod-cluster"],
            "selected": ["prod-cluster"],
            "rows_before": 4,
            "rows_after": 3,
        }
        analysis_p["metrics_severity_by_cluster"] = self.by_cluster
        phase0_prod = builder.build_dashboard(analysis_p, "Phase0", PHASE0)
        lite_prod = builder.build_dashboard(analysis_p, "Lite", LITE, lite=True)
        for dash, label in ((phase0_prod, "phase0"), (lite_prod, "lite")):
            av = next(v for v in dash["templating"]["list"] if v["name"] == "cluster")[
                "allValue"
            ]
            self.assertEqual(av, "prod-cluster|__ALL__", label)
            self.assertEqual(builder.prom_cluster_all_matcher(av), "prod-cluster", label)
            self.assertNotIn("ocp-dev", av, label)

        # Future combined board (all clusters on the board).
        combined = self.phase0
        cav = next(v for v in combined["templating"]["list"] if v["name"] == "cluster")[
            "allValue"
        ]
        self.assertEqual(cav, "ocp-dev|prod-cluster|__ALL__")
        self.assertEqual(
            builder.prom_cluster_all_matcher(cav), "ocp-dev|prod-cluster"
        )

    def test_grafana_all_never_literal_all_token_alone_when_scoped(self):
        """All selection must not expand to only __ALL__ when real clusters exist."""
        for dash in (self.phase0, self.lite, self.dev):
            av = next(v for v in dash["templating"]["list"] if v["name"] == "cluster")[
                "allValue"
            ]
            matcher = builder.prom_cluster_all_matcher(av)
            self.assertTrue(matcher, dash["uid"])
            self.assertNotEqual(matcher, "__ALL__")
            # Simulated PromQL after Grafana All → ${cluster:pipe} = allValue
            self.assertIn(matcher, av)
            self.assertTrue(av.endswith("|__ALL__") or "|__ALL__|" in av or av.endswith("__ALL__"))

    def test_severity_toolbar_hidden_kept_for_drill(self):
        """Severity dropdown removed from toolbar; hidden for Detail drill links."""
        sev = next(
            v for v in self.phase0["templating"]["list"] if v["name"] == "severity"
        )
        self.assertTrue(sev.get("multi"))
        self.assertEqual(sev.get("hide"), 2)
        self.assertEqual(sev.get("allValue"), builder.TREND_SEVERITY_FILTER)
        prod_sev = next(
            v for v in self.prod["templating"]["list"] if v["name"] == "severity"
        )
        self.assertTrue(prod_sev.get("multi"))
        self.assertEqual(prod_sev.get("hide"), 2)
        self.assertEqual(prod_sev.get("allValue"), builder.TREND_SEVERITY_FILTER)

    def test_namespace_all_value_scoped_on_phase1(self):
        ns = next(v for v in self.phase0["templating"]["list"] if v["name"] == "namespace")
        self.assertTrue(ns.get("allValue", "").endswith("|__ALL__") or ns.get("allValue") == "__ALL__")
        self.assertIn("aap", ns.get("allValue") or "")
        self.assertNotEqual(ns.get("allValue"), "aap")  # must be multi / All token
        prod_ns = next(
            v for v in self.prod["templating"]["list"] if v["name"] == "namespace"
        )
        self.assertTrue(
            (prod_ns.get("allValue") or "").endswith("|__ALL__")
            or (prod_ns.get("allValue") or "") == "__ALL__"
        )
        self.assertIn("aap", prod_ns.get("allValue") or "")

    def test_hybrid_path_matrix_gates(self):
        """Documented selection → metric family via PromQL gates (string-level)."""
        expr = builder.hybrid_findings_trend_expr()
        self.assertIn(builder.POSTURE_METRIC + "{", expr)
        self.assertIn(builder.POSTURE_METRIC_BY_CLUSTER + "{", expr)
        self.assertIn(builder.POSTURE_METRIC_BY_NS + "{", expr)
        # Legacy only when both cluster All and namespace unrestricted gates hold.
        self.assertIn(builder.hybrid_findings_trend_gate_expr(), expr)
        self.assertIn(builder.hybrid_namespace_unrestricted_gate_expr(), expr)
        # by_ns always applies both namespace selectors.
        by_ns = builder._trend_by_ns_expr()
        self.assertIn('rhacs_namespace=~"${namespace:pipe}"', by_ns)
        self.assertIn('rhacs_namespace=~"${namespace_match}"', by_ns)
        self.assertNotIn(',namespace=~"', by_ns)
        self.assertNotIn('{namespace=~"', by_ns)
        # Dev never references legacy family.
        dev_expr = builder.filterable_findings_trend_expr()
        self.assertNotIn(
            'cve_posture_findings{job="cve-analyzer-ns-metrics"',
            dev_expr,
        )

    def test_no_duplicate_all_counting_in_prom_sample(self):
        """Selecting All must sum real cluster labels — __ALL__ is not a Prom label."""
        text = builder.posture_metrics_text(
            self.analysis["metrics_severity_all_clusters"],
            by_cluster=self.by_cluster,
        )
        self.assertNotIn('cluster="__ALL__"', text)
        all_value = builder.dashboard_cluster_all_value(["prod-cluster", "ocp-dev"])
        matcher = builder.prom_cluster_all_matcher(all_value)
        # Alphabetical — matches Grafana sort=5 and Unique ClusterKey equal-filters.
        self.assertEqual(matcher, "ocp-dev|prod-cluster")
        matching = [
            line
            for line in text.splitlines()
            if line.startswith("cve_posture_findings_by_cluster{")
            and 'severity="Total"' in line
        ]
        parts = set(matcher.split("|"))
        total = 0
        for line in matching:
            cl = line.split('cluster="', 1)[1].split('"', 1)[0]
            if cl in parts:
                total += int(line.rsplit(" ", 1)[-1])
        self.assertEqual(total, 4)

    def test_dashboard_json_under_16mb(self):
        for name, dash in (
            ("phase0", self.phase0),
            ("prod", self.prod),
            ("lite", self.lite),
            ("dev", self.dev),
        ):
            body = {
                "dashboard": dash,
                "overwrite": True,
                "message": "phase1 local",
                "folderUid": "Security-folder",
            }
            size = len(json.dumps(body).encode("utf-8"))
            self.assertLess(size, 16 * 1024 * 1024, name)

    def test_analyze_paths_emits_by_cluster_from_full_report(self):
        import csv

        payload = analytics.OCP_DEFAULT_REPO
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scrub.csv"

            def crow(cve: str, cluster: str, severity: str) -> dict:
                return {
                    "CVE": cve,
                    "Severity": severity,
                    "Cluster": cluster,
                    "Image": f"{payload}@sha256:{cve[-1] * 64}",
                    "Namespace": "openshift-apiserver",
                    "Discovered At": "2026-09-01T00:00:00Z",
                    "AgeDays": "40",
                }

            with path.open("w", newline="", encoding="utf-8") as fh:
                fields = list(crow("CVE-1", "prod", "Critical").keys())
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerow(crow("CVE-1", "prod", "Critical"))
                writer.writerow(crow("CVE-2", "prod-infra", "Important"))
                writer.writerow(crow("CVE-3", "prod-infra", "Critical"))

            analysis = analytics.analyze_paths(
                path,
                None,
                FILES / "image_families.yaml",
                report_date=datetime(2026, 10, 28, tzinfo=timezone.utc),
                clusters=["prod"],
            )
        # Dashboard scoped to prod, metrics still full report.
        self.assertEqual(analysis["cluster_scope"]["rows_after"], 1)
        self.assertEqual(analysis["metrics_severity_all_clusters"]["Total"], 3)
        byc = analysis["metrics_severity_by_cluster"]
        self.assertEqual(byc["prod"]["Total"], 1)
        self.assertEqual(byc["prod-infra"]["Total"], 2)
        self.assertEqual(
            sum(v["Total"] for v in byc.values()),
            analysis["metrics_severity_all_clusters"]["Total"],
        )
        byns = analysis["metrics_severity_by_ns"]
        self.assertEqual(
            sum(v["Total"] for v in byns.values()),
            analysis["metrics_severity_all_clusters"]["Total"],
        )
        for sev in builder.POSTURE_SEVERITIES:
            rolled = {}
            for (cluster, _ns), counts in byns.items():
                rolled[cluster] = rolled.get(cluster, 0) + int(counts.get(sev, 0))
            for cluster, expected in byc.items():
                self.assertEqual(rolled.get(cluster, 0), int(expected.get(sev, 0)))


if __name__ == "__main__":
    unittest.main()
