"""RHBK client-only runs must not pull in install, scopes, or the exporter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
GENERATE = ROOT / "roles/bootstrap_generate_env_vars/tasks/main.yml"
JT_MAP = ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"
PLAYBOOKS = ROOT / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"


def test_client_scopes_playbook_is_not_tagged_as_rhbk_client() -> None:
    text = PLAYBOOKS.read_text(encoding="utf-8")
    items = yaml.safe_load(text)["bootstrap_generate_playbook_repo_generated_playbooks"]
    by_dest = {item["dest"]: item["app"] for item in items}
    assert by_dest["playbooks/rhbk/ado-manage-client-bootstrap.yml"] == "rhbk_client"
    assert by_dest["playbooks/rhbk/ado-manage-client-scope-bootstrap.yml"] == "rhbk_client_scopes"
    assert (
        by_dest["playbooks/rhbk/ado-rhbk-login-events-exporter-bootstrap.yml"]
        == "rhbk_login_events_exporter"
    )
    assert by_dest["playbooks/rhbk/ado-deploy-and-configure-bootstrap.yml"] == "rhbk"


def test_rhbk_jt_map_splits_install_from_exporter() -> None:
    text = JT_MAP.read_text(encoding="utf-8")
    assert "ado-rhbk-login-events-exporter-bootstrap.jt.yml" in text
    rhbk_block = text[text.find("      rhbk:"): text.find("      rhbk_login_events_exporter:")]
    assert "ado-rhbk-deploy-and-configure-bootstrap.jt.yml" in rhbk_block
    assert "ado-rhbk-login-events-exporter-bootstrap.jt.yml" not in rhbk_block
    assert "ado-install-rhbk-standalone-bootstrap.jt.yml" not in rhbk_block


def test_playbook_components_gate_rhbk_install_like_grafana() -> None:
    text = GENERATE.read_text(encoding="utf-8")
    assert "| reject('equalto', 'rhbk')" in text
    rhbk_install = text[text.find("            ['rhbk']"):]
    rhbk_install = rhbk_install[: rhbk_install.find("            ['rhbk_standalone']")]
    assert "'install' in (" in rhbk_install
    assert "| length" in rhbk_install
    exporter = text[text.find("            ['rhbk_login_events_exporter']"):]
    exporter = exporter[: exporter.find("            ['quay_oidc']")]
    assert "login_events_exporter_enabled | default(false) | bool" in exporter
    scopes = text[text.find("              ['rhbk_client_scopes']"):]
    scopes = scopes[: scopes.find("              ['rhbk_mapper']")]
    assert "oauth_rhbk" not in scopes
    assert "'client_scopes' in (" in scopes


def test_overlay_defaults_login_exporter_off(tmp_path: Path) -> None:
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    preflight = {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": ["rhbk"]},
        "component_options": {"rhbk": ["client"]},
        "openshift": {"apps_domain": "apps.example.test"},
        "component_config": {
            "rhbk": {
                "hostname": "keycloak.apps.example.test",
                "realm": "demo",
            }
        },
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(OVERLAY)],
        env={
            **os.environ,
            "ADO_PREFLIGHT_JSON": str(preflight_path),
            "ADO_ENV_DIR": str(env_dir),
            "ADO_SELECTED_COMPONENTS": '["rhbk"]',
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = yaml.safe_load((env_dir / "vars_rhbk.yml").read_text(encoding="utf-8"))
    assert data["keycloak_login_events_exporter_enabled"] is False
