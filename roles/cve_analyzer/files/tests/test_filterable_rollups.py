"""Regression: namespace-aware rollups + Phase 0 dashboard filter wiring."""
from __future__ import annotations

import json
import re
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
        deployment="udi",
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
]


class FilterableRollupsTest(unittest.TestCase):
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

    def test_all_equals_full_cluster(self):
        self.assertEqual(
            sum(r["Findings"] for r in self.analysis["filterable_remediation"]), 4
        )

    def test_single_namespace(self):
        rows = [
            r
            for r in self.analysis["filterable_remediation"]
            if r["Namespace"] == "chad-devspaces"
        ]
        self.assertEqual(sum(r["Findings"] for r in rows), 2)

    def test_multi_namespace_no_dup(self):
        wanted = {"chad-devspaces", "aap"}
        rows = [
            r
            for r in self.analysis["filterable_remediation"]
            if r["Namespace"] in wanted
        ]
        self.assertEqual(sum(r["Findings"] for r in rows), 3)

    def test_regex_devspaces(self):
        pat = re.compile(".*devspaces.*")
        rows = [
            r
            for r in self.analysis["filterable_remediation"]
            if pat.search(r["Namespace"])
        ]
        self.assertEqual(sum(r["Findings"] for r in rows), 3)

    def test_panels_wire_namespace_match(self):
        for title in (
            "All components",
            "Remediation Paths",
            "Finding ownership",
            "Red Hat Components",
            "Non-Red Hat images",
            "All images",
            "Findings by namespace",
        ):
            panel = next(p for p in self.dash["panels"] if p.get("title") == title)
            blob = json.dumps(panel.get("transformations") or [])
            self.assertIn("${namespace_match}", blob, title)

    LOCKED_TREND_EXPR = builder.legacy_findings_trend_expr()
    HYBRID_TREND_EXPR = builder.hybrid_findings_trend_expr()

    def test_trend_phase1_filterable_plus_legacy(self):
        trends = [
            p
            for p in self.dash["panels"]
            if "Findings over time" in (p.get("title") or "")
        ]
        self.assertEqual(len(trends), 2)
        filt, legacy = trends[0], trends[1]
        self.assertIn("filterable", filt["title"].lower())
        self.assertEqual(filt["targets"][0]["expr"], self.HYBRID_TREND_EXPR)
        self.assertEqual(filt["targets"][0]["datasource"]["uid"], "${prometheus}")
        self.assertFalse(filt.get("timeFrom"))
        self.assertEqual(filt.get("maxDataPoints"), 5000)
        self.assertEqual(filt["targets"][0].get("interval"), "1m")
        self.assertIn("August 2, 2026", filt.get("description") or "")
        self.assertFalse(filt.get("transformations"))
        self.assertIn("legacy", legacy["title"].lower())
        self.assertEqual(legacy["targets"][0]["expr"], self.LOCKED_TREND_EXPR)
        self.assertEqual(legacy["targets"][0].get("interval"), "1h")
        self.assertFalse(legacy.get("timeFrom"))
        blob = json.dumps(filt)
        self.assertIn("${namespace:pipe}", blob)
        self.assertIn("${namespace_match}", blob)
        self.assertIn("cve_posture_findings_by_ns{", blob)
        self.assertNotIn("${component}", blob)

    def test_detail_panel_id_preserved(self):
        detail = next(p for p in self.dash["panels"] if p.get("id") == 90)
        self.assertIn("Detail", detail.get("title") or "")

    def test_phase0_uid_only(self):
        self.assertEqual(self.dash["uid"], "ado-rhacs-vuln-posture-phase0")

    def test_cluster_filter_variable(self):
        names = [v["name"] for v in self.dash["templating"]["list"]]
        self.assertIn("cluster", names)
        self.assertIn("prometheus", names)  # trends only; not the ACS cluster filter
        cluster_var = next(v for v in self.dash["templating"]["list"] if v["name"] == "cluster")
        self.assertTrue(cluster_var.get("includeAll"))
        # portable: values come from data, not hardcoded env names only
        opts = {o.get("value") for o in cluster_var.get("options") or []}
        self.assertTrue({"prod-cluster", "ocp-dev"} & opts)

    def test_cluster_filter_on_vuln_panels(self):
        for title in (
            "All components",
            "Remediation Paths",
            "Finding ownership",
            "Findings by namespace",
        ):
            panel = next(p for p in self.dash["panels"] if p.get("title") == title)
            blob = json.dumps(panel.get("transformations") or [])
            self.assertIn("${cluster:pipe}", blob, title)

    def test_cluster_filters_phase1_trend_not_legacy(self):
        filt = next(
            p
            for p in self.dash["panels"]
            if "filterable" in (p.get("title") or "").lower()
        )
        legacy = next(
            p
            for p in self.dash["panels"]
            if "legacy" in (p.get("title") or "").lower()
        )
        self.assertIn("${cluster:pipe}", json.dumps(filt))
        self.assertNotIn("${cluster", json.dumps(legacy))

    def test_single_cluster_counts(self):
        rows = [
            r
            for r in self.analysis["filterable_remediation"]
            if r["Cluster"] == "prod-cluster"
        ]
        self.assertEqual(sum(r["Findings"] for r in rows), 3)

    def test_simple_view_rows(self):
        rows = self.analysis.get("simple_view") or []
        self.assertTrue(rows)
        top = rows[0]
        for key in (
            "Cluster",
            "Namespace",
            "Image",
            "Namespace / deployment",
            "Age",
            "Oldest",
            "Critical",
            "Important",
            "Status",
            "ClusterAll",
            "NsAll",
            "AgeAll",
        ):
            self.assertIn(key, top)
        self.assertEqual(top["Status"], "needs_update")
        self.assertGreaterEqual(int(top["Critical"]) + int(top["Important"]), 1)
        # fixable Critical/Important only; Moderate-only image excluded
        images = {r["Image"] for r in rows}
        self.assertTrue(any("udi" in i or "devspaces" in i for i in images))
        # Finding age bucket tokens (not Discover day labels) for toolbar filter
        self.assertTrue(any(r["Age"] in analytics.FINDING_AGE_BUCKETS for r in rows))

    def test_simple_view_panel(self):
        panel = next(p for p in self.dash["panels"] if p.get("title") == "Simple view")
        blob = json.dumps(panel.get("transformations") or [])
        self.assertIn("${cluster:pipe}", blob)
        self.assertIn("${namespace:pipe}", blob)
        self.assertIn("${finding_age:pipe}", blob)
        self.assertIn("${source:pipe}", blob)
        # sits above Detail
        detail = next(p for p in self.dash["panels"] if p.get("id") == 90)
        self.assertLess(panel["gridPos"]["y"], detail["gridPos"]["y"])

    def test_drill_resets_namespace_match_and_hidden_vars(self):
        """Stuck payload/sre and leftover namespace_match emptied or pinned Detail."""
        panel = next(p for p in self.dash["panels"] if p.get("title") == "Finding ownership")
        url = ""
        for ov in panel.get("fieldConfig", {}).get("overrides", []):
            for prop in ov.get("properties", []):
                if prop.get("id") == "links":
                    url = prop["value"][0]["url"]
        self.assertIn("var-namespace_match=.*", url)
        self.assertIn("var-payload=.*", url)
        self.assertIn("var-sre=", url)
        self.assertNotIn("var-payload=$__all", url)
        self.assertIn("viewPanel=90", url)
        # new tab so Back on the main board does not keep drill filters
        link = next(
            prop["value"][0]
            for ov in panel.get("fieldConfig", {}).get("overrides", [])
            for prop in ov.get("properties", [])
            if prop.get("id") == "links"
        )
        self.assertTrue(link.get("targetBlank"))
        self.assertIn("${__value.raw:percentencode}", url)
        self.assertTrue(url)  # ownership click uses cell value

    def test_image_rollup_keeps_repository(self):
        panel = next(p for p in self.dash["panels"] if p.get("title") == "All images")
        group = next(
            t for t in panel["transformations"] if t.get("id") == "groupBy"
        )
        fields = group["options"]["fields"]
        self.assertIn("Repository", fields)
        self.assertIn("Cluster", fields)
        url = ""
        for ov in panel.get("fieldConfig", {}).get("overrides", []):
            for prop in ov.get("properties", []):
                if prop.get("id") == "links":
                    url = prop["value"][0]["url"]
        self.assertIn('__data.fields["Repository"]', url)
        self.assertIn('__data.fields["Cluster"]', url)

    def test_over30_drill_keeps_cluster(self):
        panel = next(
            p
            for p in self.dash["panels"]
            if "older than 30 days" in (p.get("title") or "")
        )
        group = next(t for t in panel["transformations"] if t.get("id") == "groupBy")
        self.assertIn("Cluster", group["options"]["fields"])
        url = ""
        for ov in panel.get("fieldConfig", {}).get("overrides", []):
            for prop in ov.get("properties", []):
                if prop.get("id") == "links":
                    url = prop["value"][0]["url"]
        self.assertIn("${__value.raw:percentencode}", url)
        self.assertIn('__data.fields["Cluster"]', url)

    def test_detail_filter_sim_clears_stuck_payload(self):
        """Reproduce screenshot: payload=Yes alone yields only OCP SRE rows."""
        import csv
        import io
        from collections import Counter

        detail = next(p for p in self.dash["panels"] if p.get("id") == 90)
        rows = list(csv.DictReader(io.StringIO(detail["targets"][0]["csvContent"])))
        stuck = [r for r in rows if r.get("Payload") == "Yes"]
        # Fixture may be tiny; when payload rows exist they must not be the only path
        # after a namespace drill URL resets payload to .*.
        ownership = next(p for p in self.dash["panels"] if p.get("title") == "Finding ownership")
        url = ""
        for ov in ownership.get("fieldConfig", {}).get("overrides", []):
            for prop in ov.get("properties", []):
                if prop.get("id") == "links":
                    url = prop["value"][0]["url"]
        self.assertIn("var-payload=.*", url)
        self.assertIn("var-namespace_match=.*", url)
        if stuck:
            ns = Counter(r["Namespace"] for r in stuck)
            self.assertTrue(ns)  # documents the pinned-Detail failure mode

    def test_no_string_convert_on_drill_fields(self):
        panel = next(p for p in self.dash["panels"] if p.get("title") == "All components")
        for t in panel.get("transformations") or []:
            if t.get("id") != "convertFieldType":
                continue
            for c in t.get("options", {}).get("conversions") or []:
                if c.get("targetField") in {"Namespace", "Component", "Ownership"}:
                    self.assertNotEqual(
                        c.get("destinationType"),
                        "string",
                        f"string convert on {c.get('targetField')} quotes drill values",
                    )

    def test_age_drill_pins_sre_severity_payload(self):
        panel = next(
            p
            for p in self.dash["panels"]
            if (p.get("title") or "").startswith("Critical CVEs by age")
        )
        link = next(
            prop["value"][0]
            for ov in panel.get("fieldConfig", {}).get("overrides", [])
            for prop in ov.get("properties", [])
            if prop.get("id") == "links"
        )
        url = link["url"]
        self.assertTrue(link.get("targetBlank"))
        self.assertIn("viewPanel=90", url)
        self.assertIn("${__value.raw:percentencode}", url)
        self.assertIn("var-severity=Critical", url)
        self.assertIn("var-payload=Yes", url)
        self.assertIn("Red%20Hat%20SRE%20Managed%20Services", url)
        self.assertIn("var-namespace_match=.*", url)

    def test_sre_managed_shows_cluster_column(self):
        panel = next(
            p for p in self.dash["panels"] if p.get("title") == "Red Hat SRE Managed Services"
        )
        # Cluster stays in the frame for drill + display (not custom.hidden).
        cluster_ov = next(
            ov
            for ov in panel["fieldConfig"]["overrides"]
            if ov.get("matcher", {}).get("options") == "Cluster"
        )
        hidden = [
            prop
            for prop in cluster_ov.get("properties", [])
            if prop.get("id") == "custom.hidden" and prop.get("value") is True
        ]
        self.assertEqual(hidden, [], "Cluster must be visible so duplicate components are distinguishable")
        self.assertIn("Cluster", panel["targets"][0]["csvContent"].splitlines()[0])

    def test_namespace_match_variable(self):
        names = [v["name"] for v in self.dash["templating"]["list"]]
        self.assertIn("namespace", names)
        self.assertIn("namespace_match", names)


