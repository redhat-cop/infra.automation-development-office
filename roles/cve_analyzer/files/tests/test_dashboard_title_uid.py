"""Dashboard title/UID contract: builder + publish helper (no live Grafana)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import publish_grafana_dashboard as publisher  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402
from tests.test_filterable_rollups import CFG, ROWS  # noqa: E402

PROD_UID = "ado-rhacs-vuln-posture"
PROD_TITLE = "RHACS Vulnerability Posture (ADO)"
PHASE0_UID = "ado-rhacs-vuln-posture-phase0"
CUSTOM_TITLE = "RHACS Vulnerability Posture (ADO) — Lab"


def _analysis() -> dict:
    rows = [dict(r) for r in ROWS]
    analytics.classify_rows(rows, CFG)
    return analytics.build_analysis(
        rows, datetime.now(timezone.utc), CFG, "test"
    )


class DashboardTitleUidTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = _analysis()

    def tearDown(self):
        os.environ.pop("CVE_ANALYZER_PHASE0_FEATURE_UIDS", None)
        os.environ.pop("CVE_ANALYZER_CVE_INTEL_PANELS", None)

    def test_default_title_and_uid(self):
        dash = builder.build_dashboard(
            self.analysis, PROD_TITLE, PROD_UID
        )
        self.assertEqual(dash["uid"], PROD_UID)
        self.assertEqual(dash["title"], PROD_TITLE)

    def test_custom_title_preserves_uid(self):
        dash = builder.build_dashboard(
            self.analysis, CUSTOM_TITLE, PROD_UID
        )
        self.assertEqual(dash["uid"], PROD_UID)
        self.assertEqual(dash["title"], CUSTOM_TITLE)

    def test_explicit_phase0_uid(self):
        dash = builder.build_dashboard(
            self.analysis, PROD_TITLE, PHASE0_UID
        )
        self.assertEqual(dash["uid"], PHASE0_UID)
        self.assertTrue(builder.is_phase0_feature_uid(PHASE0_UID))
        self.assertTrue(builder.phase1_filterable_trend(PHASE0_UID))

    def test_repeated_publish_payload_preserves_uid(self):
        """Simulate two publishes: uid/title stay stable; id reset each time."""
        dash = builder.build_dashboard(
            self.analysis, CUSTOM_TITLE, PROD_UID
        )
        dash["id"] = 42
        dash["version"] = 7
        for _round in range(2):
            payload_dash = dict(dash)
            payload_dash.pop("id", None)
            payload_dash["id"] = None
            payload_dash["version"] = 1
            uid = publisher.resolve_uid(payload_dash, PROD_UID)
            payload_dash["uid"] = uid
            payload_dash["title"] = CUSTOM_TITLE
            self.assertEqual(payload_dash["uid"], PROD_UID)
            self.assertEqual(payload_dash["title"], CUSTOM_TITLE)

    def test_production_uid_refuses_experimental_features(self):
        os.environ["CVE_ANALYZER_PHASE0_FEATURE_UIDS"] = "ado-rhacs-vuln-posture-new"
        self.assertFalse(builder.is_phase0_feature_uid(PROD_UID))
        # Dual Findings-over-time panels are production behavior; CVE Intel is not.
        self.assertTrue(builder.phase1_filterable_trend(PROD_UID))
        self.assertFalse(builder.phase1_hybrid_trend(PROD_UID))
        self.assertFalse(
            builder._cve_intel_panels_enabled(PROD_UID, cve_intel_panels=True)
        )
        dash = builder.build_dashboard(
            self.analysis,
            PROD_TITLE,
            PROD_UID,
            cve_intel_panels=True,
        )
        titles = [p.get("title") for p in dash.get("panels") or []]
        self.assertNotIn("Recent reports", titles)
        trends = [t for t in titles if t and "Findings over time" in t]
        self.assertEqual(len(trends), 2)
        self.assertTrue(any("filterable" in (t or "").lower() for t in trends))
        self.assertTrue(any("legacy" in (t or "").lower() for t in trends))

    def test_phase0_uid_allows_configured_experimental_features(self):
        self.assertTrue(
            builder._cve_intel_panels_enabled(PHASE0_UID, cve_intel_panels=True)
        )
        dash = builder.build_dashboard(
            self.analysis,
            PROD_TITLE,
            PHASE0_UID,
            cve_intel_panels=True,
        )
        self.assertEqual(dash["uid"], PHASE0_UID)
        self.assertTrue(builder.phase1_filterable_trend(PHASE0_UID))

    def test_missing_or_invalid_uid_refused(self):
        with self.assertRaises(ValueError):
            publisher.resolve_uid({"title": PROD_TITLE}, "")
        with self.assertRaises(ValueError):
            publisher.resolve_uid({"uid": ""}, "")
        with self.assertRaises(ValueError):
            publisher.resolve_uid({"uid": "bad uid!"}, "")
        with self.assertRaises(ValueError):
            publisher.resolve_uid({"uid": "x" * 41}, "")

    def test_publish_helper_cli_refuses_empty_uid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dash.json"
            path.write_text(
                json.dumps({"title": PROD_TITLE, "uid": ""}),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GRAFANA_URL": "https://grafana.example",
                "GRAFANA_PASSWORD": "secret",
            }
            proc = subprocess.run(
                [
                    sys.executable,
                    str(FILES / "publish_grafana_dashboard.py"),
                    str(path),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            result = Path(str(path) + ".publish-result.txt").read_text()
            self.assertIn("uid is required", result)

    def test_static_overview_sample_matches_production_identity(self):
        overview = json.loads(
            (FILES / "rhacs-vulnerability-overview.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(overview["uid"], PROD_UID)
        self.assertEqual(overview["title"], PROD_TITLE)


class PublishResponseUidTest(unittest.TestCase):
    def test_response_uid_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dash.json"
            path.write_text(
                json.dumps({"title": PROD_TITLE, "uid": PROD_UID}),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "GRAFANA_URL": "https://grafana.example",
                "GRAFANA_PASSWORD": "secret",
            }

            class _Resp:
                status = 200

                def read(self):
                    return json.dumps(
                        {"uid": "random-generated-uid"}
                    ).encode()

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            argv = [
                "publish_grafana_dashboard.py",
                str(path),
                "--uid",
                PROD_UID,
                "--title",
                PROD_TITLE,
            ]
            with mock.patch(
                "publish_grafana_dashboard.urllib.request.urlopen",
                return_value=_Resp(),
            ):
                with mock.patch.object(sys, "argv", argv):
                    with mock.patch.dict(os.environ, env, clear=False):
                        code = publisher.main()
            self.assertEqual(code, 1)
            result = Path(str(path) + ".publish-result.txt").read_text()
            self.assertIn("expected", result)


if __name__ == "__main__":
    unittest.main()
