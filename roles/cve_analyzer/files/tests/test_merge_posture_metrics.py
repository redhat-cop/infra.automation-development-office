"""Merge safety: replace posture families only; no dupes; keep unrelated metrics."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import merge_posture_metrics as merge_mod  # noqa: E402

TRIAGE = (
    "# HELP cve_triage_open unrelated triage gauge\n"
    "# TYPE cve_triage_open gauge\n"
    'cve_triage_open{severity="Critical"} 9\n'
)
OTHER = "unrelated_job_metric{job=\"other\"} 42\n"


def _block(total: int = 4, by_prod: int = 3, by_dev: int = 1) -> str:
    return builder.posture_metrics_text(
        {
            "Total": total,
            "Critical": 2,
            "Important": 1,
            "Moderate": 1,
            "Low": 0,
        },
        by_cluster={
            "prod-cluster": {
                "Total": by_prod,
                "Critical": 2,
                "Important": 1,
                "Moderate": 0,
                "Low": 0,
            },
            "ocp-dev": {
                "Total": by_dev,
                "Critical": 0,
                "Important": 0,
                "Moderate": 1,
                "Low": 0,
            },
        },
        by_ns={
            ("prod-cluster", "aap"): {
                "Total": by_prod,
                "Critical": 2,
                "Important": 1,
                "Moderate": 0,
                "Low": 0,
            },
            ("ocp-dev", "openshift-gitops"): {
                "Total": by_dev,
                "Critical": 0,
                "Important": 0,
                "Moderate": 1,
                "Low": 0,
            },
        },
    )


class MergePostureMetricsSafetyTest(unittest.TestCase):
    def test_preserves_unrelated_and_updates_values(self):
        existing = (
            TRIAGE
            + OTHER
            + "# BEGIN cve_posture\n"
            + 'cve_posture_findings{severity="Total"} 99\n'
            + 'cve_posture_findings_by_cluster{cluster="old",severity="Total"} 1\n'
            + "# END cve_posture\n"
        )
        for merge_fn in (builder.merge_posture_metrics, merge_mod.merge):
            with self.subTest(merge=merge_fn.__module__):
                out = merge_fn(existing, _block(total=4, by_prod=3, by_dev=1))
                self.assertIn("cve_triage_open", out)
                self.assertIn('cve_triage_open{severity="Critical"} 9', out)
                self.assertIn("unrelated_job_metric", out)
                self.assertIn('cve_posture_findings{severity="Total"} 4', out)
                self.assertNotIn('severity="Total"} 99', out)
                self.assertNotIn('cluster="old"', out)
                self.assertIn('cluster="prod-cluster"', out)
                self.assertIn('cluster="ocp-dev"', out)

    def test_repeated_merge_no_duplicate_series(self):
        block_a = _block(total=4, by_prod=3, by_dev=1)
        block_b = _block(total=10, by_prod=7, by_dev=3)
        seed = TRIAGE + OTHER
        for merge_fn in (builder.merge_posture_metrics, merge_mod.merge):
            with self.subTest(merge=merge_fn.__module__):
                once = merge_fn(seed, block_a)
                twice = merge_fn(once, block_b)
                thrice = merge_fn(twice, block_b)
                self.assertEqual(twice, thrice)
                self.assertEqual(
                    twice.count('cve_posture_findings{severity="Total"}'), 1
                )
                self.assertEqual(
                    twice.count("cve_posture_findings_by_cluster{"), 10
                )  # 2 clusters × 5 severities
                self.assertEqual(
                    twice.count("cve_posture_findings_by_ns{"), 10
                )  # 2 ns keys × 5 severities
                self.assertIn('cve_posture_findings{severity="Total"} 10', twice)
                self.assertIn(
                    'cve_posture_findings_by_cluster{cluster="prod-cluster",'
                    'severity="Total"} 7',
                    twice,
                )
                self.assertIn(
                    'cve_posture_findings_by_ns{cluster="prod-cluster",'
                    'rhacs_namespace="aap",severity="Total"} 7',
                    twice,
                )
                self.assertIn("cve_triage_open", twice)
                self.assertIn("unrelated_job_metric", twice)
                # Orphan series outside markers also replaced.
                orphan = once + 'cve_posture_findings{severity="Total"} 77\n'
                cleaned = merge_fn(orphan, block_b)
                self.assertEqual(
                    cleaned.count('cve_posture_findings{severity="Total"}'), 1
                )
                self.assertIn('cve_posture_findings{severity="Total"} 10', cleaned)

    def test_does_not_strip_lookalike_metric_names(self):
        existing = (
            "# HELP cve_posture_findings_extra keep me\n"
            "# TYPE cve_posture_findings_extra gauge\n"
            "cve_posture_findings_extra 1\n"
        )
        out = merge_mod.merge(existing, _block())
        self.assertIn("cve_posture_findings_extra", out)
        self.assertIn('cve_posture_findings{severity="Total"} 4', out)


if __name__ == "__main__":
    unittest.main()
