#!/usr/bin/env python3
"""cve_analyzer_clusters exact-name filter + metrics stay all-cluster."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import rhacs_report_analytics as analytics  # noqa: E402


PAYLOAD = analytics.OCP_DEFAULT_REPO


def _row(cve: str, cluster: str, severity: str = "Critical") -> dict:
    return {
        "CVE": cve,
        "Severity": severity,
        "Cluster": cluster,
        "Image": f"{PAYLOAD}@sha256:{cve[-1] * 64}",
        "Namespace": "openshift-apiserver",
        "Discovered At": "2026-09-01T00:00:00Z",
        "AgeDays": "40",
    }


class ClusterFilterUnitTests(unittest.TestCase):
    def test_empty_keeps_all(self) -> None:
        rows = [
            {"cluster": "prod", "cve": "A"},
            {"cluster": "ocp-dev", "cve": "B"},
        ]
        filtered, meta = analytics.filter_rows_by_clusters(rows, [])
        self.assertEqual(len(filtered), 2)
        self.assertTrue(meta["all_clusters"])

    def test_one_and_two_clusters(self) -> None:
        rows = [
            {"cluster": "prod", "cve": "A"},
            {"cluster": "prod-infra", "cve": "B"},
            {"cluster": "ocp-dev", "cve": "C"},
        ]
        one, meta1 = analytics.filter_rows_by_clusters(rows, ["prod"])
        self.assertEqual([r["cve"] for r in one], ["A"])
        self.assertEqual(meta1["rows_after"], 1)
        two, meta2 = analytics.filter_rows_by_clusters(rows, ["prod", "ocp-dev"])
        self.assertEqual({r["cve"] for r in two}, {"A", "C"})
        self.assertEqual(meta2["selected"], ["prod", "ocp-dev"])

    def test_invalid_cluster_fails(self) -> None:
        rows = [{"cluster": "prod", "cve": "A"}]
        with self.assertRaises(ValueError) as ctx:
            analytics.filter_rows_by_clusters(rows, ["no-such-cluster"])
        self.assertIn("no-such-cluster", str(ctx.exception))
        self.assertIn("Available clusters", str(ctx.exception))

    def test_analyze_paths_metrics_remain_all_cluster(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scrub.csv"
            with path.open("w", newline="", encoding="utf-8") as fh:
                fields = list(_row("CVE-1", "prod").keys())
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerow(_row("CVE-1", "prod", "Critical"))
                writer.writerow(_row("CVE-2", "prod-infra", "Important"))
                writer.writerow(_row("CVE-3", "prod-infra", "Critical"))

            analysis = analytics.analyze_paths(
                path,
                None,
                FILES / "image_families.yaml",
                report_date=datetime(2026, 10, 28, tzinfo=timezone.utc),
                clusters=["prod"],
            )
        self.assertFalse(analysis["cluster_scope"]["all_clusters"])
        self.assertEqual(analysis["cluster_scope"]["rows_after"], 1)
        self.assertEqual(analysis["all"]["finding_occurrences"], 1)
        # Metrics snapshot is unfiltered.
        self.assertEqual(analysis["metrics_scope"], "all_clusters")
        self.assertEqual(analysis["metrics_severity_all_clusters"]["Total"], 3)
        self.assertEqual(analysis["metrics_severity_all_clusters"]["Critical"], 2)
        byc = analysis["metrics_severity_by_cluster"]
        self.assertEqual(byc["prod"]["Total"], 1)
        self.assertEqual(byc["prod-infra"]["Total"], 2)


class ClusterFilterBuilderTests(unittest.TestCase):
    def test_builder_full_and_lite_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            csv_path = data_dir / "RHACS_Vulnerability_Report_SCRUBBED_2026-10-28_120000.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                fields = list(_row("CVE-1", "prod").keys())
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                for i in range(30):
                    cluster = "prod" if i < 20 else "prod-infra"
                    writer.writerow(
                        _row(f"CVE-2026-{i}", cluster, "Critical" if i % 2 == 0 else "Important")
                    )
            (data_dir / "data.json").write_text("[]", encoding="utf-8")
            (data_dir / "installed-images.json").write_text("{}", encoding="utf-8")
            (data_dir / "operator-subscriptions.json").write_text("[]", encoding="utf-8")
            families = FILES / "image_families.yaml"

            def run(out_name: str, extra: list[str], env_extra: dict | None = None) -> dict:
                out = data_dir / out_name
                env = os.environ.copy()
                env.update(env_extra or {})
                cmd = [
                    sys.executable,
                    str(FILES / "build_rhacs_vuln_dashboard.py"),
                    str(data_dir / "data.json"),
                    str(out),
                    "--data-dir",
                    str(data_dir),
                    "--families-yaml",
                    str(families),
                    "--uid",
                    "ado-rhacs-vuln-posture-phase0",
                    "--metrics-out",
                    str(data_dir / "cve_posture.prom"),
                    *extra,
                ]
                proc = subprocess.run(
                    cmd, check=False, capture_output=True, text=True, env=env
                )
                return {
                    "rc": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "size": out.stat().st_size if out.exists() else 0,
                    "out": out,
                }

            all_full = run("all-full.json", [])
            one_full = run("one-full.json", ["--cluster", "prod"])
            two_full = run("two-full.json", ["--cluster", "prod", "--cluster", "prod-infra"])
            one_lite = run("one-lite.json", ["--cluster", "prod", "--lite"])
            bad = run("bad.json", ["--cluster", "missing-cluster"])

            self.assertEqual(all_full["rc"], 0, all_full["stderr"] or all_full["stdout"])
            self.assertEqual(one_full["rc"], 0, one_full["stderr"] or one_full["stdout"])
            self.assertEqual(two_full["rc"], 0, two_full["stderr"] or two_full["stdout"])
            self.assertEqual(one_lite["rc"], 0, one_lite["stderr"] or one_lite["stdout"])
            self.assertNotEqual(bad["rc"], 0)
            self.assertIn("not found", (bad["stderr"] + bad["stdout"]).lower())

            self.assertIn("METRICS_SCOPE all_clusters", one_full["stdout"])
            self.assertIn("dashboard=prod", one_full["stdout"])
            self.assertIn("rows_after=20", one_full["stdout"])
            self.assertIn("rows_after=30", two_full["stdout"])
            self.assertIn("rows_after=30", all_full["stdout"])
            self.assertIn("detail_rows=20", one_full["stdout"])
            self.assertIn("detail_rows=30", all_full["stdout"])
            # Lite drops panel 90; size must shrink vs Full for the same cluster set.
            self.assertLess(one_lite["size"], one_full["size"])
            self.assertIn("detail_rows_embedded=0", one_lite["stdout"])

            prom = (data_dir / "cve_posture.prom").read_text(encoding="utf-8")
            # Last build was lite one-cluster, but gauges must still be all 30 rows.
            self.assertIn("cve_posture_findings", prom)
            # 15 Critical + 15 Important across both clusters in the fixture.
            self.assertRegex(prom, r'cve_posture_findings\{severity="Critical"\} 15')
            self.assertRegex(prom, r'cve_posture_findings\{severity="Important"\} 15')
            self.assertIn("cve_posture_findings_by_cluster", prom)
            self.assertRegex(
                prom,
                r'cve_posture_findings_by_cluster\{cluster="prod",severity="Critical"\} 10',
            )
            self.assertRegex(
                prom,
                r'cve_posture_findings_by_cluster\{cluster="prod-infra",severity="Critical"\} 5',
            )
            self.assertIn("by_cluster_total=30", one_full["stdout"])

            one_dash = json.loads(one_full["out"].read_text(encoding="utf-8"))
            filt = next(
                p
                for p in one_dash["panels"]
                if "filterable" in (p.get("title") or "").lower()
            )
            legacy = next(
                p
                for p in one_dash["panels"]
                if "legacy" in (p.get("title") or "").lower()
            )
            self.assertIn("limited to: prod", filt.get("description") or "")
            self.assertIn("cve_posture_findings_by_cluster", filt["targets"][0]["expr"])
            self.assertIn(
                'cve_posture_findings{job="cve-analyzer-ns-metrics"}',
                legacy["targets"][0]["expr"],
            )


if __name__ == "__main__":
    unittest.main()
