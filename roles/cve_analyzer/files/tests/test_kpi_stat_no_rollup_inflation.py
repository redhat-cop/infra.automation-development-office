"""KPI stats must match old-dashboard totals (no hierarchical rollup sum).

Phase 1 Cluster/Namespace allValue is ``c1|c2|…|__ALL__``. Strict filters keep
both real labels and ``__ALL__`` rows. Summing hierarchical namespace_rollups
inflated Total ~4× vs the older board on the same CSV.

KPIs now include Ownership so SRE managed filters top counts.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402

from tests.test_filterable_rollups import CFG, ROWS  # noqa: E402


FILTER_ALL = analytics.FILTER_ALL


def _phase1_all_kpi_sum(rows: list[list]) -> int:
    """Simulate Grafana All: Age must be __ALL__; Cluster/Namespace any real or __ALL__."""
    total = 0
    for row in rows:
        _source, cluster, namespace, age, _ownership, value = row[:6]
        if age != FILTER_ALL:
            continue
        # Phase 1 allValue includes real names + __ALL__ — both match.
        total += int(value)
    return total


class KpiStatNoRollupInflationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [dict(r) for r in ROWS]
        analytics.classify_rows(rows, CFG)
        cls.analysis = analytics.build_analysis(
            rows, datetime.now(timezone.utc), CFG, "test"
        )
        cls.all_block = cls.analysis["all"]
        cls.rh_block = cls.analysis["redhat"]
        cls.nrs_block = cls.analysis["non_redhat_sources"]
        cls.true_total = len(rows)
        cls.true_critical = sum(1 for r in rows if r.get("severity") == "Critical")

    def test_additive_kpi_all_filters_match_true_finding_count(self):
        stat_rows = builder._stat_metric_rows(self.analysis, "Total")
        # Source=All sources only (default dropdown)
        all_source = [r for r in stat_rows if r[0] == builder.SOURCE_ALL]
        got = _phase1_all_kpi_sum(all_source)
        self.assertEqual(got, self.true_total)
        # Old bug: hierarchical rollups summed to ~4×
        self.assertLess(got, self.true_total * 2)

    def test_critical_kpi_all_filters_match_true_critical_count(self):
        stat_rows = builder._stat_metric_rows(self.analysis, "Critical")
        all_source = [r for r in stat_rows if r[0] == builder.SOURCE_ALL]
        got = _phase1_all_kpi_sum(all_source)
        self.assertEqual(got, self.true_critical)

    def test_no_hierarchical_rollup_rows_in_additive_kpi(self):
        stat_rows = builder._stat_metric_rows(self.analysis, "Total")
        for row in stat_rows:
            _source, cluster, namespace, age, _own, _value = row[:6]
            if age == FILTER_ALL:
                self.assertNotEqual(cluster, FILTER_ALL, row)
                self.assertNotEqual(namespace, FILTER_ALL, row)

    def test_unique_cves_all_uses_distinct_rollup_not_ownership_sum(self):
        """All filters → one Ownership/SreKey=__ALL__ distinct, not ownership sum."""
        stat_rows = builder._stat_metric_rows(self.analysis, "Unique CVEs")
        all_source = [r for r in stat_rows if r[0] == builder.SOURCE_ALL]
        self.assertGreaterEqual(len(all_source), 1)
        # Simulate Grafana All: ClusterKey=allValue, SreKey=__ALL__, Age=__ALL__
        clusters = sorted(
            {
                analytics._cluster_of(r)
                for r in ROWS
                if analytics._cluster_of(r) != FILTER_ALL
            },
            key=str.casefold,
        )
        cl_all = analytics.cluster_all_key(clusters)
        matched = [
            r
            for r in all_source
            if r[1] == cl_all and r[3] == FILTER_ALL and r[4] == FILTER_ALL
        ]
        self.assertEqual(len(matched), 1, matched)
        self.assertEqual(matched[0][5], self.all_block["unique_cves"])
        # Ownership-part Age=__ALL__ sum must be >= true distinct (overlap).
        own_parts = [
            r
            for r in all_source
            if r[1] == cl_all
            and r[3] == FILTER_ALL
            and r[4] != FILTER_ALL
            and "|" not in str(r[4])
        ]
        self.assertGreaterEqual(sum(r[5] for r in own_parts), matched[0][5])

    def test_unique_cves_per_cluster_nonzero(self):
        stat_rows = builder._stat_metric_rows(self.analysis, "Unique CVEs")
        all_source = [r for r in stat_rows if r[0] == builder.SOURCE_ALL]
        for cluster in ("prod-cluster", "ocp-dev"):
            rows = [
                r
                for r in all_source
                if r[1] == cluster and r[3] == FILTER_ALL and r[4] == FILTER_ALL
            ]
            if any(analytics._cluster_of(r) == cluster for r in ROWS):
                self.assertEqual(len(rows), 1, rows)
                self.assertGreater(rows[0][5], 0)

    def test_unique_cves_source_both_equals_all(self):
        """RH+NRS multi pipe uses All-sources distinct (not RH+NRS sum)."""
        stat_rows = builder._stat_metric_rows(self.analysis, "Unique CVEs")
        clusters = sorted(
            {
                analytics._cluster_of(r)
                for r in ROWS
                if analytics._cluster_of(r) != FILTER_ALL
            },
            key=str.casefold,
        )
        cl_all = analytics.cluster_all_key(clusters)

        def pick(source: str) -> int:
            matched = [
                r
                for r in stat_rows
                if r[0] == source
                and r[1] == cl_all
                and r[3] == FILTER_ALL
                and r[4] == FILTER_ALL
            ]
            self.assertEqual(len(matched), 1, (source, matched))
            return matched[0][5]

        self.assertEqual(pick(builder.SOURCE_BOTH), pick(builder.SOURCE_ALL))
        self.assertEqual(pick(builder.SOURCE_ALL), self.all_block["unique_cves"])

    def test_kpi_panels_wire_sre_filter(self):
        dash = builder.build_dashboard(
            self.analysis,
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            "ado-rhacs-vuln-posture-phase0",
        )
        total = next(p for p in dash["panels"] if p.get("title") == "Total")
        blob = json.dumps(total.get("transformations") or [])
        self.assertIn("${sre", blob)
        self.assertIn("Ownership", blob)
        unique = next(p for p in dash["panels"] if p.get("title") == "Unique CVEs")
        ub = json.dumps(unique.get("transformations") or [])
        self.assertIn("SreKey", ub)
        self.assertIn("ClusterKey", ub)
        sre = next(v for v in dash["templating"]["list"] if v["name"] == "sre")
        self.assertEqual(sre.get("allValue"), FILTER_ALL)

    def test_legacy_trend_promql_dedupes_scrape_churn(self):
        expr = builder.legacy_findings_trend_expr()
        self.assertIn('cve_posture_findings{job="cve-analyzer-ns-metrics"}', expr)
        self.assertIn("quantile by (severity) (0.5,", expr)
        self.assertIn("sum by (severity, pod)", expr)
        self.assertNotIn("sum by (severity) (last_over_time", expr)
        self.assertIn("last_over_time", expr)

    def test_phase1_dashboard_keeps_filterable_and_legacy_panels(self):
        dash = builder.build_dashboard(
            self.analysis,
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            "ado-rhacs-vuln-posture-phase0",
        )
        trends = [
            p
            for p in dash["panels"]
            if "Findings over time" in (p.get("title") or "")
        ]
        self.assertEqual(len(trends), 2)
        self.assertEqual(
            trends[1]["targets"][0]["expr"], builder.legacy_findings_trend_expr()
        )
        filt = trends[0]["targets"][0]["expr"]
        self.assertIn("quantile by (severity) (0.5,", filt)
        self.assertIn("sum by (severity, pod)", filt)
        self.assertIn("cve_posture_findings_by_cluster", filt)
        self.assertIn("cve_posture_findings_by_ns", filt)
        # KPI Total panel still present and uses sum calc
        total = next(p for p in dash["panels"] if p.get("title") == "Total")
        self.assertEqual(total["options"]["reduceOptions"]["calcs"], ["sum"])

    def test_production_all_value_keeps_additive_kpi_nonzero(self):
        """Bare allValue=__ALL__ zeros Total/Critical; pipe form matches CSV."""
        dash = builder.build_dashboard(
            self.analysis,
            "RHACS Vulnerability Posture (ADO)",
            "ado-rhacs-vuln-posture",
        )
        cluster = next(v for v in dash["templating"]["list"] if v["name"] == "cluster")
        namespace = next(
            v for v in dash["templating"]["list"] if v["name"] == "namespace"
        )
        self.assertNotEqual(cluster.get("allValue"), builder.FILTER_ALL)
        self.assertTrue(str(cluster.get("allValue") or "").endswith("|__ALL__"))
        self.assertTrue(str(namespace.get("allValue") or "").endswith("|__ALL__"))
        # Simulate Grafana All → ${cluster:pipe} = allValue
        all_cluster = set(str(cluster["allValue"]).split("|"))
        all_ns = set(str(namespace["allValue"]).split("|"))
        stat_rows = builder._stat_metric_rows(self.analysis, "Total")
        matched = 0
        for row in stat_rows:
            source, cl, ns, age, _own, value = row[:6]
            if source != builder.SOURCE_ALL:
                continue
            if age != FILTER_ALL:
                continue
            if cl in all_cluster and ns in all_ns:
                matched += int(value)
        self.assertEqual(matched, self.true_total)
        trends = [
            p
            for p in dash["panels"]
            if "Findings over time" in (p.get("title") or "")
        ]
        self.assertEqual(len(trends), 2)
        self.assertIn("filterable", (trends[0].get("title") or "").lower())
        self.assertIn("legacy", (trends[1].get("title") or "").lower())
        # Panel 90 Detail preserved on Full production board
        self.assertTrue(
            any(p.get("id") == builder.DETAIL_PANEL_ID for p in dash["panels"])
        )


if __name__ == "__main__":
    unittest.main()
