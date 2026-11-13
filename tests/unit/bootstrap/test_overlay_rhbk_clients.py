"""Overlay behavior for Keycloak client removal in preflight JSON.

Runs the real ``overlay_preflight_component_values.py`` against a throwaway
env dir and checks what lands in generated ``vars_rhbk.yml``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(
    os.environ.get("ADO_OVERLAY_SCRIPT_UNDER_TEST")
    or ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"
)

GRAFANA = {
    "id": "grafana-client",
    "name": "Grafana",
    "redirect_uris": "https://grafana.apps.example.test/*",
    "web_origins": "https://grafana.apps.example.test",
}
GITLAB = {
    "id": "gitlab-removed-marker",
    "name": "GitLab",
    "redirect_uris": "https://gitlab.apps.example.test/cb",
    "web_origins": "https://gitlab.apps.example.test",
}


def _generate(tmp_path: Path, rhbk_config: dict) -> dict:
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
                **rhbk_config,
            }
        },
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    env = {
        **os.environ,
        "ADO_PREFLIGHT_JSON": str(preflight_path),
        "ADO_ENV_DIR": str(env_dir),
        "ADO_SELECTED_COMPONENTS": '["rhbk"]',
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    text = (env_dir / "vars_rhbk.yml").read_text(encoding="utf-8")
    return {"text": text, "data": yaml.safe_load(text)}


def _overlay(
    tmp_path: Path,
    *,
    selected: list[str],
    rhbk: dict | None,
    oauth: dict | None = None,
    oauth_requested: bool = True,
) -> tuple[int, str, dict | None]:
    """Run the overlay twice (template pass, then overlay) like the role does."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    config = {}
    if rhbk is not None:
        config["rhbk"] = {
            "hostname": "keycloak.apps.example.test",
            "realm": "demo",
            "admin_password": "rhbk-admin-pass",
            **rhbk,
        }
    preflight = {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": ["rhbk"] if rhbk is not None else []},
        "component_options": {
            "openshift": ["oauth_rhbk"] if oauth_requested else [],
            "rhbk": ["client"],
        },
        "openshift": {"apps_domain": "apps.example.test", "oauth_rhbk": oauth or {}},
        "component_config": config,
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    env = {
        **os.environ,
        "ADO_PREFLIGHT_JSON": str(preflight_path),
        "ADO_ENV_DIR": str(env_dir),
        "ADO_SELECTED_COMPONENTS": json.dumps(selected),
    }
    result = None
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            break
    assert result is not None
    vars_path = env_dir / "vars_rhbk.yml"
    data = yaml.safe_load(vars_path.read_text(encoding="utf-8")) if vars_path.exists() else None
    return result.returncode, result.stderr, data


def test_openshift_oidc_fails_instead_of_using_grafana_client(
    tmp_path: Path,
) -> None:
    """Grafana is the first client; OpenShift OIDC must not inherit it."""
    code, err, data = _overlay(
        tmp_path,
        selected=["rhbk", "openshift"],
        rhbk={"clients": [GRAFANA], "client": GRAFANA["id"]},
    )
    assert code != 0
    assert "OpenShift OIDC" in err
    assert "has no Keycloak client" in err
    assert data is None or "grafana-client" not in str(data.get("openshift_oidc_auth"))


def test_openshift_oidc_uses_explicit_oauth_client_over_first_client(
    tmp_path: Path,
) -> None:
    code, err, data = _overlay(
        tmp_path,
        selected=["rhbk", "openshift"],
        rhbk={"clients": [GRAFANA], "client": GRAFANA["id"]},
        oauth={"client_id": "MyOpenShiftClient"},
    )
    assert code == 0, err
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "MyOpenShiftClient"
    assert data["openshift_oidc_client_id"] == "MyOpenShiftClient"


def test_openshift_oidc_uses_rhbk_openshift_client_id(tmp_path: Path) -> None:
    code, err, data = _overlay(
        tmp_path,
        selected=["rhbk", "openshift"],
        rhbk={
            "clients": [GRAFANA],
            "client": GRAFANA["id"],
            "openshift_oidc_client_id": "OpenshiftDev",
        },
    )
    assert code == 0, err
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"


def test_openshift_oidc_resolves_openshift_specific_client(
    tmp_path: Path,
) -> None:
    ocp = {**GRAFANA, "id": "OpenshiftDev", "name": "OpenShift"}
    code, err, data = _overlay(
        tmp_path,
        selected=["rhbk", "openshift"],
        rhbk={"clients": [GRAFANA, ocp], "client": GRAFANA["id"]},
    )
    assert code == 0, err
    assert data["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"


def test_no_openshift_oidc_request_generates_no_openshift_client(
    tmp_path: Path,
) -> None:
    code, err, data = _overlay(
        tmp_path,
        selected=["rhbk", "openshift"],
        rhbk={"clients": [GRAFANA], "client": GRAFANA["id"]},
        oauth_requested=False,
    )
    assert code == 0, err
    assert "openshift_oidc_client_id" not in data
    assert "grafana-client" not in str(data.get("openshift_oidc_auth", {}))
    assert data["rhbk_clients"].keys() == {GRAFANA["id"]}


def test_stale_openshift_client_from_previous_run_is_dropped(
    tmp_path: Path,
) -> None:
    """A rerun after removing the OpenShift client must not keep its id."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vars_rhbk.yml").write_text(
        "---\nopenshift_oidc_client_id: OpenshiftDev\n"
        "openshift_oidc_auth:\n  keycloak_client_id: OpenshiftDev\n",
        encoding="utf-8",
    )
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
                "clients": [GRAFANA],
            }
        },
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    env = {
        **os.environ,
        "ADO_PREFLIGHT_JSON": str(preflight_path),
        "ADO_ENV_DIR": str(env_dir),
        "ADO_SELECTED_COMPONENTS": '["rhbk","openshift"]',
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    text = (env_dir / "vars_rhbk.yml").read_text(encoding="utf-8")
    assert "OpenshiftDev" not in text


def test_external_keycloak_requires_explicit_openshift_client(
    tmp_path: Path,
) -> None:
    """No local RHBK: the OpenShift client lives in an external Keycloak."""
    oauth = {
        "keycloak_hostname": "kc.external.test",
        "realm": "corp",
        "admin_user": "admin",
        "admin_password": "external-pass",
    }
    code, err, _ = _overlay(tmp_path, selected=["openshift"], rhbk=None, oauth=oauth)
    assert code != 0
    assert "externally managed Keycloak client but no client ID" in err


def test_external_keycloak_with_explicit_client_is_accepted(
    tmp_path: Path,
) -> None:
    oauth = {
        "client_id": "corp-openshift",
        "keycloak_hostname": "kc.external.test",
        "realm": "corp",
        "admin_user": "admin",
        "admin_password": "external-pass",
    }
    code, err, _ = _overlay(tmp_path, selected=["openshift"], rhbk=None, oauth=oauth)
    assert code == 0, err


def test_removed_client_is_absent_from_generated_vars(tmp_path: Path) -> None:
    out = _generate(
        tmp_path,
        {
            "clients": [GRAFANA],
            "clients_dismissed": [GITLAB["id"]],
            "client": GRAFANA["id"],
        },
    )
    assert list(out["data"]["rhbk_clients"]) == [GRAFANA["id"]]
    assert [c["id"] for c in out["data"]["clients"]] == [GRAFANA["id"]]
    # No trace of the removed client, including the UI-only bookkeeping key.
    assert GITLAB["id"] not in out["text"]
    assert "clients_dismissed" not in out["text"]


def test_both_clients_present_when_not_removed(tmp_path: Path) -> None:
    out = _generate(tmp_path, {"clients": [GRAFANA, GITLAB]})
    assert set(out["data"]["rhbk_clients"]) == {GRAFANA["id"], GITLAB["id"]}


@pytest.mark.parametrize("dismissed", [[], ["anything"]])
def test_all_clients_removed_generates_no_client_work(tmp_path: Path, dismissed: list[str]) -> None:
    blank = {"id": "", "name": "", "redirect_uris": "", "web_origins": ""}
    out = _generate(tmp_path, {"clients": [blank], "clients_dismissed": dismissed})
    assert "rhbk_clients" not in out["data"]
    assert "clients_dismissed" not in out["text"]


def test_legacy_export_without_create_client_still_provisions(tmp_path: Path) -> None:
    out = _generate(tmp_path, {"clients": [GRAFANA, GITLAB]})
    assert set(out["data"]["rhbk_clients"]) == {GRAFANA["id"], GITLAB["id"]}


def test_unmanaged_client_is_omitted_from_rhbk_clients(tmp_path: Path) -> None:
    unmanaged = {**GITLAB, "create_client": False}
    out = _generate(tmp_path, {"clients": [GRAFANA, unmanaged], "client": GRAFANA["id"]})
    assert list(out["data"]["rhbk_clients"]) == [GRAFANA["id"]]
    assert GITLAB["id"] not in out["data"]["rhbk_clients"]
    # The row stays in the passthrough clients list (app OIDC still uses the id).
    assert GITLAB["id"] in [c["id"] for c in out["data"]["clients"]]


def test_all_unmanaged_clients_write_no_provision_inputs(tmp_path: Path) -> None:
    unmanaged_ocp = {
        "id": "OpenshiftDev",
        "name": "OpenShift",
        "redirect_uris": "https://oauth.example/*",
        "web_origins": "https://oauth.example",
        "create_client": False,
        "source": "openshift",
    }
    out = _generate(
        tmp_path,
        {
            "clients": [unmanaged_ocp, {**GRAFANA, "create_client": False}],
            "client": "OpenshiftDev",
        },
    )
    assert "rhbk_clients" not in out["data"]
    assert "rhbk_client" not in out["data"]
    assert [c["id"] for c in out["data"]["clients"]] == ["OpenshiftDev", GRAFANA["id"]]


def test_switching_to_unmanaged_drops_prior_rhbk_clients(tmp_path: Path) -> None:
    """Yes then No must not leave a provision entry a later JT can recreate."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vars_rhbk.yml").write_text(
        "---\nrhbk_client: OpenshiftDev\nrhbk_clients:\n  OpenshiftDev:\n"
        "    rhbk_client_name: OpenShift\n  grafana-client:\n    rhbk_client_name: Grafana\n",
        encoding="utf-8",
    )
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
                "client": "OpenshiftDev",
                "clients": [
                    {
                        "id": "OpenshiftDev",
                        "name": "OpenShift",
                        "redirect_uris": "https://oauth.example/*",
                        "web_origins": "https://oauth.example",
                        "create_client": False,
                        "source": "openshift",
                    },
                    {**GRAFANA, "create_client": True},
                ],
            }
        },
    }
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
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
    assert list(data["rhbk_clients"]) == [GRAFANA["id"]]
    assert "OpenshiftDev" not in data["rhbk_clients"]
    assert data.get("rhbk_client") != "OpenshiftDev"


def test_missing_preflight_clients_drops_retained_rhbk_clients(tmp_path: Path) -> None:
    """Seed or hand-edited rhbk_clients cannot survive a regenerate without rows."""
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vars_rhbk.yml").write_text(
        "---\nrhbk_clients:\n  minio:\n    rhbk_client_name: MinIO\n"
        "  leftover:\n    rhbk_client_name: Leftover\n"
        "components_env:\n  rhbk:\n    rhbk_clients:\n      minio:\n"
        "        rhbk_client_name: MinIO\n",
        encoding="utf-8",
    )
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
        [sys.executable, str(SCRIPT)],
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
    assert "rhbk_clients" not in data
    env_rhbk = (data.get("components_env") or {}).get("rhbk") or {}
    assert "rhbk_clients" not in env_rhbk
