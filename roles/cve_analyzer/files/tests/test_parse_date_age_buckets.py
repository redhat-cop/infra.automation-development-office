#!/usr/bin/env python3
"""English-month Discovered At must populate OCP age buckets and over-30."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import rhacs_report_analytics as analytics  # noqa: E402


class ParseDateEnglishMonthTests(unittest.TestCase):
    def test_english_month_formats(self) -> None:
        cases = {
            "October 09, 2026": datetime(2026, 10, 9, tzinfo=timezone.utc),
            "October 5, 2026": datetime(2026, 10, 5, tzinfo=timezone.utc),
            "Oct 09, 2026": datetime(2026, 10, 9, tzinfo=timezone.utc),
            "September 28, 2026": datetime(2026, 9, 28, tzinfo=timezone.utc),
            "2026-10-09T00:00:00Z": datetime(2026, 10, 9, tzinfo=timezone.utc),
            "10/09/2026": datetime(2026, 10, 9, tzinfo=timezone.utc),
        }
        for raw, expected in cases.items():
            got = analytics.parse_date(raw)
            self.assertIsNotNone(got, raw)
            assert got is not None
            self.assertEqual(got.date(), expected.date(), raw)

    def test_ui_csv_without_agedays_fills_buckets(self) -> None:
        """Reproduce Downloads UI scrubbed shape: Discovered At only."""
        report_date = datetime(2026, 10, 28, tzinfo=timezone.utc)
        payload = analytics.OCP_DEFAULT_REPO
        rows_in = [
            # Critical, ~23 days -> 14–30
            {
                "CVE": "CVE-2026-1",
                "Severity": "Critical",
                "Image": f"{payload}@sha256:{'a' * 64}",
                "Namespace": "openshift-apiserver",
                "Discovered At": "October 05, 2026",
            },
            # Important, ~49 days -> 30–60 / over-30
            {
                "CVE": "CVE-2026-2",
                "Severity": "Important",
                "Image": f"{payload}@sha256:{'b' * 64}",
                "Namespace": "openshift-apiserver",
                "Discovered At": "September 09, 2026",
            },
            # Important, ~19 days -> 14–30 (not over-30)
            {
                "CVE": "CVE-2026-3",
                "Severity": "Important",
                "Image": f"{payload}@sha256:{'c' * 64}",
                "Namespace": "openshift-monitoring",
                "Discovered At": "October 09, 2026",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ui_scrubbed.csv"
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows_in[0].keys()))
                writer.writeheader()
                writer.writerows(rows_in)

            rows = analytics.load_scrubbed_rows(path)
            analytics.finalize_ages(rows, report_date)

        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r.get("discovered") is not None for r in rows))
        self.assertNotIn("Unknown", {r["age_bucket"] for r in rows})

        cfg = {"ocp_payload_repository": payload, "families": []}
        ocp = analytics.ocp_payload_report(rows, cfg)
        crit = analytics.unique_cve_age_buckets(ocp["rows"], "Critical", report_date)
        imp = analytics.unique_cve_age_buckets(ocp["rows"], "Important", report_date)
        self.assertEqual(crit.get("Unknown", 0), 0)
        self.assertEqual(imp.get("Unknown", 0), 0)
        self.assertEqual(crit["14–30 days"], 1)
        self.assertEqual(imp["30–60 days"], 1)
        self.assertEqual(imp["14–30 days"], 1)

        over = analytics.component_over_30(rows)
        self.assertGreaterEqual(sum(r["Total >30 Days"] for r in over), 1)


if __name__ == "__main__":
    unittest.main()
