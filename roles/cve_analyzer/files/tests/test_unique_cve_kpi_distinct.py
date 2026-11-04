#!/usr/bin/env python3
"""Unique CVE KPI equals COUNT(DISTINCT cve) — not ownership/source sum."""
from __future__ import annotations

import json
import sys
import unittest
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402

FILTER_ALL = analytics.FILTER_ALL
GROUND = Path("/tmp/rhacs-scrubbed-groundtruth.csv")
GT_JSON = Path("/tmp/unique-cve-groundtruth.json")


def _load_ground_analysis():
    if not GROUND.is_file():
        raise unittest.SkipTest(f"missing {GROUND}")
    return analytics.analyze_paths(
        GROUND,
        None,
        FILES / "image_families.yaml",
    )


class UniqueCveKpiDistinctTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = _load_ground_analysis()
        # Re-load rows for ground-truth predicates (same CSV as analysis).
        cls.rows = analytics.load_scrubbed_rows(GROUND)
        families = analytics.load_image_families(FILES / "image_families.yaml")
        analytics.classify_rows(cls.rows, families)
        report_date = analytics.scrubbed_pull_time(GROUND)
        analytics.finalize_ages(cls.rows, report_date)
        cls.gt = json.loads(GT_JSON.read_text()) if GT_JSON.is_file() else {}

    def _truth(self, predicate) -> int:
        return len(
            {
                str(r.get("cve") or "").strip()
                for r in self.rows
                if str(r.get("cve") or "").strip() and predicate(r)
            }
        )

    def _unique_kpi(self, source: str, cluster_key: str, sre_key: str) -> int:
        rows = builder._stat_metric_rows(self.analysis, "Unique CVEs")
        matched = [
            r
            for r in rows
            if r[0] == source
            and r[1] == cluster_key
            and r[3] == FILTER_ALL
            and r[4] == sre_key
        ]
        self.assertEqual(len(matched), 1, (source, cluster_key, sre_key, matched[:3]))
        return int(matched[0][5])

    def test_ground_truth_all_and_slices(self):
        clusters = sorted(
            {
                analytics._cluster_of(r)
                for r in self.rows
                if analytics._cluster_of(r) != FILTER_ALL
            },
            key=str.casefold,
        )
        cl_all = analytics.cluster_all_key(clusters)
        expect = self.gt.get("ground_truth") or {}

        all_n = self._unique_kpi(builder.SOURCE_ALL, cl_all, FILTER_ALL)
        self.assertEqual(all_n, self._truth(lambda _r: True))
        if expect:
            self.assertEqual(all_n, expect["all"])

        rh_n = self._unique_kpi(builder.SOURCE_REDHAT, cl_all, FILTER_ALL)
        self.assertEqual(
            rh_n, self._truth(lambda r: bool(r.get("redhat_source")))
        )
        nrs_n = self._unique_kpi(builder.SOURCE_NON_REDHAT, cl_all, FILTER_ALL)
        self.assertEqual(
            nrs_n, self._truth(lambda r: not r.get("redhat_source"))
        )
        # RH+NRS multi → All distinct (full population), not RH+NRS sum
        both = self._unique_kpi(builder.SOURCE_BOTH, cl_all, FILTER_ALL)
        self.assertEqual(both, all_n)
        self.assertLess(both, rh_n + nrs_n)

        for cluster in clusters:
            got = self._unique_kpi(builder.SOURCE_ALL, cluster, FILTER_ALL)
            want = self._truth(lambda r, c=cluster: analytics._cluster_of(r) == c)
            self.assertEqual(got, want, cluster)
            self.assertGreater(got, 0, cluster)

        # Multi both clusters
        if len(clusters) > 1:
            multi = "|".join(clusters)
            self.assertEqual(
                self._unique_kpi(builder.SOURCE_ALL, multi, FILTER_ALL), all_n
            )

        labels = analytics.ownership_label_order()
        for label in labels:
            key = next(
                k for k, v in analytics.OWNERSHIP_LABELS.items() if v == label
            )
            got = self._unique_kpi(builder.SOURCE_ALL, cl_all, label)
            want = self._truth(
                lambda r, k=key: (r.get("ownership") or "non_redhat") == k
            )
            self.assertEqual(got, want, label)

        # Ownership sum inflates; __ALL__ does not
        own_sum = sum(
            self._unique_kpi(builder.SOURCE_ALL, cl_all, label) for label in labels
        )
        self.assertGreater(own_sum, all_n)
        if expect:
            self.assertEqual(own_sum, expect["own_sum"])
            self.assertEqual(all_n, expect["own_union"])

    def test_dashboard_unique_panel_wiring_and_size(self):
        dash = builder.build_dashboard(
            self.analysis,
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            "ado-rhacs-vuln-posture-phase0",
        )
        unique = next(p for p in dash["panels"] if p.get("title") == "Unique CVEs")
        blob = json.dumps(unique)
        self.assertIn("ClusterKey", blob)
        self.assertIn("SreKey", blob)
        self.assertIn("${cluster:pipe}", blob)
        self.assertIn("${sre:pipe}", blob)
        self.assertIn("${source:pipe}", blob)
        sre = next(v for v in dash["templating"]["list"] if v["name"] == "sre")
        self.assertEqual(sre.get("allValue"), FILTER_ALL)
        raw = json.dumps(dash, separators=(",", ":"))
        size = len(raw.encode("utf-8"))
        self.assertLess(size, 16 * 1024 * 1024, size)
        print(f"DASHBOARD_SIZE_BYTES={size}")
        print(f"BUILDER_FINGERPRINT={builder.builder_fingerprint_tag()}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
