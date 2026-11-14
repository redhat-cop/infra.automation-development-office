"""Hub force-update must not fail org-prefix verify when no JTs were generated."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APPLY = ROOT / "roles/bootstrap_controller/tasks/apply_aap_25_plus.yml"


def test_empty_template_lookup_does_not_assert_on_skipped_register() -> None:
    text = APPLY.read_text(encoding="utf-8")
    assert "Fail if generated organization templates were not found" in text
    assert "bootstrap_controller_org_template_lookup is not skipped" in text
    assert "No generated job or workflow templates to verify" in text
    fail_block = text.split("Fail if generated organization templates were not found", 1)[1]
    fail_when = fail_block.split("- name:", 1)[0]
    assert "is not skipped" in fail_when
