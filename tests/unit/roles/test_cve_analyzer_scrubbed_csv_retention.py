"""Decision contracts for scrubbed CSV same-job retention.

Mirrors retain_scrubbed_csv.yml without writing files.
"""
from __future__ import annotations

from pathlib import Path


def retention_decision(
    enabled: bool,
    retention_dir: str,
    csv_present: bool,
    allow_ephemeral: bool = False,
) -> str:
    """Return expected retention outcome."""
    if not enabled:
        return "skip"
    if not csv_present:
        return "fail_missing_csv"
    cleaned = (retention_dir or "").strip()
    if not cleaned:
        return "fail_missing_dir"
    if cleaned == "/tmp" or cleaned.startswith("/tmp/"):
        if not allow_ephemeral:
            return "fail_ephemeral"
    return "retain"


def test_disabled_skips() -> None:
    assert retention_decision(False, "", True) == "skip"
    assert retention_decision(False, "/var/lib/cve-analyzer/scrubbed-csv", True) == (
        "skip"
    )


def test_enabled_requires_csv_and_durable_dir() -> None:
    assert retention_decision(True, "", True) == "fail_missing_dir"
    assert retention_decision(True, "/var/lib/x", False) == "fail_missing_csv"
    assert retention_decision(True, "/tmp/retain", True) == "fail_ephemeral"
    assert (
        retention_decision(True, "/tmp/retain", True, allow_ephemeral=True)
        == "retain"
    )
    assert (
        retention_decision(True, "/var/lib/cve-analyzer/scrubbed-csv", True)
        == "retain"
    )


def test_retention_path_layout() -> None:
    root = "/var/lib/cve-analyzer/scrubbed-csv"
    job = "1926"
    stamp = "20261104T145542Z"
    dirname = f"job{job}-{stamp}"
    csv_name = "RHACS_Vulnerability_Report_SCRUBBED_2026-11-04_145354.csv"
    path = f"{root}/{dirname}/{csv_name}"
    meta = f"{root}/{dirname}/validation-meta.json"
    assert path.endswith(".csv")
    assert meta.endswith("validation-meta.json")
    assert "/tmp" not in path


def test_retention_task_file_present() -> None:
    role = Path(__file__).resolve().parents[3] / "roles/cve_analyzer"
    assert (role / "tasks/retain_scrubbed_csv.yml").is_file()