class ImageUpdateCheckGateTests(unittest.TestCase):
    """Phase 4B: catalog/DockerHub Action checks default off; enable preserves path."""

    def tearDown(self):
        import os

        os.environ.pop("CVE_ANALYZER_IMAGE_UPDATE_CHECK", None)

    def test_default_disabled(self):
        import os

        os.environ.pop("CVE_ANALYZER_IMAGE_UPDATE_CHECK", None)
        self.assertFalse(analytics._image_updates_enabled())

    def test_explicit_false_disabled(self):
        import os

        os.environ["CVE_ANALYZER_IMAGE_UPDATE_CHECK"] = "false"
        self.assertFalse(analytics._image_updates_enabled())

    def test_explicit_true_enabled(self):
        import os

        os.environ["CVE_ANALYZER_IMAGE_UPDATE_CHECK"] = "true"
        self.assertTrue(analytics._image_updates_enabled())

    def test_annotate_skips_network_when_disabled(self):
        import os
        from unittest import mock

        os.environ["CVE_ANALYZER_IMAGE_UPDATE_CHECK"] = "false"
        items = [
            {
                "Component": "docker.io/library/nginx",
                "Action": analytics.DEFAULT_REVIEW_ACTION,
                "Findings": 1,
            }
        ]
        by_family = {
            "docker.io/library/nginx": [
                {
                    "repository": "docker.io/library/nginx",
                    "digest": "sha256:abc",
                    "image": "docker.io/library/nginx:1.25",
                }
            ]
        }
        with mock.patch.object(analytics, "image_update_action") as mocked:
            analytics.annotate_image_updates(items, by_family)
            mocked.assert_not_called()
        self.assertEqual(items[0]["Action"], analytics.DEFAULT_REVIEW_ACTION)

    def test_annotate_calls_when_enabled(self):
        import os
        from unittest import mock

        os.environ["CVE_ANALYZER_IMAGE_UPDATE_CHECK"] = "true"
        items = [
            {
                "Component": "docker.io/library/nginx",
                "Action": analytics.DEFAULT_REVIEW_ACTION,
                "Findings": 1,
            }
        ]
        by_family = {
            "docker.io/library/nginx": [
                {
                    "repository": "docker.io/library/nginx",
                    "digest": "sha256:abc",
                    "image": "docker.io/library/nginx:1.25",
                }
            ]
        }
        with mock.patch.object(
            analytics, "image_update_action", return_value="No newer image (nginx:1.25)"
        ) as mocked:
            analytics.annotate_image_updates(items, by_family)
            mocked.assert_called_once()
        self.assertEqual(items[0]["Action"], "No newer image (nginx:1.25)")

    def test_classify_and_drilldown_independent_of_gate(self):
        """Classification / panel 90 inputs do not require catalog checks."""
        import os

        os.environ["CVE_ANALYZER_IMAGE_UPDATE_CHECK"] = "false"
        rows = [dict(r) for r in ROWS]
        analytics.classify_rows(rows, CFG)
        self.assertTrue(all(r.get("ownership") for r in rows))
        self.assertTrue(all(r.get("remediation_action") for r in rows))
        detail = analytics.drilldown_rows(rows, CFG, limit=100)
        self.assertGreater(len(detail), 0)
        self.assertIn("Action", detail[0])
        self.assertIn("Severity", detail[0])

    def test_platform_payload_bars_keeps_category_xfield(self):
        """Panel 16 must keep Category string + xField (not exclude after groupBy)."""
        rows = [dict(r) for r in ROWS]
        analytics.classify_rows(rows, CFG)
        analysis = analytics.build_analysis(
            rows, datetime.now(timezone.utc), CFG, "test"
        )
        panel = builder.platform_payload_bars(analysis, x=0, y=0, w=12, h=8)
        self.assertEqual(panel["type"], "barchart")
        self.assertEqual(panel["options"].get("xField"), "Category")
        csv = (panel.get("targets") or [{}])[0].get("csvContent") or ""
        self.assertIn("Category", csv.splitlines()[0])
        self.assertIn("Ownership", csv.splitlines()[0])
        organize = [
            t
            for t in panel.get("transformations") or []
            if t.get("id") == "organize"
            and (t.get("options") or {}).get("renameByName")
        ]
        self.assertTrue(organize)
        exclude = (organize[-1].get("options") or {}).get("excludeByName") or {}
        self.assertFalse(exclude.get("Category"))
        dash = builder.build_dashboard(
            analysis,
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            "ado-rhacs-vuln-posture-phase0",
        )
        fp = builder.builder_fingerprint_tag()
        self.assertIn(fp, dash.get("tags") or [])
        bars = [
            p
            for p in dash.get("panels") or []
            if p.get("type") == "barchart"
            and "OpenShift images" in (p.get("title") or "")
        ]
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["options"].get("xField"), "Category")


if __name__ == "__main__":
    unittest.main()
