#!/usr/bin/env python3
"""CVE Intelligence panel guards — Mythos-style Recent reports only."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
from cve_intel import build_cve_intel_panels as intel  # noqa: E402


class CveIntelPanelsTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("CVE_ANALYZER_CVE_INTEL_PANELS", None)
        os.environ.pop("CVE_ANALYZER_PHASE0_FEATURE_UIDS", None)

    def test_production_uid_never_gets_panels(self):
        self.assertFalse(
            builder._cve_intel_panels_enabled(
                "ado-rhacs-vuln-posture", cve_intel_panels=True
            )
        )

    def test_phase0_requires_flag(self):
        os.environ.pop("CVE_ANALYZER_CVE_INTEL_PANELS", None)
        self.assertFalse(
            builder._cve_intel_panels_enabled(
                "ado-rhacs-vuln-posture-phase0", cve_intel_panels=False
            )
        )
        self.assertTrue(
            builder._cve_intel_panels_enabled(
                "ado-rhacs-vuln-posture-phase0", cve_intel_panels=True
            )
        )

    def test_custom_allowlisted_uid_with_flag(self):
        os.environ["CVE_ANALYZER_PHASE0_FEATURE_UIDS"] = "ado-rhacs-vuln-posture-new"
        self.assertTrue(
            builder._cve_intel_panels_enabled(
                "ado-rhacs-vuln-posture-new", cve_intel_panels=True
            )
        )
        self.assertFalse(
            builder._cve_intel_panels_enabled(
                "ado-rhacs-vuln-posture-new", cve_intel_panels=False
            )
        )

    def test_section_is_recent_reports_only(self):
        panels = intel.intel_section_panels(y_start=10)
        titles = [p.get("title") for p in panels]
        self.assertEqual(titles, ["Recent reports"])
        self.assertEqual(len(panels), 1)

    def test_recent_reports_sql_has_day_columns(self):
        sql = intel.mythos_recent_reports_panel(y=0)["targets"][0]["rawSql"].lower()
        self.assertIn('as "date"', sql)
        self.assertIn('as "total"', sql)
        self.assertIn('as "critical"', sql)
        self.assertIn('as "high"', sql)
        self.assertIn('as "medium"', sql)
        self.assertIn('as "low"', sql)
        self.assertIn('as "note"', sql)
        self.assertIn("generate_series", sql)

    def test_panels_import_from_script_directory(self):
        """AAP runs the builder from the data dir, not the role files dir."""
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            for name in (
                "build_rhacs_vuln_dashboard.py",
                "rhacs_report_analytics.py",
                "image_families.yaml",
            ):
                shutil.copy(FILES / name, data / name)
            csv_path = data / "RHACS_Vulnerability_Report_SCRUBBED_test.csv"
            row = {
                "CVE": "CVE-2026-0001",
                "Severity": "Critical",
                "Cluster": "preprod",
                "Image": "registry.redhat.io/openshift4/ose-console-rhel9@sha256:" + ("a" * 64),
                "Namespace": "openshift-console",
                "Discovered At": "2026-09-01T00:00:00Z",
                "AgeDays": "40",
            }
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
                row2 = dict(row)
                row2["Cluster"] = "preprod-infra"
                row2["CVE"] = "CVE-2026-0002"
                writer.writerow(row2)
            env = os.environ.copy()
            env["CVE_ANALYZER_CVE_INTEL_PANELS"] = "true"
            env["CVE_ANALYZER_CLUSTERS"] = "preprod,preprod-infra"
            # Isolate from developer PYTHONPATH that already includes role files/
            # (otherwise cve_intel imports succeed before staging and this gate
            # never fails).
            env["PYTHONPATH"] = ""
            cmd = [
                sys.executable,
                str(data / "build_rhacs_vuln_dashboard.py"),
                "",
                str(data / "out.json"),
                "--uid",
                "ado-rhacs-vuln-posture-phase0",
                "--data-dir",
                str(data),
                "--families-yaml",
                str(data / "image_families.yaml"),
            ]
            missing = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("No module named 'cve_intel'", missing.stderr)

            pkg = data / "cve_intel"
            pkg.mkdir()
            for name in ("__init__.py", "build_cve_intel_panels.py"):
                shutil.copy(FILES / "cve_intel" / name, pkg / name)
            staged = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
            self.assertEqual(staged.returncode, 0, staged.stderr)
            text = (data / "out.json").read_text(encoding="utf-8")
            self.assertIn("Recent reports", text)
            self.assertLess(len(text.encode("utf-8")), 16 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
