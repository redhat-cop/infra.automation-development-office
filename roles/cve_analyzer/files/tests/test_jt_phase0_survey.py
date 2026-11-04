#!/usr/bin/env python3
"""Contoller JT survey must declare Phase 0 UID/title overrides.

AAP strips undeclared launch extra_vars. Without these survey fields, a
Phase 0 UID override is ignored and publish falls through to production.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
JT_DIR = REPO / "roles" / "bootstrap_controller" / "files" / "job_templates"
REQUIRED_VARS = {
    "cve_analyzer_vuln_dashboard_uid",
    "cve_analyzer_vuln_dashboard_title",
    "cve_analyzer_phase0_publish_only",
}
PHASE0 = "ado-rhacs-vuln-posture-phase0"
PROD = "ado-rhacs-vuln-posture"


class JtPhase0SurveyTest(unittest.TestCase):
    def _survey_vars(self, path: Path) -> dict[str, dict]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        templates = data.get("controller_templates") or []
        self.assertEqual(len(templates), 1, path.name)
        survey = templates[0].get("survey_spec") or {}
        spec = survey.get("spec") or []
        return {item["variable"]: item for item in spec if "variable" in item}

    def test_publish_rhacs_posture_survey_declares_uid_title_gate(self):
        path = JT_DIR / "ado-cve-analyzer-publish-rhacs-posture-bootstrap.jt.yml"
        vars_by_name = self._survey_vars(path)
        self.assertTrue(REQUIRED_VARS.issubset(vars_by_name), vars_by_name.keys())
        uid = vars_by_name["cve_analyzer_vuln_dashboard_uid"]
        self.assertEqual(uid.get("type"), "multiplechoice")
        self.assertIn(PHASE0, uid.get("choices") or [])
        self.assertIn(PROD, uid.get("choices") or [])
        self.assertEqual(uid.get("default"), PHASE0)
        gate = vars_by_name["cve_analyzer_phase0_publish_only"]
        self.assertEqual(gate.get("default"), "true")
        title = vars_by_name["cve_analyzer_vuln_dashboard_title"]
        self.assertEqual(title.get("type"), "text")
        self.assertTrue(title.get("required"))

    def test_full_workflow_survey_declares_uid_title_gate(self):
        path = JT_DIR / "ado-cve-analyzer-full-bootstrap.jt.yml"
        vars_by_name = self._survey_vars(path)
        self.assertTrue(REQUIRED_VARS.issubset(vars_by_name), vars_by_name.keys())
        self.assertEqual(
            vars_by_name["cve_analyzer_vuln_dashboard_uid"].get("default"),
            PHASE0,
        )


if __name__ == "__main__":
    unittest.main()
