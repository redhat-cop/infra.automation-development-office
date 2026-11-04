#!/usr/bin/env python3
"""Unique KPI combined Finding age = set union, never sum of bucket Uniques."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402

FILTER_ALL = analytics.FILTER_ALL
OVER_14 = "15-30 days|30-60 days|Over 60 days"
OVER_30 = "30-60 days|Over 60 days"


def _row(**kwargs) -> dict:
    base = {
        "cve": "CVE-X",
        "cluster": "ocp-dev",
        "ownership": "sre_managed",
        "finding_age": "0-15 days",
        "namespace": "ns-a",
        "severity": "Critical",
        "fixable": True,
        "redhat_source": True,
        "digest": "sha256:abc",
        "repository": "registry.example/app",
        "component": "app",
        "image": "registry.example/app:1",
        "deployment": "app",
        "age_days": 7,
    }
    base.update(kwargs)
    return base


def _rows_multi_age() -> list[dict]:
    """CVE-1 appears in two age buckets; CVE-2 only in 15-30."""
    return [
        _row(cve="CVE-1", finding_age="0-15 days", age_days=7, redhat_source=True),
        _row(
            cve="CVE-1",
            finding_age="Over 60 days",
            age_days=90,
            redhat_source=True,
        ),
        _row(
            cve="CVE-2",
            finding_age="15-30 days",
            age_days=20,
            severity="Low",
            fixable=False,
            redhat_source=False,
        ),
    ]


def _pick(
    items: list[dict], *, cluster_key: str, sre_key: str, age: str
) -> int:
    matched = [
        i
        for i in items
        if i.get("ClusterKey") == cluster_key
        and i.get("SreKey") == sre_key
        and i.get("Age") == age
    ]
    assert len(matched) == 1, (cluster_key, sre_key, age, matched)
    return int(matched[0]["Unique CVEs"])


class UniqueCveAgeUnionTest(unittest.TestCase):
    def test_combined_age_counts_cve_once(self):
        items = analytics.unique_cves_kpi_filterable(_rows_multi_age())
        cl_all = analytics.cluster_all_key(["ocp-dev"])
        # Singles: CVE-1 in 0-15 and Over 60; CVE-2 in 15-30
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age="0-15 days"), 1)
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age="15-30 days"), 1)
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age="Over 60 days"), 1)
        # Sum of singles would be 3; Age=__ALL__ distinct is 2
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age=FILTER_ALL), 2)
        # Over 14 = 15-30 ∪ Over 60 → CVE-1 + CVE-2 = 2 (not 1+1=2 wait: CVE-1 in Over60, CVE-2 in 15-30 → 2)
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age=OVER_14), 2)
        # 0-15|Over 60 → only CVE-1 once
        pipe = "0-15 days|Over 60 days"
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age=pipe), 1)
        # Inflated sum of those two singles would be 2
        self.assertEqual(
            _pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age="0-15 days")
            + _pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age="Over 60 days"),
            2,
        )

    def test_over30_union(self):
        items = analytics.unique_cves_kpi_filterable(_rows_multi_age())
        cl_all = analytics.cluster_all_key(["ocp-dev"])
        # Over 30 = 30-60 ∪ Over 60 → only CVE-1
        self.assertEqual(_pick(items, cluster_key=cl_all, sre_key=FILTER_ALL, age=OVER_30), 1)

    def _analysis(self):
        rows_in = _rows_multi_age()
        fam = analytics.load_image_families(FILES / "image_families.yaml")
        return analytics.build_analysis(
            rows_in, datetime.now(timezone.utc), fam, "synthetic"
        )

    def test_source_both_emits_individual_ages(self):
        analysis = self._analysis()
        kpi_rows = builder._stat_metric_rows(analysis, "Unique CVEs")
        both_ages = {r[3] for r in kpi_rows if r[0] == builder.SOURCE_BOTH}
        self.assertIn("0-15 days", both_ages)
        self.assertIn(OVER_14, both_ages)
        self.assertIn(FILTER_ALL, both_ages)
        rh_ages = {r[3] for r in kpi_rows if r[0] == builder.SOURCE_REDHAT}
        self.assertIn("0-15 days", rh_ages)

    def test_unique_panel_uses_equal_age_not_regex(self):
        dash = builder.build_dashboard(
            self._analysis(),
            "RHACS Vulnerability Posture (ADO) - Phase 0",
            "ado-rhacs-vuln-posture-phase0",
        )
        unique = next(p for p in dash["panels"] if p.get("title") == "Unique CVEs")
        age_filters = []
        for xf in unique.get("transformations") or []:
            for f in (xf.get("options") or {}).get("filters") or []:
                if f.get("fieldName") == "Age":
                    age_filters.append(f)
        self.assertEqual(len(age_filters), 1)
        cfg = age_filters[0].get("config") or {}
        self.assertEqual(cfg.get("id"), "equal")
        self.assertEqual((cfg.get("options") or {}).get("value"), "${finding_age:pipe}")
        self.assertEqual(
            ((unique.get("fieldConfig") or {}).get("defaults") or {}).get("noValue"),
            "n/a",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
