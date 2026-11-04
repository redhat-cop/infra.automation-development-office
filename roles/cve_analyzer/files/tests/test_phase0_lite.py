#!/usr/bin/env python3
"""Phase 0 Lite: omit Detail panel 90; Full unchanged; panel 11 PromQL locked."""
from __future__ import annotations

import csv
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

PHASE0_UID = "ado-rhacs-vuln-posture-phase0"
TITLE = "RHACS Vulnerability Posture (ADO) - Phase 0"
LIMIT_LITE_API = 12 * 1024 * 1024
KPI_TITLES = frozenset(
    {
        "Total",
        "Critical",
        "Important",
        "Moderate",
        "Low",
        "Unique CVEs",
        "Fixable findings",
    }
)


def _api_body_bytes(dash: dict) -> int:
    payload = {
        "dashboard": dash,
        "overwrite": True,
        "message": "Updated by cve-analyzer Ansible (live data.json or sample)",
        "folderUid": "Security-folder",
    }
    return len(json.dumps(payload).encode("utf-8"))


def _kpi_targets(dash: dict) -> dict[str, object]:
    return {
        (p.get("title") or ""): (p.get("targets") or [])
        for p in dash.get("panels") or []
        if p.get("type") == "stat" and (p.get("title") or "") in KPI_TITLES
    }


def _trend_panel(dash: dict) -> dict:
    """Primary (filterable) Phase 0 Panel 11."""
    return next(
        p
        for p in dash["panels"]
        if p.get("type") == "timeseries"
        and "filterable" in (p.get("title") or "").lower()
    )


class Phase0LiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [dict(r) for r in ROWS]
        analytics.classify_rows(rows, CFG)
        cls.analysis = analytics.build_analysis(
            rows, datetime.now(timezone.utc), CFG, "test"
        )
        cls.full = builder.build_dashboard(
            cls.analysis, TITLE, PHASE0_UID, lite=False
        )
        cls.lite = builder.build_dashboard(
            cls.analysis, TITLE, PHASE0_UID, lite=True
        )
        cls.full_again = builder.build_dashboard(
            cls.analysis, TITLE, PHASE0_UID, lite=False
        )

    def test_full_unchanged_across_builds(self):
        self.assertEqual(self.full, self.full_again)

    def test_full_has_panel_90_with_detail(self):
        p90 = next(p for p in self.full["panels"] if p.get("id") == 90)
        csv_text = p90["targets"][0].get("csvContent") or ""
        self.assertGreater(csv_text.count("\n"), 1)
        self.assertIn("&viewPanel=90", json.dumps(self.full))

    def test_lite_omits_panel_90_and_viewpanel_links(self):
        ids = [p.get("id") for p in self.lite["panels"]]
        self.assertNotIn(90, ids)
        blob = json.dumps(self.lite)
        # Drill URLs use &viewPanel=90 — must not appear in Lite.
        self.assertNotIn("&viewPanel=90", blob)
        self.assertIn("Phase 0 Lite", blob)
        self.assertIn("Detail omitted", self.lite.get("title", ""))

    def test_panel_11_promql_identical(self):
        f11 = _trend_panel(self.full)
        l11 = _trend_panel(self.lite)
        self.assertEqual(f11.get("targets"), l11.get("targets"))
        expr = f11["targets"][0]["expr"]
        self.assertIn("cve_posture_findings_by_cluster", expr)
        self.assertIn('cluster=~"${cluster:pipe}"', expr)
        self.assertEqual(
            f11["targets"][0]["datasource"],
            l11["targets"][0]["datasource"],
        )
        # Legacy reference PromQL stays locked on both Full and Lite.
        f_legacy = next(
            p
            for p in self.full["panels"]
            if "legacy" in (p.get("title") or "").lower()
        )
        l_legacy = next(
            p
            for p in self.lite["panels"]
            if "legacy" in (p.get("title") or "").lower()
        )
        self.assertEqual(f_legacy["targets"], l_legacy["targets"])
        self.assertIn(
            'cve_posture_findings{job="cve-analyzer-ns-metrics"}',
            f_legacy["targets"][0]["expr"],
        )

    def test_summary_stat_values_identical(self):
        self.assertEqual(_kpi_targets(self.full), _kpi_targets(self.lite))
        self.assertTrue(KPI_TITLES <= set(_kpi_targets(self.full)))

    def test_lite_api_body_under_12mb_on_fixture(self):
        lite_bytes = _api_body_bytes(self.lite)
        full_bytes = _api_body_bytes(self.full)
        self.assertLess(lite_bytes, full_bytes)
        self.assertLess(lite_bytes, LIMIT_LITE_API)

    def test_age_panels_labeled_when_lite(self):
        ages = [
            p
            for p in self.lite["panels"]
            if "CVEs by age" in (p.get("title") or "")
        ]
        self.assertEqual(len(ages), 2)
        for panel in ages:
            self.assertIn("unavailable in Phase 0 Lite", panel.get("description") or "")


class Phase0LiteLargeCsvSmoke(unittest.TestCase):
    """If a scrubbed CSV is present, assert Lite API body < 12 MB."""

    def test_lite_under_12mb_when_scrubbed_available(self):
        scrubbed = None
        for base in (Path("/tmp/cve-phase4c-local"), Path.home() / "Downloads"):
            if not base.exists():
                continue
            files = sorted(
                base.glob("RHACS*SCRUBBED*.csv"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if files:
                scrubbed = files[0]
                break
        if scrubbed is None:
            self.skipTest("No scrubbed CSV available for large-size smoke")
        families = FILES / "image_families.yaml"
        analysis = analytics.analyze_paths(scrubbed, None, families)
        lite = builder.build_dashboard(analysis, TITLE, PHASE0_UID, lite=True)
        full = builder.build_dashboard(analysis, TITLE, PHASE0_UID, lite=False)
        lite_api = _api_body_bytes(lite)
        full_api = _api_body_bytes(full)
        self.assertNotIn(90, [p.get("id") for p in lite["panels"]])
        self.assertIn(90, [p.get("id") for p in full["panels"]])
        self.assertLess(lite_api, LIMIT_LITE_API)
        self.assertLess(lite_api, full_api)
        self.assertEqual(
            _trend_panel(full)["targets"],
            _trend_panel(lite)["targets"],
        )
        self.assertEqual(_kpi_targets(full), _kpi_targets(lite))
        self.assertNotIn("&viewPanel=90", json.dumps(lite))
        print(
            f"SMOKE scrubbed={scrubbed.name} "
            f"full_api={full_api} lite_api={lite_api} "
            f"full_json={len(builder.serialize_dashboard_json(full).encode())} "
            f"lite_json={len(builder.serialize_dashboard_json(lite).encode())}",
            flush=True,
        )


if __name__ == "__main__":
    unittest.main()
