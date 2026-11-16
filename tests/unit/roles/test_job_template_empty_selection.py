"""Empty JT selection must not copy the full files/job_templates catalog."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"


def test_empty_jt_selection_does_not_glob_all_templates() -> None:
    text = TASKS.read_text(encoding="utf-8")
    copy = text[text.find("AAP configs | Copy job templates for generated playbooks only") :]
    copy = copy[: copy.find("AAP configs | Ensure workflow config directory exists")]
    assert "src_dir.glob" not in copy.split("selected =")[1].split("Copied job templates")[0]
    assert "Never dump the full files/job_templates catalog" in copy
    assert "existing.unlink()" in copy
    assert "if not selected:\n        selected = [p.name" not in copy
