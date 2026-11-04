#!/usr/bin/env python3
"""Unit tests for CVE Intelligence collector helpers (no network)."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "cve_intel" / "collect_rh_published_cves.py"


def _load():
    spec = importlib.util.spec_from_file_location("collect_rh_published_cves", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class CollectHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def test_normalize_severity(self):
        self.assertEqual(self.mod.normalize_severity("important"), "Important")
        self.assertEqual(self.mod.normalize_severity("MEDIUM"), "Moderate")
        self.assertEqual(self.mod.normalize_severity("critical"), "Critical")

    def test_normalize_record_preserves_public_date_and_portal(self):
        list_row = {
            "CVE": "CVE-2026-111497",
            "severity": "important",
            "public_date": "2026-10-22T13:35:41Z",
            "bugzilla_description": "brotli OOB write",
            "advisories": ["RHSA-2026:90495"],
            "resource_url": "https://access.redhat.com/hydra/rest/securitydata/cve/CVE-2026-111497.json",
        }
        detail = {
            "threat_severity": "Important",
            "public_date": "2026-10-22T13:35:41Z",
            "details": ["Out-of-bounds write in brotli decoder"],
            "affected_release": [
                {
                    "product_name": "Red Hat Enterprise Linux 9",
                    "advisory": "RHSA-2026:90495",
                }
            ],
            "package_state": [],
            "cvss3": {"cvss3_base_score": "8.1", "cvss3_scoring_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"},
            "bugzilla": {"id": "2558973", "description": "brotli OOB"},
        }
        rec = self.mod.normalize_record(list_row, detail, collected_at="2026-10-29T12:00:00+00:00")
        self.assertEqual(rec["cve_id"], "CVE-2026-111497")
        self.assertEqual(rec["threat_severity"], "Important")
        self.assertEqual(rec["public_date"], "2026-10-22T13:35:41Z")
        self.assertEqual(rec["first_seen_at"], "2026-10-29T12:00:00+00:00")
        self.assertIn("RHSA-2026:90495", rec["advisories"])
        self.assertIn("Red Hat Enterprise Linux 9", rec["products"])
        self.assertEqual(
            rec["portal_url"],
            "https://access.redhat.com/security/cve/cve-2026-111497",
        )
        self.assertEqual(rec["cvss3_score"], 8.1)

    def test_daily_summary(self):
        records = [
            {"public_date": "2026-10-28T01:00:00Z", "threat_severity": "Critical"},
            {"public_date": "2026-10-28T02:00:00Z", "threat_severity": "Important"},
            {"public_date": "2026-10-29T03:00:00Z", "threat_severity": "Moderate"},
        ]
        summary = self.mod.daily_summary(records)
        by_day = {r["pub_day"]: r for r in summary}
        self.assertEqual(by_day["2026-10-28"]["total"], 2)
        self.assertEqual(by_day["2026-10-28"]["Critical"], 1)
        self.assertEqual(by_day["2026-10-28"]["Important"], 1)
        self.assertEqual(by_day["2026-10-29"]["Moderate"], 1)


if __name__ == "__main__":
    unittest.main()
