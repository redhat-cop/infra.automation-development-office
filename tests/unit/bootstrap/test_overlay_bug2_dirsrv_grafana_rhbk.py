"""Original Bug 2: 389ds + Grafana + RHBK must not invent a 389ds OIDC client.

Grafana still receives grafana-client. 389ds (dirsrv) has no Keycloak client
row, is not an OIDC consumer, and gets no OIDC vars.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FILES = ROOT / "roles/bootstrap_generate_env_vars/files"
OVERLAY = FILES / "overlay_preflight_component_values.py"
PRESETS_APP = (
    Path(os.environ.get("ADO_PREFLIGHT_UI_DIR") or ROOT.parent / "ado-preflight-ui")
    / "src/App.jsx"
)

GRAFANA_CLIENT = {
    "id": "grafana-client",
    "name": "Grafana",
    "source": "grafana",
    "redirect_uris": "https://grafana.apps.example.test/*",
    "web_origins": "https://grafana.apps.example.test",
}


def _oidc():
    spec = importlib.util.spec_from_file_location(
        "preflight_oidc_bug2", FILES / "preflight_oidc.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_preflight():
    return {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": ["rhbk", "grafana", "dirsrv"]},
        "component_options": {"rhbk": ["client"], "grafana": ["oidc"]},
        "openshift": {"apps_domain": "apps.example.test"},
        "component_config": {
            "rhbk": {
                "hostname": "keycloak.apps.example.test",
                "realm": "demo",
                "admin_user": "admin",
                "admin_password": "rhbk-admin-pass-9f2",
                "clients": [dict(GRAFANA_CLIENT)],
            },
            "grafana": {
                "hostname": "grafana.apps.example.test",
                "oidc": {"enabled": True, "client_id": "grafana-client"},
            },
            "dirsrv": {"hostname": "dirsrv.apps.example.test", "replicas": 1},
        },
    }


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


def test_dirsrv_is_not_an_oidc_consumer() -> None:
    keys = {item["key"] for item in _oidc().OIDC_CONSUMERS}
    assert "grafana" in keys
    assert "dirsrv" not in keys
    assert "389ds" not in keys
    assert "389" not in keys


def test_overlay_gives_grafana_a_client_and_dirsrv_none(tmp_path: Path) -> None:
    selected = ["rhbk", "grafana", "dirsrv"]
    result, env_dir = run_overlay(tmp_path, make_preflight(), selected)
    assert result.returncode == 0, result.stderr

    rhbk = load(env_dir, "vars_rhbk.yml")
    grafana = load(env_dir, "vars_grafana.yml")
    dirsrv = load(env_dir, "vars_dirsrv.yml")

    assert rhbk is not None
    provisioned = set(rhbk.get("rhbk_clients") or {})
    assert "grafana-client" in provisioned
    assert provisioned == {"grafana-client"}
    for forbidden in ("dirsrv", "389ds", "389", "ldap"):
        assert forbidden not in provisioned
        assert forbidden not in json.dumps(rhbk.get("rhbk_clients") or {})

    assert grafana is not None
    assert grafana["oidc"]["enabled"] is True
    assert grafana["oidc"]["client_id"] == "grafana-client"

    assert dirsrv is not None
    dumped = json.dumps(dirsrv).lower()
    assert "oidc" not in dumped
    assert "keycloak" not in dumped
    assert "grafana-client" not in dumped


def test_ui_presets_do_not_offer_a_dirsrv_client() -> None:
    if not PRESETS_APP.is_file():
        import pytest

        pytest.skip(f"ado-preflight-ui App.jsx not present: {PRESETS_APP}")
    text = PRESETS_APP.read_text(encoding="utf-8")
    start = text.index("function buildRhbkOidcClientPresets")
    end = text.index("\nfunction ", start + 1)
    fn = text[start:end]
    assert "key: 'grafana'" in fn
    assert "key: 'dirsrv'" not in fn
    assert "source: 'dirsrv'" not in fn
    assert "389ds" not in fn
    assert "389-ds" not in fn
