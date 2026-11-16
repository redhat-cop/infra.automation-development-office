"""Grafana Preflight replicas must reach grafana_install_replicas."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"


def run_overlay(tmp_path: Path, replicas):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    preflight = {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": ["grafana"]},
        "component_options": {"grafana": ["install"]},
        "openshift": {"apps_domain": "apps.example.test"},
        "component_config": {
            "grafana": {
                "hostname": "grafana.apps.example.test",
                "replicas": replicas,
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
            "ADO_SELECTED_COMPONENTS": json.dumps(["grafana"]),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = yaml.safe_load((env_dir / "vars_grafana.yml").read_text(encoding="utf-8"))
    return data


def test_overlay_maps_grafana_replicas(tmp_path: Path) -> None:
    data = run_overlay(tmp_path, 2)
    assert data["grafana_replicas"] == 2
    assert data["grafana_install_replicas"] == 2
    assert data["components_env"]["grafana"]["replicas"] == 2
