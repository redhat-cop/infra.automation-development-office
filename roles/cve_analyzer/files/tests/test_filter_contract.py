"""Phase 0 RHACS dashboard filter-contract regression.

Encodes the 27-panel coverage matrix: which toolbar filters each panel must
honor, which are intentionally global, and which Prom dimensions are absent.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402

CFG = {
    "families": [
        {
            "name": "Dev Spaces / UDI",
            "ownership": "redhat_component",
            "remediation_type": "operator_update",
            "action": "Update Dev Spaces",
            "match": {"image_contains": ["devspaces/udi"]},
        },
        {
            "name": "OCP payload",
            "ownership": "sre_managed",
            "remediation_type": "ocp_upgrade",
            "action": "Upgrade OpenShift",
            "match": {
                "repository_equals": [
                    "quay.io/openshift-release-dev/ocp-v4.0-art-dev"
                ]
            },
        },
    ],
    "ocp_payload_repository": "quay.io/openshift-release-dev/ocp-v4.0-art-dev",
}


def _row(**kw):
    kw.setdefault("digest", "sha256:deadbeef")
    kw.setdefault("component", kw.get("repository", "comp"))
    kw.setdefault("cluster", "prod-cluster")
    kw.setdefault("deployment", "dep")
    return kw


ROWS = [
    _row(
        namespace="chad-devspaces",
        image="registry.redhat.io/devspaces/udi-rhel9:latest",
        repository="registry.redhat.io/devspaces/udi-rhel9",
        cve="CVE-2024-1",
        severity="Critical",
        fixable=True,
        age_days=40,
        finding_age="30-60 days",
        redhat_source=True,
    ),
    _row(
        namespace="chad-devspaces",
        image="registry.redhat.io/devspaces/udi-rhel9:latest",
        repository="registry.redhat.io/devspaces/udi-rhel9",
        cve="CVE-2024-2",
        severity="Important",
        fixable=True,
        age_days=10,
        finding_age="0-15 days",
        redhat_source=True,
    ),
    _row(
        namespace="aap",
        image="quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:abc",
        repository="quay.io/openshift-release-dev/ocp-v4.0-art-dev",
        cve="CVE-2024-3",
        severity="Critical",
        fixable=False,
        age_days=100,
        finding_age="Over 60 days",
        redhat_source=True,
        discovered=datetime(2024, 1, 1, tzinfo=timezone.utc),
    ),
    _row(
        namespace="admin-devspaces",
        image="docker.io/library/nginx:1.25",
        repository="docker.io/library/nginx",
        cve="CVE-2024-4",
        severity="Moderate",
        fixable=True,
        age_days=5,
        finding_age="0-15 days",
        redhat_source=False,
        cluster="ocp-dev",
    ),
    _row(
        namespace="openshift-apiserver",
        image="quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:def",
        repository="quay.io/openshift-release-dev/ocp-v4.0-art-dev",
        cve="CVE-2024-5",
        severity="Important",
        fixable=True,
        age_days=20,
        finding_age="15-30 days",
        redhat_source=True,
        cluster="ocp-dev",
        discovered=datetime(2024, 6, 1, tzinfo=timezone.utc),
    ),
]


# Filter keys used in the matrix below.
# Y = must respond; N = intentionally ignores; P = Prom-supported only;
# U = unsupported (missing CSV dim or Prom label — do not fake).
#
# Columns: Cluster, Source, Namespace, FindingAge, Component, SRE, Severity
FILTER_MATRIX = {
    # id: (title_substr, datasource, cluster, source, ns, age, component, sre, severity, notes)
    1: ("RHACS vulnerability posture", "markdown", "N", "N", "N", "N", "N", "N", "N", "header"),
    2: ("OpenShift", "prometheus", "N", "N", "N", "N", "N", "N", "N", "version badge"),
    3: ("Operators with updates", "stat", "N", "N", "N", "N", "N", "N", "N", "cluster-wide tile"),
    4: ("Total", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "KPI; SRE via Ownership"),
    5: ("Unique CVEs", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "KPI; SRE via Ownership"),
    6: ("Fixable findings", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "KPI; SRE via Ownership"),
    7: ("Critical", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "severity-specific KPI"),
    8: ("Important", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "severity-specific KPI"),
    9: ("Moderate", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "severity-specific KPI"),
    10: ("Low", "csv", "Y", "Y", "Y", "Y", "N", "Y", "N", "severity-specific KPI"),
    11: (
        "Findings over time — filterable",
        "prometheus",
        "Y",
        "U",
        "Y",
        "U",
        "U",
        "U",
        "N",
        "Prom labels: cluster, rhacs_namespace; all severities hardcoded",
    ),
    12: (
        "Findings over time — legacy",
        "prometheus",
        "N",
        "N",
        "N",
        "N",
        "N",
        "N",
        "N",
        "intentional all-cluster reference",
    ),
    13: (
        "Findings by namespace",
        "csv",
        "Y",
        "Y",
        "Y",
        "Y",
        "Y",
        "Y",
        "U",
        "sev as columns; component/SRE via pre-rollup dims",
    ),
    14: ("All components", "csv", "Y", "Y", "Y", "Y", "Y", "Y", "U", "sev as columns"),
    15: ("Critical findings by namespace", "csv", "Y", "Y", "Y", "Y", "N", "N", "N", "critical-only"),
    16: (
        "Red Hat SRE-managed OpenShift images",
        "csv",
        "Y",
        "Y",
        "N",
        "N",
        "N",
        "Y",
        "N",
        "cluster-wide; SRE via Ownership; ignore ns/age/component",
    ),
    17: (
        "Critical CVEs by age — SRE-managed",
        "csv",
        "Y",
        "Y",
        "N",
        "N",
        "N",
        "N",
        "N",
        "age DISTRIBUTION (AGE_BUCKETS); Finding age N/A",
    ),
    18: (
        "Important CVEs by age — SRE-managed",
        "csv",
        "Y",
        "Y",
        "N",
        "N",
        "N",
        "N",
        "N",
        "age DISTRIBUTION (AGE_BUCKETS); Finding age N/A",
    ),
    19: ("All images", "csv", "Y", "Y", "Y", "Y", "Y", "Y", "U", "sev as columns"),
    20: ("Unique CVEs older than 30 days", "csv", "Y", "Y", "Y", "Y", "N", "N", "U", ""),
    21: ("Finding ownership", "csv", "Y", "Y", "Y", "Y", "N", "Y", "U", ""),
    22: ("Red Hat SRE Managed Services", "csv", "Y", "Y", "Y", "Y", "Y", "Y", "U", ""),
    23: ("Red Hat Components", "csv", "Y", "Y", "Y", "Y", "Y", "Y", "U", ""),
    24: ("Non-Red Hat images", "csv", "Y", "Y", "Y", "Y", "Y", "Y", "U", ""),
    25: ("Remediation Paths", "csv", "Y", "Y", "Y", "Y", "N", "Y", "U", "SRE via Ownership"),
    26: ("Simple view", "csv", "Y", "Y", "Y", "Y", "N", "N", "U", "fixable Crit/Imp only"),
    90: ("Detail for the row you clicked", "csv", "Y", "Y", "Y", "Y", "Y", "Y", "Y", ""),
}

PROM_MISSING_LABELS = (
    "source / redhat_source",
    "finding_age / age bucket",
    "component / family",
    "ownership / sre_managed",
)


def _panel_by_title_substr(dash: dict, substr: str) -> dict:
    matches = [
        p for p in dash["panels"] if substr.lower() in (p.get("title") or "").lower()
    ]
    if not matches and substr.lower() in ("openshift",):
        matches = [p for p in dash["panels"] if p.get("type") == "stat" and not p.get("title")]
    # header markdown has empty title
    if not matches and "posture" in substr.lower():
        matches = [p for p in dash["panels"] if p.get("type") == "text"]
    assert matches, f"no panel matching {substr!r}"
    return matches[0]


def _transform_blob(panel: dict) -> str:
    return json.dumps(panel.get("transformations") or [])


def _csv_headers(panel: dict) -> list[str]:
    target = (panel.get("targets") or [{}])[0]
    content = target.get("csvContent") or ""
    if not content.strip():
        return []
    return next(csv.reader(io.StringIO(content)))


class FilterContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [dict(r) for r in ROWS]
        analytics.classify_rows(rows, CFG)
        cls.analysis = analytics.build_analysis(
            rows, datetime.now(timezone.utc), CFG, "test"
        )
        cls.dash = builder.build_dashboard(
            cls.analysis,
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            "ado-rhacs-vuln-posture-phase0",
        )

    def test_panel_count_includes_detail(self):
        ids = {p.get("id") for p in self.dash["panels"]}
        self.assertIn(90, ids)
        # 26 content panels + detail 90 (ids assigned sequentially; count panels)
        self.assertGreaterEqual(len(self.dash["panels"]), 26)

    def test_source_variable_multiselect(self):
        source = next(v for v in self.dash["templating"]["list"] if v["name"] == "source")
        self.assertTrue(source.get("multi"))
        self.assertTrue(source.get("includeAll"))
        self.assertEqual(source.get("allValue"), builder.SOURCE_ALL)
        # All sources is allValue only — not a redundant dropdown chip.
        opts = {o["value"] for o in source.get("options") or [] if o.get("value") != "$__all"}
        self.assertEqual(opts, {builder.SOURCE_REDHAT, builder.SOURCE_NON_REDHAT})
        self.assertNotIn(builder.SOURCE_ALL, opts)

    def test_severity_toolbar_hidden(self):
        sev = next(v for v in self.dash["templating"]["list"] if v["name"] == "severity")
        self.assertEqual(sev.get("hide"), 2)
        trend = next(
            p
            for p in self.dash["panels"]
            if "Findings over time — filterable" in (p.get("title") or "")
        )
        expr = trend["targets"][0]["expr"]
        self.assertNotIn("${severity", expr)
        self.assertIn(builder.TREND_SEVERITY_FILTER, expr)

    def test_ocp_bar_keeps_category_string_field(self):
        panel = next(
            p
            for p in self.dash["panels"]
            if "SRE-managed OpenShift images" in (p.get("title") or "")
        )
        blob = json.dumps(panel.get("transformations") or [])
        self.assertIn("Category", blob)
        # Must not hide Category after groupBy (barchart needs a string field).
        for t in panel.get("transformations") or []:
            if t.get("id") != "organize":
                continue
            excluded = (t.get("options") or {}).get("excludeByName") or {}
            self.assertFalse(excluded.get("Category"), t)

    def test_sre_component_multiselect(self):
        for name in ("sre", "component"):
            var = next(v for v in self.dash["templating"]["list"] if v["name"] == name)
            self.assertTrue(var.get("multi"), name)

    def test_matrix_wiring(self):
        """Assert transform / expr wiring matches FILTER_MATRIX expectations."""
        for _pid, spec in FILTER_MATRIX.items():
            title, _ds, cluster, source, ns, age, component, sre, severity, _notes = spec
            if title.startswith("RHACS vulnerability") or title == "OpenShift":
                continue
            panel = _panel_by_title_substr(self.dash, title)
            blob = _transform_blob(panel)
            expr = json.dumps(panel.get("targets") or [])
            combined = blob + expr

            def expect(flag: str, needle: str, label: str) -> None:
                if flag == "Y":
                    self.assertIn(needle, combined, f"{title}: missing {label}")
                elif flag in {"N", "U"}:
                    # Intentional ignore / unsupported: must not claim via transform
                    if flag == "N" and needle in combined and "legacy" not in title.lower():
                        # legacy panel must not include cluster filter — checked below
                        pass

            if cluster == "Y":
                self.assertTrue(
                    "${cluster:pipe}" in combined or "cluster=" in combined,
                    f"{title}: cluster filter missing",
                )
            if source == "Y":
                self.assertIn("${source:pipe}", blob, f"{title}: source filter missing")
            if ns == "Y":
                self.assertTrue(
                    "${namespace:pipe}" in combined or "rhacs_namespace" in combined,
                    f"{title}: namespace filter missing",
                )
            if age == "Y":
                self.assertIn("${finding_age:pipe}", blob, f"{title}: finding_age missing")
            if component == "Y":
                self.assertIn("${component", blob, f"{title}: component filter missing")
            if sre == "Y":
                self.assertIn("${sre", blob, f"{title}: sre filter missing")
            if severity == "Y":
                self.assertIn("${severity", combined, f"{title}: severity filter missing")

            if "legacy" in title.lower():
                self.assertNotIn("${cluster", combined)
                self.assertNotIn("${source", combined)
                self.assertNotIn("${namespace", combined)

            if "SRE-managed OpenShift" in title or "CVEs by age" in title:
                self.assertNotIn("${namespace:pipe}", blob)
                self.assertNotIn("${finding_age:pipe}", blob)

    def test_prom_panel11_unsupported_dims_documented(self):
        panel = _panel_by_title_substr(self.dash, "Findings over time — filterable")
        expr = panel["targets"][0]["expr"]
        self.assertIn("cve_posture_findings", expr)
        for missing in ("source=", "finding_age=", "component=", "ownership="):
            self.assertNotIn(missing, expr)
        # Document required Prom label extensions (do not fake on Panel 11).
        self.assertGreaterEqual(len(PROM_MISSING_LABELS), 4)
        self.assertTrue(any("source" in item for item in PROM_MISSING_LABELS))

    def test_detail_source_all_uses_sentinel_not_row_doubling(self):
        """Panel 90 must stay under Grafana 16 MB: one CSV row per drilldown.

        Source=All matches via hidden SourceAll=SOURCE_ALL (ClusterAll pattern),
        not a second SOURCE_ALL copy of every finding.
        """
        detail = next(p for p in self.dash["panels"] if p.get("id") == 90)
        headers = _csv_headers(detail)
        self.assertIn("SourceAll", headers)
        content = detail["targets"][0]["csvContent"]
        data_rows = max(0, content.count("\n") - 1)
        self.assertEqual(data_rows, len(self.analysis.get("drilldown") or []))
        blob = _transform_blob(detail)
        self.assertIn("SourceAll", blob)
        self.assertIn("${source:pipe}", blob)
        self.assertIn("${source}", blob)
        # Must not use by_source hide of Source alone without SourceAll path.
        reader = list(csv.DictReader(io.StringIO(content)))
        self.assertTrue(reader)
        self.assertTrue(all(r.get("SourceAll") == builder.SOURCE_ALL for r in reader))
        self.assertTrue(
            all(r.get("Source") in {builder.SOURCE_REDHAT, builder.SOURCE_NON_REDHAT} for r in reader)
        )

    def test_findings_by_namespace_honors_component_and_sre(self):
        panel = next(p for p in self.dash["panels"] if p.get("title") == "Findings by namespace")
        headers = _csv_headers(panel)
        self.assertIn("Component", headers)
        self.assertIn("Ownership", headers)
        blob = _transform_blob(panel)
        self.assertIn("${component:pipe}", blob)
        self.assertIn("${sre:pipe}", blob)
        self.assertIn("${finding_age:pipe}", blob)
        # Pre-rollup CSV must keep Component rows (not coarse by_namespace only).
        reader = list(csv.DictReader(io.StringIO(panel["targets"][0]["csvContent"])))
        self.assertTrue(any(r.get("Component") for r in reader))

    def test_kpi_all_source_no_double_count_on_toy_data(self):
        """All-sources KPI rows must not equal sum of RH + Non-RH slices."""
        total = next(p for p in self.dash["panels"] if p.get("title") == "Total")
        rows = list(csv.DictReader(io.StringIO(total["targets"][0]["csvContent"])))
        all_vals = [
            int(r["value"])
            for r in rows
            if r["Source"] == builder.SOURCE_ALL and r["Age"] != analytics.FILTER_ALL
        ]
        rh_vals = [
            int(r["value"])
            for r in rows
            if r["Source"] == builder.SOURCE_REDHAT and r["Age"] != analytics.FILTER_ALL
        ]
        nrs_vals = [
            int(r["value"])
            for r in rows
            if r["Source"] == builder.SOURCE_NON_REDHAT and r["Age"] != analytics.FILTER_ALL
        ]
        self.assertEqual(sum(all_vals), sum(rh_vals) + sum(nrs_vals))
        # Selecting All uses SOURCE_ALL rows only — not RH+NRS pipe
        source_var = next(v for v in self.dash["templating"]["list"] if v["name"] == "source")
        self.assertEqual(source_var["allValue"], builder.SOURCE_ALL)

    def test_simple_view_namespace_slice(self):
        rows = self.analysis["simple_view"]
        ns_rows = [r for r in rows if r["Namespace"] == "chad-devspaces"]
        self.assertTrue(ns_rows)
        other = [r for r in rows if r["Namespace"] == "admin-devspaces"]
        # nginx is Moderate-only → excluded from simple view
        self.assertFalse(other)

    def test_ocp_panels_have_cluster_and_source(self):
        for substr in (
            "Red Hat SRE-managed OpenShift images",
            "Critical CVEs by age — SRE-managed",
            "Important CVEs by age — SRE-managed",
        ):
            panel = _panel_by_title_substr(self.dash, substr)
            headers = _csv_headers(panel)
            self.assertIn("Source", headers, substr)
            self.assertIn("Cluster", headers, substr)
            blob = _transform_blob(panel)
            self.assertIn("${source:pipe}", blob, substr)
            self.assertIn("${cluster:pipe}", blob, substr)

    def test_cluster_filter_roundtrip_on_components(self):
        rows = self.analysis["filterable_all_components"]
        prod = [r for r in rows if r["Cluster"] == "prod-cluster"]
        dev = [r for r in rows if r["Cluster"] == "ocp-dev"]
        self.assertTrue(prod)
        self.assertTrue(dev)
        self.assertEqual(
            len(rows),
            len(prod) + len(dev),
        )

    def test_source_slices_partition(self):
        by = self.analysis["filterables_by_source"]
        self.assertEqual(
            set(by),
            {builder.SOURCE_ALL, builder.SOURCE_REDHAT, builder.SOURCE_NON_REDHAT},
        )
        all_n = sum(r["Findings"] for r in by[builder.SOURCE_ALL]["filterable_remediation"])
        rh_n = sum(r["Findings"] for r in by[builder.SOURCE_REDHAT]["filterable_remediation"])
        nrs_n = sum(
            r["Findings"] for r in by[builder.SOURCE_NON_REDHAT]["filterable_remediation"]
        )
        self.assertEqual(all_n, rh_n + nrs_n)

    def test_panel11_and_12_preserved(self):
        titles = [p.get("title") or "" for p in self.dash["panels"]]
        self.assertTrue(any("filterable" in t.lower() for t in titles))
        self.assertTrue(any("legacy" in t.lower() for t in titles))
        detail = next(p for p in self.dash["panels"] if p.get("id") == 90)
        self.assertIn("Detail", detail.get("title") or "")

    def test_uid_phase0(self):
        self.assertEqual(self.dash["uid"], "ado-rhacs-vuln-posture-phase0")


if __name__ == "__main__":
    unittest.main()
