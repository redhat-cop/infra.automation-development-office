"""STIG hardening must be audit-first from preflight JSON to the role."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"
SEED = ROOT / "roles/bootstrap_generate_playbook_repo/files/playbooks/rhel/ado-stig-hardening-bootstrap.yml"
JT = ROOT / "roles/bootstrap_controller/files/job_templates/ado-rhel-stig-hardening-bootstrap.jt.yml"
WORKFLOW = ROOT / "roles/bootstrap_controller/files/workflows/ado-rhel-workflow-bootstrap.wf.yml"
VARS_TEMPLATE = ROOT / "roles/bootstrap_generate_env_vars/templates/component_vars.yml.j2"
ROLE = ROOT / "roles/rhel_stig_cac"
MODULE_UTIL = ROOT / "plugins/module_utils/rhel_stig_cac.py"


def run_overlay(tmp_path: Path, stig_config: dict) -> dict:
    env_dir = tmp_path / "env"
    env_dir.mkdir(exist_ok=True)
    preflight = {
        "environment": "t",
        "components": ["stig"],
        "component_config": {"stig": stig_config},
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(OVERLAY)],
        env={
            **os.environ,
            "ADO_PREFLIGHT_JSON": str(preflight_path),
            "ADO_ENV_DIR": str(env_dir),
            "ADO_SELECTED_COMPONENTS": json.dumps(["stig"]),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load((env_dir / "vars_stig.yml").read_text(encoding="utf-8")) or {}


def test_overlay_maps_remediation_inputs(tmp_path: Path) -> None:
    data = run_overlay(
        tmp_path,
        {
            "profile": "RHEL 9 STIG",
            "mode": "Remediate",
            "remediation_approved": True,
            "recovery_confirmed": "true",
            "controls": "RHEL-09-432010, V-258083\nRHEL-09-432010",
            "allow_protected": ["sshd_set_idle_timeout"],
        },
    )
    assert data["stig_mode"] == "remediate"
    assert data["stig_remediation_approved"] is True
    assert data["stig_recovery_confirmed"] is True
    assert data["stig_controls"] == ["RHEL-09-432010", "V-258083"]
    assert data["stig_allow_protected"] == ["sshd_set_idle_timeout"]


def test_overlay_unclear_approval_is_false(tmp_path: Path) -> None:
    data = run_overlay(
        tmp_path,
        {"mode": "remediate", "remediation_approved": "maybe", "recovery_confirmed": "no"},
    )
    assert data["stig_remediation_approved"] is False
    assert data["stig_recovery_confirmed"] is False


def test_overlay_rejects_unknown_mode(tmp_path: Path) -> None:
    data = run_overlay(tmp_path, {"mode": "destroy-everything"})
    assert "stig_mode" not in data


def test_overlay_retired_remediate_key_does_not_remediate(tmp_path: Path) -> None:
    """An old export with remediate=true must not turn into a remediation."""
    data = run_overlay(tmp_path, {"profile": "RHEL 9 STIG", "remediate": True})
    assert "rhel_stig_cac_remediate" not in data
    assert "rhel_stig_cac_remediate" not in (data.get("components_env", {}).get("rhel", {}))
    assert data.get("stig_mode") is None


def test_generated_stig_vars_default_to_audit() -> None:
    text = VARS_TEMPLATE.read_text(encoding="utf-8")
    block = text.split("{% elif component_name == 'stig' %}")[1].split("{% elif")[0]
    values = yaml.safe_load(block.replace("{% else %}", ""))
    assert values["stig_engine"] == "cac"
    assert values["stig_mode"] == "audit"
    assert values["stig_remediation_approved"] is False
    assert values["stig_recovery_confirmed"] is False
    assert "rhel_stig_cac_remediate" not in values


def _survey() -> dict:
    spec = yaml.safe_load(JT.read_text(encoding="utf-8"))["controller_templates"][0]["survey_spec"]["spec"]
    return {question["variable"]: question for question in spec}


def test_job_template_survey_is_audit_first() -> None:
    survey = _survey()
    assert "rhel_stig_cac_remediate" not in survey
    assert survey["stig_engine"]["default"] == "cac"
    assert survey["stig_mode"]["default"] == "audit"
    assert survey["stig_mode"]["choices"] == ["audit", "prepare", "remediate", "verify"]
    assert survey["stig_remediation_approved"]["default"] == "false"
    assert survey["stig_recovery_confirmed"]["default"] == "false"
    assert survey["stig_controls"]["type"] == "textarea"
    assert survey["stig_controls"]["required"] is False
    assert survey["stig_allow_protected"]["required"] is False


def _seed_play() -> dict:
    return yaml.safe_load(SEED.read_text(encoding="utf-8"))[0]


def test_playbook_seed_defaults_and_gates() -> None:
    play = _seed_play()
    text = SEED.read_text(encoding="utf-8")
    assert "rhel_stig_cac_remediate" not in text
    assert "default('cac')" in play["vars"]["rhel_stig_engine"]
    assert "default('audit')" in play["vars"]["rhel_stig_mode"]
    for key in ("rhel_stig_remediation_approved", "rhel_stig_recovery_confirmed"):
        assert "default(false)" in play["vars"][key]
    gate = next(task for task in play["pre_tasks"] if "system_role engine" in task["name"])
    assert gate["when"] == "rhel_stig_engine != 'cac'"
    assert "rhel_stig_remediation_approved | bool" in gate["ansible.builtin.assert"]["that"]
    assert "rhel_stig_recovery_confirmed | bool" in gate["ansible.builtin.assert"]["that"]


def test_playbook_seed_passes_every_input_to_the_role() -> None:
    roles = {entry["role"]: entry for entry in _seed_play()["roles"]}
    cac = roles["infra.automation_development_office.rhel_stig_cac"]
    assert cac["when"] == "rhel_stig_engine == 'cac'"
    assert set(cac["vars"]) == {
        "rhel_stig_cac_profile_label",
        "rhel_stig_cac_mode",
        "rhel_stig_cac_remediation_approved",
        "rhel_stig_cac_recovery_confirmed",
        "rhel_stig_cac_controls",
        "rhel_stig_cac_allow_protected",
    }
    assert roles["infra.automation_development_office.rhel_ext_system_roles"]["when"] == "rhel_stig_engine != 'cac'"


def test_role_defaults_cannot_change_a_host() -> None:
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text(encoding="utf-8"))
    assert defaults["rhel_stig_cac_mode"] == "audit"
    assert defaults["rhel_stig_cac_remediation_approved"] is False
    assert defaults["rhel_stig_cac_recovery_confirmed"] is False
    assert defaults["rhel_stig_cac_controls"] == []
    assert "rhel_stig_cac_remediate" not in defaults


def test_role_tailored_profile_matches_module_utility() -> None:
    role_vars = yaml.safe_load((ROLE / "vars/main.yml").read_text(encoding="utf-8"))
    source = MODULE_UTIL.read_text(encoding="utf-8")
    match = re.search(r'^TAILORED_PROFILE = "([^"]+)"', source, re.MULTILINE)
    assert match
    assert role_vars["rhel_stig_cac_tailored_profile"] == match.group(1)


def test_protected_patterns_cover_lockout_controls() -> None:
    """Real SSG rule names that can lock out access or break the AAP connection."""
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text(encoding="utf-8"))
    patterns = [re.compile(pattern) for pattern in defaults["rhel_stig_cac_protected_patterns"]]

    def protected(rule: str) -> bool:
        return any(pattern.search(rule) for pattern in patterns)

    must_protect = [
        "sysctl_crypto_fips_enabled",
        "configure_crypto_policy",
        "sshd_disable_root_login",
        "sshd_set_idle_timeout",
        "file_permissions_sshd_config",
        "service_sshd_enabled",
        "sssd_enable_smartcards",
        "enable_authselect",
        "accounts_password_pam_minlen",
        "accounts_passwords_pam_faillock_deny",
        "account_password_pam_faillock_system_auth",
        "set_password_hashing_algorithm_logindefs",
        "no_empty_passwords",
        "use_pam_wheel_for_su",
        "sudo_remove_nopasswd",
        "sudo_require_reauthentication",
        "disallow_bypass_password_sudo",
        "configured_firewalld_default_deny",
        "firewalld_sshd_port_enabled",
        "networkmanager_dns_mode",
    ]
    assert [rule for rule in must_protect if not protected(rule)] == []
    harmless = [
        "package_sudo_installed",
        "service_auditd_enabled",
        "kernel_module_bluetooth_disabled",
        "audit_rules_login_events",
        "banner_etc_issue",
        "accounts_umask_etc_profile",
    ]
    assert [rule for rule in harmless if protected(rule)] == []


def test_stig_job_template_is_registered_and_in_the_workflow() -> None:
    configs = (ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml").read_text(encoding="utf-8")
    assert "ado-rhel-stig-hardening-bootstrap.jt.yml" in configs
    assert "RHEL STIG Hardening" in WORKFLOW.read_text(encoding="utf-8")


def test_role_dispatches_every_mode() -> None:
    modes = yaml.safe_load((ROLE / "vars/main.yml").read_text(encoding="utf-8"))["rhel_stig_cac_valid_modes"]
    for mode in modes:
        assert (ROLE / "tasks" / f"{mode}.yml").is_file(), mode


def test_remediation_runs_only_after_every_gate() -> None:
    tasks = yaml.safe_load((ROLE / "tasks/remediate.yml").read_text(encoding="utf-8"))
    names = [task["name"] for task in tasks]
    gate = names.index("Require approval, recovery confirmation, and controls")
    protected = names.index("Refuse protected controls")
    first_scan = names.index("Audit selected controls before remediation")
    remediate = names.index("Remediate selected controls")
    assert gate < names.index("Check STIG CaC prerequisites") < protected < first_scan < remediate
    assert names.index("Audit selected controls after remediation") > remediate


def test_audit_never_installs_or_remediates() -> None:
    for mode in ("audit", "verify"):
        text = (ROLE / "tasks" / f"{mode}.yml").read_text(encoding="utf-8")
        assert "ansible.builtin.package" not in text
        assert "rhel_stig_cac_phase_remediate: true" not in text
    for name in ("prerequisites.yml", "resolve.yml", "scan.yml", "evidence.yml", "finish.yml"):
        assert "ansible.builtin.package" not in (ROLE / "tasks" / name).read_text(encoding="utf-8")
