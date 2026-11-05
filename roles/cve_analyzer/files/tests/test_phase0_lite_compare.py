"""Full + Lite compare: same analysis, different JSON sizes / panel 90."""
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

PHASE0 = "ado-rhacs-vuln-posture-phase0"
LITE_UID = "ado-lite"


class LiteCompareBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = [dict(r) for r in ROWS]
        analytics.classify_rows(rows, CFG)
        cls.analysis = analytics.build_analysis(
            rows, datetime.now(timezone.utc), CFG, "test"
        )
        cls.full = builder.build_dashboard(
            cls.analysis,
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            PHASE0,
            lite=False,
        )
        cls.lite = builder.build_dashboard(
            cls.analysis,
            "RHACS Vulnerability Posture (ADO) - Lite",
            LITE_UID,
            lite=True,
        )

    def test_uids_and_titles(self):
        self.assertEqual(self.full.get("uid"), PHASE0)
        self.assertEqual(self.lite.get("uid"), LITE_UID)
        self.assertIn("Lite", self.lite.get("title", ""))

    def test_panel_90_only_on_full(self):
        self.assertIn(90, [p.get("id") for p in self.full["panels"]])
        self.assertNotIn(90, [p.get("id") for p in self.lite["panels"]])
        self.assertIn("&viewPanel=90", json.dumps(self.full))
        self.assertNotIn("&viewPanel=90", json.dumps(self.lite))

    def test_lite_smaller(self):
        full_b = len(builder.serialize_dashboard_json(self.full).encode())
        lite_b = len(builder.serialize_dashboard_json(self.lite).encode())
        self.assertLess(lite_b, full_b)

    def test_trend_promql_identical(self):
        def trend(dash):
            return next(
                p
                for p in dash["panels"]
                if p.get("type") == "timeseries"
                and "filterable" in (p.get("title") or "").lower()
            )

        self.assertEqual(trend(self.full)["targets"], trend(self.lite)["targets"])
        self.assertIn(
            "cve_posture_findings_by_cluster",
            trend(self.full)["targets"][0]["expr"],
        )


if __name__ == "__main__":
    unittest.main()
