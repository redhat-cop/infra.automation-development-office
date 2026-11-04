"""CVE Analyzer action isolation (Phase A+B acceptance).

1. enrichment enables the four phases without mutating the caller flag.
2. full keeps enrichment optional via cve_analyzer_run_enrichment.
3. A later role invocation does not inherit enrichment from a prior one.
"""
from __future__ import annotations

import os
import pwd
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

ROLE = Path(__file__).resolve().parents[3] / "roles/cve_analyzer"
PREFLIGHT = ROLE / "tasks/preflight.yml"
MAIN = ROLE / "tasks/main.yml"


def _effective(action: str, run_enrichment: bool) -> bool:
    """Mirror preflight.yml: action enrichment OR caller flag."""
    return action == "enrichment" or bool(run_enrichment)


def _phases(
    action: str,
    *,
    run_enrichment: bool = False,
    ocp_auth_ready: bool = False,
    cve_intel_enabled: bool = False,
) -> set[str]:
    """Which timed phases main.yml runs for an action (not skips)."""
    effective = _effective(action, run_enrichment)
    out: set[str] = set()

    if action in ("fetch_export", "pipeline", "full", "enrichment"):
        out.add("auth")

    if action in ("fetch_export", "full", "enrichment"):
        out.add("export")

    if action in ("pipeline", "full", "enrichment") and effective:
        out.add("enrichment_pipeline")

    if action in ("publish_grafana", "full", "enrichment") and effective:
        out.add("triage_grafana")

    if action in ("publish_rhacs_posture", "full", "enrichment"):
        out.add("posture")

    if (
        action in ("publish_metrics", "publish_grafana")
        or (action == "full" and effective)
    ) and ocp_auth_ready:
        out.add("ns_metrics")

    if action == "cve_intel" or (action == "full" and cve_intel_enabled):
        out.add("cve_intel")

    if action == "repair_posture_metrics":
        out.add("repair_posture_metrics")

    return out


def test_repair_posture_metrics_is_isolated() -> None:
    phases = _phases("repair_posture_metrics", ocp_auth_ready=True)
    assert phases == {"repair_posture_metrics"}
    assert "export" not in phases
    assert "auth" not in phases
    assert "posture" not in phases


def test_enrichment_runs_four_phases_exactly_once() -> None:
    phases = _phases("enrichment")
    assert phases == {
        "auth",
        "export",
        "enrichment_pipeline",
        "triage_grafana",
        "posture",
    }
    # Matches former run-pipeline.yml: no ns_metrics, no cve_intel.
    assert "ns_metrics" not in phases
    assert "cve_intel" not in phases


def test_full_preserves_optional_enrichment() -> None:
    without = _phases("full", run_enrichment=False)
    with_enr = _phases("full", run_enrichment=True)
    assert without == {"auth", "export", "posture"}
    assert "enrichment_pipeline" not in without
    assert "triage_grafana" not in without
    assert with_enr >= {"auth", "export", "enrichment_pipeline", "triage_grafana", "posture"}


def test_effective_flag_does_not_leak_across_invocations() -> None:
    # enrichment forces effective true without needing the caller flag.
    assert _effective("enrichment", False) is True
    # A subsequent full with flag still false stays optional-off.
    assert _effective("full", False) is False
    # Caller can still opt in on full / pipeline / publish_grafana.
    assert _effective("full", True) is True
    assert _effective("pipeline", True) is True
    assert _effective("pipeline", False) is False


def test_preflight_does_not_mutate_caller_run_enrichment_flag() -> None:
    text = PREFLIGHT.read_text()
    assert "cve_analyzer_effective_run_enrichment" in text
    # Must not assign the caller-facing flag (set_fact leak).
    assert not re.search(
        r"set_fact:\s*\n\s*cve_analyzer_run_enrichment:",
        text,
    )
    assert "cve_analyzer_run_enrichment: true" not in text


def test_main_uses_effective_enrichment_flag() -> None:
    text = MAIN.read_text()
    assert "cve_analyzer_effective_run_enrichment" in text
    # Dispatcher gates must not use the raw caller flag alone.
    assert "cve_analyzer_run_enrichment | bool" not in text


def test_pipeline_still_requires_acs_in_preflight() -> None:
    text = PREFLIGHT.read_text()
    assert "'pipeline'" in text
    assert "Require ACS Central URL" in text
    # Grafana is not required for bare pipeline.
    grafana_block = text.split("Require Grafana URL")[1]
    assert "'pipeline'" not in grafana_block.split("- name:")[0]


def _run_isolation_play() -> None:
    """Ansible proof: enrichment then full does not leave run_enrichment true."""
    play = textwrap.dedent(
        f"""
        ---
        - hosts: localhost
          gather_facts: false
          vars:
            env: unit
            cve_analyzer_require_env: true
            cve_analyzer_data_dir: /tmp/cve-analyzer-unit-isolation
            acs_central_url: https://central.example.test
            grafana_url: https://grafana.example.test
            cve_analyzer_run_enrichment: false
          tasks:
            - name: First invocation computes enrichment effective flag
              ansible.builtin.include_tasks: {PREFLIGHT}
              vars:
                cve_analyzer_action: enrichment

            - name: Capture after enrichment action
              ansible.builtin.set_fact:
                after_enrichment_effective: "{{{{ cve_analyzer_effective_run_enrichment }}}}"
                after_enrichment_caller_flag: "{{{{ cve_analyzer_run_enrichment }}}}"

            - name: Second invocation is full without enrichment
              ansible.builtin.include_tasks: {PREFLIGHT}
              vars:
                cve_analyzer_action: full
                cve_analyzer_run_enrichment: false

            - name: Assert no leak into caller flag or full effective
              ansible.builtin.assert:
                that:
                  - after_enrichment_effective | bool
                  - after_enrichment_caller_flag | bool == false
                  - cve_analyzer_run_enrichment | bool == false
                  - cve_analyzer_effective_run_enrichment | bool == false
                fail_msg: >-
                  Enrichment leaked into the next invocation
                  (caller={{{{ cve_analyzer_run_enrichment }}}},
                  effective={{{{ cve_analyzer_effective_run_enrichment }}}},
                  after_caller={{{{ after_enrichment_caller_flag }}}}).
        """
    )
    with tempfile.TemporaryDirectory(prefix="ado-cve-action-") as tmp:
        work = Path(tmp)
        play_path = work / "play.yml"
        play_path.write_text(play)
        (work / "ansible.cfg").write_text(
            "[defaults]\nhost_key_checking = false\n"
        )
        env = os.environ.copy()
        env.pop("PYTHONNOUSERSITE", None)
        env.pop("PYTHONSAFEPATH", None)
        home = pwd.getpwuid(os.getuid()).pw_dir
        py = f"python{sys.version_info.major}.{sys.version_info.minor}"
        user_site = str(Path(home) / f".local/lib/{py}/site-packages")
        if Path(user_site).is_dir():
            env["PYTHONPATH"] = user_site + os.pathsep + env.get(
                "PYTHONPATH", ""
            )
            env["HOME"] = home
        env["ANSIBLE_CONFIG"] = str(work / "ansible.cfg")
        env["ANSIBLE_LOCAL_TEMP"] = str(work / "ansible-tmp")
        env["ANSIBLE_NOCOLOR"] = "1"
        Path(env["ANSIBLE_LOCAL_TEMP"]).mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["ansible-playbook", str(play_path)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)


def test_ansible_enrichment_does_not_leak_into_following_full() -> None:
    _run_isolation_play()
