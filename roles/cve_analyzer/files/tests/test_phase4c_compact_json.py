#!/usr/bin/env python3
"""Phase 4C-1: compact dashboard JSON must parse to the same structure as indent=2."""
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

# Reuse filterable fixture rows / CFG for equivalent-input structural compare.
from tests.test_filterable_rollups import CFG, ROWS  # noqa: E402


class CompactJsonIdentityTest(unittest.TestCase):
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
        cls.pretty = builder.serialize_dashboard_json(cls.dash, compact=False)
        cls.compact = builder.serialize_dashboard_json(cls.dash, compact=True)

    def test_both_parse(self):
        self.assertIsInstance(json.loads(self.pretty), dict)
        self.assertIsInstance(json.loads(self.compact), dict)

    def test_parsed_structures_identical(self):
        self.assertEqual(json.loads(self.pretty), json.loads(self.compact))

    def test_compact_smaller(self):
        self.assertLess(len(self.compact.encode("utf-8")), len(self.pretty.encode("utf-8")))

    def test_panel_ids_unchanged(self):
        pretty_ids = [p.get("id") for p in json.loads(self.pretty)["panels"]]
        compact_ids = [p.get("id") for p in json.loads(self.compact)["panels"]]
        self.assertEqual(pretty_ids, compact_ids)
        self.assertIn(90, compact_ids)
        self.assertIn(11, compact_ids)

    def test_panel_11_queries_identical(self):
        p = next(x for x in json.loads(self.pretty)["panels"] if x.get("id") == 11)
        c = next(x for x in json.loads(self.compact)["panels"] if x.get("id") == 11)
        self.assertEqual(p.get("targets"), c.get("targets"))
        self.assertEqual(p.get("title"), c.get("title"))

    def test_panel_90_data_and_filters_identical(self):
        p = next(x for x in json.loads(self.pretty)["panels"] if x.get("id") == 90)
        c = next(x for x in json.loads(self.compact)["panels"] if x.get("id") == 90)
        self.assertEqual(p.get("targets"), c.get("targets"))
        self.assertEqual(p.get("transformations"), c.get("transformations"))
        self.assertEqual(p.get("fieldConfig"), c.get("fieldConfig"))

    def test_templating_and_links_unchanged(self):
        p = json.loads(self.pretty)
        c = json.loads(self.compact)
        self.assertEqual(p.get("templating"), c.get("templating"))
        self.assertEqual(p.get("links"), c.get("links"))
        # Drill-down URLs live in panel fieldConfig / links — full panel equality
        # already covered by structure identity; spot-check detail description.
        pd = next(x for x in p["panels"] if x.get("id") == 90)
        cd = next(x for x in c["panels"] if x.get("id") == 90)
        self.assertEqual(pd.get("description"), cd.get("description"))

    def test_detail_row_count_unchanged(self):
        # Fixture produces one drilldown row per input finding (within limit).
        self.assertEqual(len(self.analysis.get("drilldown") or []), len(ROWS))
        pretty_detail = next(x for x in json.loads(self.pretty)["panels"] if x.get("id") == 90)
        compact_detail = next(x for x in json.loads(self.compact)["panels"] if x.get("id") == 90)
        self.assertEqual(pretty_detail["targets"], compact_detail["targets"])


if __name__ == "__main__":
    unittest.main()
