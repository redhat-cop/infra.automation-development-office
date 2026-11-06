"""MinIO and Developer Hub OIDC client IDs through overlay group_vars.

Runs the real overlay and ``preflight_oidc.py`` against a throwaway env dir.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FILES = Path(
    os.environ.get("ADO_OIDC_FILES_UNDER_TEST") or ROOT / "roles/bootstrap_generate_env_vars/files"
)
OVERLAY = FILES / "overlay_preflight_component_values.py"

GRAFANA = {
    "id": "grafana-client",
    "name": "Grafana",
    "redirect_uris": "https://grafana.apps.example.test/*",
    "web_origins": "https://grafana.apps.example.test",
}
OPENSHIFT = {
    "id": "OpenshiftDev",
    "name": "OpenShift",
    "redirect_uris": "https://oauth.apps.example.test/*",
    "web_origins": "https://oauth.apps.example.test",
}
MINIO = {
    "id": "minio",
    "name": "MinIO",
    "redirect_uris": "https://minio.apps.example.test/*",
    "web_origins": "https://minio.apps.example.test",
}
DEV_HUB = {
    "id": "rhdh",
    "name": "Developer Hub",
    "redirect_uris": "https://backstage.apps.example.test/*",
    "web_origins": "https://backstage.apps.example.test",
}


def _defaults_module():
    sys.path.insert(0, str(FILES))
    try:
        import preflight_oidc

        return preflight_oidc
    finally:
        sys.path.remove(str(FILES))


def rhbk_form(*rows, **extra):
    clients = [copy.deepcopy(row) for row in rows] if rows else [
        copy.deepcopy(GRAFANA),
        copy.deepcopy(OPENSHIFT),
    ]
    return {
        "hostname": "keycloak.apps.example.test",
        "realm": "demo",
        "admin_user": "admin",
        "admin_password": "rhbk-admin-pass-9f2",
        "clients": clients,
        **extra,
    }


def make_preflight(*, rhbk=None, apps=None, options=None, config=None, oauth=None):
    component_config = dict(config or {})
    if rhbk is not None:
        component_config["rhbk"] = rhbk
    opts = {"rhbk": ["client"]}
    if oauth is not None:
        opts["openshift"] = ["oauth_rhbk"]
    opts.update(options or {})
    return {
        "environment": "t",
        "components": ["openshift"],
        "component_apps": {"openshift": list(apps or [])},
        "component_options": opts,
        "openshift": {
            "apps_domain": "apps.example.test",
            "oauth_rhbk": oauth if oauth is not None else {"client_id": "OpenshiftDev"},
        },
        "component_config": component_config,
    }


def run(tmp_path, preflight, selected, *, env_name="env"):
    env_dir = tmp_path / env_name
    env_dir.mkdir(exist_ok=True)
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


# Resolvers -------------------------------------------------------------------


def test_minio_resolver_prefers_oidc_client_id():
    module = _defaults_module()
    assert (
        module.resolve_minio_oidc_client_id_from_config(
            {"oidc_client_id": "minio-ui", "oidc": {"client_id": "minio-nested"}}
        )
        == "minio-ui"
    )


def test_minio_resolver_reads_nested_legacy_field():
    module = _defaults_module()
    assert (
        module.resolve_minio_oidc_client_id_from_config(
            {"oidc": {"client_id": "minio-nested"}}
        )
        == "minio-nested"
    )


def test_minio_resolver_does_not_use_unrelated_fields():
    module = _defaults_module()
    assert module.resolve_minio_oidc_client_id_from_config({}) == ""
    assert (
        module.resolve_minio_oidc_client_id(
            {
                "component_config": {
                    "minio": {},
                    "rhbk": {"clients": [{"id": "grafana-client"}], "client": "grafana-client"},
                }
            }
        )
        == ""
    )


def test_dev_hub_resolver_canonical_then_legacy():
    module = _defaults_module()
    assert (
        module.resolve_dev_hub_keycloak_client_id_from_config(
            {"keycloak_client_id": "hub-a"}
        )
        == "hub-a"
    )
    assert (
        module.resolve_dev_hub_keycloak_client_id_from_config(
            {"oidc_client_id": "legacy-hub"}
        )
        == "legacy-hub"
    )


def test_dev_hub_resolver_legacy_custom_beats_default_canonical():
    module = _defaults_module()
    assert (
        module.resolve_dev_hub_keycloak_client_id_from_config(
            {"keycloak_client_id": "rhdh", "oidc_client_id": "my-rhdh"}
        )
        == "my-rhdh"
    )


def test_dev_hub_resolver_canonical_wins_when_both_custom():
    module = _defaults_module()
    assert (
        module.resolve_dev_hub_keycloak_client_id_from_config(
            {"keycloak_client_id": "hub-a", "oidc_client_id": "hub-b"}
        )
        == "hub-a"
    )


def test_minio_keycloak_ownership_prefers_matching_client_row():
    module = _defaults_module()
    managed = {
        "component_config": {
            "minio": {"oidc_client_id": "minio"},
            "rhbk": {"clients": [{**MINIO}]},
        }
    }
    unmanaged = {
        "component_config": {
            "minio": {"oidc_client_id": "minio-existing"},
            "rhbk": {"clients": [{**MINIO, "id": "minio-existing", "create_client": False}]},
        }
    }
    legacy = {
        "component_config": {
            "minio": {"oidc_client_id": "minio"},
            "rhbk": {"clients": [{**MINIO}]},
        }
    }
    assert module.minio_keycloak_is_managed(managed) is True
    assert module.minio_keycloak_is_managed(unmanaged) is False
    assert module.minio_keycloak_is_managed(legacy) is True
    flag_only = {
        "component_config": {
            "minio": {"oidc_client_id": "minio", "minio_oidc_create_keycloak_client": False},
            "rhbk": {"clients": []},
        }
    }
    assert module.minio_keycloak_is_managed(flag_only) is False
    assert module.minio_role_owns_keycloak_client_id(managed, ["minio", "rhbk"], "minio")
    assert not module.minio_role_owns_keycloak_client_id(managed, ["rhbk"], "minio")
    assert not module.minio_role_owns_keycloak_client_id(managed, ["minio"], "grafana-client")


def test_minio_role_keycloak_tasks_require_manage_flag():
    """Direct playbook and overlay both hit these gates; default true is not enough."""
    text = (
        ROOT / "roles/ocp_minio/tasks/configure-keycloak-oidc.yml"
    ).read_text(encoding="utf-8")
    assert "ocp_minio_manage_keycloak | bool" in text
    assert "ocp_minio_apply_policy_mapper | bool" in text
    create_blocks = text.split("include_role:")
    assert len(create_blocks) >= 3
    for block in create_blocks[1:3]:
        assert "ocp_minio_manage_keycloak | bool" in block
        assert "minio_oidc_create_keycloak_client | default(true)" not in block.split("when:")[-1]


# Overlay group_vars ----------------------------------------------------------


def test_minio_default_client_id_reaches_group_vars(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(MINIO, GRAFANA),
            apps=["rhbk", "minio"],
            options={"minio": ["oidc"]},
            config={"minio": {"oidc_enabled": True}},
        ),
        ["rhbk", "minio"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_minio.yml")
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    assert data["minio_oidc_client_id"] == "minio"
    assert "grafana-client" not in str(data.get("minio_oidc_client_id"))
    assert data["minio_oidc_create_keycloak_client"] is True
    assert data["minio_oidc_create_policy_mapper"] is True
    assert "minio" not in (rhbk_vars.get("rhbk_clients") or {})


def test_minio_custom_oidc_client_id_reaches_group_vars(tmp_path):
    custom = {**copy.deepcopy(MINIO), "id": "minio-custom"}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(custom, GRAFANA),
            apps=["rhbk", "minio"],
            options={"minio": ["oidc"]},
            config={"minio": {"oidc_enabled": True, "oidc_client_id": "minio-custom"}},
        ),
        ["rhbk", "minio"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_minio.yml")
    assert data["minio_oidc_client_id"] == "minio-custom"
    assert data["minio_oidc_client_id"] != "grafana-client"


def test_minio_legacy_nested_oidc_client_id(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form({**copy.deepcopy(MINIO), "id": "minio-nested"}, GRAFANA),
            apps=["rhbk", "minio"],
            options={"minio": ["oidc"]},
            config={
                "minio": {
                    "oidc_enabled": True,
                    "oidc": {"enabled": True, "client_id": "minio-nested"},
                }
            },
        ),
        ["rhbk", "minio"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_minio.yml")
    assert data["minio_oidc_client_id"] == "minio-nested"


def test_minio_canonical_wins_over_nested_conflict(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form({**copy.deepcopy(MINIO), "id": "minio-ui"}, GRAFANA),
            apps=["rhbk", "minio"],
            options={"minio": ["oidc"]},
            config={
                "minio": {
                    "oidc_enabled": True,
                    "oidc_client_id": "minio-ui",
                    "oidc": {"enabled": True, "client_id": "minio-nested"},
                }
            },
        ),
        ["rhbk", "minio"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_minio.yml")
    assert data["minio_oidc_client_id"] == "minio-ui"
    assert data["components_env"]["minio"]["oidc"]["client_id"] == "minio-ui"


def test_minio_unmanaged_client_still_writes_oidc_id(tmp_path):
    unmanaged = {**copy.deepcopy(MINIO), "id": "minio-existing", "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged, GRAFANA),
            apps=["rhbk", "minio"],
            options={"minio": ["oidc"]},
            config={
                "minio": {"oidc_enabled": True, "oidc_client_id": "minio-existing"}
            },
        ),
        ["rhbk", "minio"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    minio_vars = load(env_dir, "vars_minio.yml")
    assert "minio-existing" not in (rhbk_vars.get("rhbk_clients") or {})
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert minio_vars["minio_oidc_client_id"] == "minio-existing"
    assert minio_vars["minio_oidc_create_keycloak_client"] is False
    assert minio_vars["minio_oidc_create_policy_mapper"] is False


def test_minio_legacy_json_without_create_client_is_managed(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(MINIO, GRAFANA),
            apps=["rhbk", "minio"],
            options={"minio": ["oidc"]},
            config={"minio": {"oidc_enabled": True, "oidc_client_id": "minio"}},
        ),
        ["rhbk", "minio"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    minio_vars = load(env_dir, "vars_minio.yml")
    assert "minio" not in (rhbk_vars.get("rhbk_clients") or {})
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert minio_vars["minio_oidc_create_keycloak_client"] is True
    assert minio_vars["minio_oidc_create_policy_mapper"] is True
    assert minio_vars["minio_oidc_client_id"] == "minio"
    assert minio_vars.get("minio_oidc_enabled") is True


def test_mixed_grafana_managed_minio_unmanaged(tmp_path):
    grafana = {"oidc": {"enabled": True, "client_id": "grafana-client"}}
    unmanaged_minio = {**copy.deepcopy(MINIO), "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged_minio, GRAFANA),
            apps=["rhbk", "grafana", "minio"],
            options={"grafana": ["oidc"], "minio": ["oidc"]},
            config={
                "grafana": grafana,
                "minio": {"oidc_enabled": True, "oidc_client_id": "minio"},
            },
        ),
        ["rhbk", "grafana", "minio"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    minio_vars = load(env_dir, "vars_minio.yml")
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert "minio" not in rhbk_vars["rhbk_clients"]
    assert load(env_dir, "vars_grafana.yml")["oidc"]["client_id"] == "grafana-client"
    assert minio_vars["minio_oidc_client_id"] == "minio"
    assert minio_vars["minio_oidc_create_keycloak_client"] is False
    assert minio_vars["minio_oidc_create_policy_mapper"] is False


def test_dev_hub_default_client_id_reaches_group_vars(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(DEV_HUB, GRAFANA),
            apps=["rhbk", "dev_hub"],
            options={"dev_hub": ["oidc"]},
            # Blank canonical field (form default omitted) still writes rhdh.
            config={"dev_hub": {"keycloak_client_id": ""}},
        ),
        ["rhbk", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_dev_hub.yml")
    assert data["dev_hub_keycloak_client_id"] == "rhdh"
    assert "oidc_client_id" not in data
    assert "oidc_client_id" not in (data.get("component_config") or {}).get("dev_hub", {})


def test_dev_hub_custom_keycloak_client_id(tmp_path):
    custom = {**copy.deepcopy(DEV_HUB), "id": "hub-custom"}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(custom, GRAFANA),
            apps=["rhbk", "dev_hub"],
            options={"dev_hub": ["oidc"]},
            config={"dev_hub": {"keycloak_client_id": "hub-custom"}},
        ),
        ["rhbk", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_dev_hub.yml")
    assert data["dev_hub_keycloak_client_id"] == "hub-custom"


def test_dev_hub_legacy_oidc_client_id(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form({**copy.deepcopy(DEV_HUB), "id": "legacy-hub"}, GRAFANA),
            apps=["rhbk", "dev_hub"],
            options={"dev_hub": ["oidc"]},
            config={"dev_hub": {"oidc_client_id": "legacy-hub"}},
        ),
        ["rhbk", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_dev_hub.yml")
    assert data["dev_hub_keycloak_client_id"] == "legacy-hub"
    assert "oidc_client_id" not in data


def test_dev_hub_legacy_custom_beats_imported_default(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form({**copy.deepcopy(DEV_HUB), "id": "my-rhdh"}, GRAFANA),
            apps=["rhbk", "dev_hub"],
            options={"dev_hub": ["oidc"]},
            config={"dev_hub": {"keycloak_client_id": "rhdh", "oidc_client_id": "my-rhdh"}},
        ),
        ["rhbk", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_dev_hub.yml")
    assert data["dev_hub_keycloak_client_id"] == "my-rhdh"
    assert "oidc_client_id" not in data


def test_dev_hub_both_custom_canonical_wins(tmp_path):
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form({**copy.deepcopy(DEV_HUB), "id": "hub-a"}, GRAFANA),
            apps=["rhbk", "dev_hub"],
            options={"dev_hub": ["oidc"]},
            config={"dev_hub": {"keycloak_client_id": "hub-a", "oidc_client_id": "hub-b"}},
        ),
        ["rhbk", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    data = load(env_dir, "vars_dev_hub.yml")
    assert data["dev_hub_keycloak_client_id"] == "hub-a"
    assert "oidc_client_id" not in data


def test_dev_hub_unmanaged_client_still_writes_id(tmp_path):
    unmanaged = {**copy.deepcopy(DEV_HUB), "id": "hub-existing", "create_client": False}
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk_form(unmanaged, GRAFANA),
            apps=["rhbk", "dev_hub"],
            options={"dev_hub": ["oidc"]},
            config={"dev_hub": {"keycloak_client_id": "hub-existing"}},
        ),
        ["rhbk", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    hub_vars = load(env_dir, "vars_dev_hub.yml")
    assert "hub-existing" not in (rhbk_vars.get("rhbk_clients") or {})
    assert list(rhbk_vars["rhbk_clients"]) == ["grafana-client"]
    assert hub_vars["dev_hub_keycloak_client_id"] == "hub-existing"


def test_multi_component_mixed_ownership_and_custom_ids(tmp_path):
    """Grafana managed, OpenShift existing, MinIO/Dev Hub custom IDs."""
    grafana = {"oidc": {"enabled": True, "client_id": "grafana-client"}}
    rhbk = rhbk_form(
        {**copy.deepcopy(OPENSHIFT), "create_client": False, "source": "openshift"},
        {**copy.deepcopy(GRAFANA), "create_client": True, "source": "grafana"},
        {**copy.deepcopy(MINIO), "id": "minio-lab", "create_client": True},
        {**copy.deepcopy(DEV_HUB), "id": "hub-lab", "create_client": False},
        client="OpenshiftDev",
    )
    result, env_dir = run(
        tmp_path,
        make_preflight(
            rhbk=rhbk,
            apps=["rhbk", "grafana", "minio", "dev_hub"],
            options={"grafana": ["oidc"], "minio": ["oidc"], "dev_hub": ["oidc"]},
            config={
                "grafana": grafana,
                "minio": {"oidc_enabled": True, "oidc_client_id": "minio-lab"},
                "dev_hub": {"keycloak_client_id": "hub-lab"},
            },
            oauth={"client_id": "OpenshiftDev"},
        ),
        ["rhbk", "openshift", "grafana", "minio", "dev_hub"],
    )
    assert result.returncode == 0, result.stderr
    rhbk_vars = load(env_dir, "vars_rhbk.yml")
    assert set(rhbk_vars["rhbk_clients"]) == {"grafana-client"}
    assert "minio-lab" not in rhbk_vars["rhbk_clients"]
    assert "OpenshiftDev" not in rhbk_vars["rhbk_clients"]
    assert "hub-lab" not in rhbk_vars["rhbk_clients"]
    assert rhbk_vars["openshift_oidc_auth"]["keycloak_client_id"] == "OpenshiftDev"
    assert load(env_dir, "vars_grafana.yml")["oidc"]["client_id"] == "grafana-client"
    minio_vars = load(env_dir, "vars_minio.yml")
    assert minio_vars["minio_oidc_client_id"] == "minio-lab"
    assert minio_vars["minio_oidc_create_keycloak_client"] is True
    assert minio_vars["minio_oidc_create_policy_mapper"] is True
    assert load(env_dir, "vars_dev_hub.yml")["dev_hub_keycloak_client_id"] == "hub-lab"
    # Passthrough list may still list unmanaged rows; it is not the provision dict.
    passthrough = rhbk_vars.get("clients") or []
    passthrough_ids = {
        str(row.get("id") or "")
        for row in passthrough
        if isinstance(row, dict)
    }
    assert "OpenshiftDev" in passthrough_ids
    assert "hub-lab" in passthrough_ids
