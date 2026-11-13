"""Original Bug 3: Install AAP and Using/configure AAP stay independent.

Install AAP (pre_installs.install_aap) generates operator-install vars and is
the only overlay path that adds the aap component. Using an existing Controller
(aap.enabled) does not generate install work. Unchecking Install AAP leaves no
vars_aap.yml even when leftover component_config.aap remains.
"""

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
GENERATE_ENV = ROOT / "roles/bootstrap_generate_env_vars/tasks/main.yml"
GENERATE_AAP = ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"
PLAYBOOK_DEFAULTS = ROOT / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
PLAYBOOK_TASKS = ROOT / "roles/bootstrap_generate_playbook_repo/tasks/main.yml"
AAP_CONFIG_J2 = ROOT / "roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2"
UI_APP = (
    Path(os.environ.get("ADO_PREFLIGHT_UI_DIR") or ROOT.parent / "ado-preflight-ui")
    / "src/App.jsx"
)

OCP_INSTALL_JT = "ado-aap-ocp-install-bootstrap.jt.yml"
RHEL_INSTALL_JT = "ado-aap-rhel-install-bootstrap.jt.yml"
OCP_INSTALL_PB = "playbooks/aap/ado-aap-ocp-install-bootstrap.yml"
RHEL_INSTALL_PB = "playbooks/aap/ado-aap-rhel-install-bootstrap.yml"


def base_preflight(**extra):
    data = {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": ["grafana"]},
        "component_options": {},
        "openshift": {"apps_domain": "apps.example.test"},
        "aap": {
            "enabled": False,
            "hostname": "aap.apps.example.test",
            "organization": "ADO",
            "project": "ADO-project",
        },
        "pre_installs": {"install_aap": False, "attach_aap_license": False},
        "component_config": {
            "grafana": {"hostname": "grafana.apps.example.test"},
            "aap": {
                "hostname": "aap.apps.example.test",
                "install_during_bootstrap": False,
                "license_only": False,
                "install_target": "openshift",
            },
        },
    }
    data.update(extra)
    return data


def run_overlay(tmp_path, preflight, selected):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(OVERLAY)],
        env={
            **os.environ,
            "ADO_PREFLIGHT_JSON": str(preflight_path),
            "ADO_ENV_DIR": str(env_dir),
            "ADO_SELECTED_COMPONENTS": json.dumps(selected),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, env_dir


def load(env_dir, name):
    path = env_dir / name
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def test_install_aap_generates_install_vars_without_using_aap(tmp_path: Path) -> None:
    preflight = base_preflight()
    preflight["pre_installs"]["install_aap"] = True
    preflight["aap"]["enabled"] = False
    preflight["component_config"]["aap"]["install_during_bootstrap"] = True
    result, env_dir = run_overlay(tmp_path, preflight, ["grafana"])
    assert result.returncode == 0, result.stderr
    aap = load(env_dir, "vars_aap.yml")
    assert aap is not None
    assert aap["aap_install_during_bootstrap"] is True
    assert aap.get("aap_ocp_install_license_only") is False
    assert load(env_dir, "vars_grafana.yml") is not None


def test_using_existing_aap_does_not_generate_install_vars(tmp_path: Path) -> None:
    preflight = base_preflight()
    preflight["aap"]["enabled"] = True
    preflight["pre_installs"]["install_aap"] = False
    result, env_dir = run_overlay(tmp_path, preflight, ["grafana"])
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_aap.yml") is None
    assert load(env_dir, "vars_grafana.yml") is not None


def test_unchecking_install_aap_drops_generated_install_work(tmp_path: Path) -> None:
    preflight = base_preflight()
    preflight["aap"]["enabled"] = True
    preflight["pre_installs"]["install_aap"] = False
    preflight["pre_installs"]["aap"] = {
        "license_only": False,
        "license_mode": "none",
        "install_target": "openshift",
    }
    preflight["component_config"]["aap"] = {
        "hostname": "aap.apps.example.test",
        "install_during_bootstrap": False,
        "license_only": False,
        "license_mode": "none",
        "install_target": "openshift",
    }
    preflight["components"] = ["openshift"]
    preflight["component_apps"]["openshift"] = ["grafana"]
    result, env_dir = run_overlay(tmp_path, preflight, ["grafana", "openshift"])
    assert result.returncode == 0, result.stderr
    assert load(env_dir, "vars_aap.yml") is None


def test_env_gen_playbook_inclusion_is_install_flag_not_aap_enabled() -> None:
    text = GENERATE_ENV.read_text(encoding="utf-8")
    assert "Skip Contoller API when installing the AAP operator during bootstrap" in text
    assert "bootstrap_generate_env_vars_use_aap: false" in text
    playbook_task = "Include AAP playbook/JT when Install AAP or license attach is requested"
    assert playbook_task in text
    start = text.index(playbook_task)
    end = text.index("\n- name:", start)
    block = text[start:end]
    assert "install_aap" in block
    assert "aap.enabled" not in block
    assert ").enabled" not in block
    use_aap = GENERATE_ENV.read_text(encoding="utf-8")
    assert "bootstrap_generate_env_vars_use_aap:" in use_aap
    assert "preflight.aap" in use_aap or "bootstrap_generate_env_vars_preflight.aap" in use_aap


def test_install_job_templates_and_playbooks_are_aap_component_only() -> None:
    generate = GENERATE_AAP.read_text(encoding="utf-8")
    match = re.search(r"\n      aap:\n((?:        - .+\n)+)", generate)
    assert match, "aap JT map missing"
    mapped = match.group(1)
    assert OCP_INSTALL_JT in mapped
    assert RHEL_INSTALL_JT in mapped
    defaults = PLAYBOOK_DEFAULTS.read_text(encoding="utf-8")
    assert OCP_INSTALL_PB in defaults
    assert RHEL_INSTALL_PB in defaults
    drop = PLAYBOOK_TASKS.read_text(encoding="utf-8")
    assert "Drop unused AAP install target playbook" in drop
    assert OCP_INSTALL_PB in drop
    assert RHEL_INSTALL_PB in drop


def test_controller_config_template_is_not_the_install_playbook() -> None:
    text = AAP_CONFIG_J2.read_text(encoding="utf-8")
    assert "controller_bootstrap_organization" in text
    assert "ado-aap-ocp-install" not in text


def test_ui_set_install_aap_does_not_imply_using_aap() -> None:
    if not UI_APP.is_file():
        import pytest

        pytest.skip(f"ado-preflight-ui App.jsx not present: {UI_APP}")
    text = UI_APP.read_text(encoding="utf-8")
    start = text.index("const setInstallAap = checked => {")
    end = text.index("const setOpenshiftAgent", start)
    fn = text[start:end]
    assert "copy.pre_installs.install_aap = !!checked" in fn
    assert "copy.aap.enabled = false" in fn
    assert "filter(c => c !== 'aap')" in fn
    assert "app !== 'aap'" in fn
    assert "copy.component_config.aap.install_during_bootstrap = false" in fn
    assert "Install AAP is not a platform component selection" in fn
