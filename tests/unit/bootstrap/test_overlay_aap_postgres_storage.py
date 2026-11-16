"""Install AAP managed PostgreSQL storage maps into platform_manifest_overrides.spec.database."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"


def base_preflight(**extra):
    data = {
        "environment": "t",
        "components": [],
        "component_apps": {},
        "component_options": {},
        "openshift": {
            "api_host": "https://api.example.test:6443",
            "token": "sha256~test",
            "apps_domain": "apps.example.test",
        },
        "aap": {
            "enabled": False,
            "admin_username": "admin",
            "admin_password": "admin",
            "hostname": "aap.apps.example.test",
            "organization": "ADO",
            "project": "ADO-project",
        },
        "pre_installs": {
            "install_aap": True,
            "attach_aap_license": False,
            "aap": {"install_target": "openshift", "license_mode": "none"},
        },
        "component_config": {
            "aap": {
                "hostname": "aap.apps.example.test",
                "namespace": "aap-chad",
                "install_during_bootstrap": True,
                "install_target": "openshift",
                "deployment_version": "2.7",
                "storage": "nfs-csi",
                "hub_storage_type": "S3",
                "hub_s3_secret": "hub-s3-secret",
                "database_type": "managed",
                "postgres_storage": "synology-iscsi-storage",
                "postgres_storage_size": "20Gi",
            },
        },
    }
    data.update(extra)
    return data


def run_overlay(tmp_path, preflight, selected=None):
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
            "ADO_SELECTED_COMPONENTS": json.dumps(selected or []),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, env_dir


def load(env_dir, name):
    path = env_dir / name
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def platform_db(aap):
    overrides = aap["aap_ocp_install_platform"]["platform_manifest_overrides"]
    assert "database" not in overrides, (
        "root-level database must not be emitted — aap_utilities merges at CR root"
    )
    return overrides["spec"]["database"]


def test_managed_postgres_storage_maps_to_platform_database_override(tmp_path: Path) -> None:
    result, env_dir = run_overlay(tmp_path, base_preflight())
    assert result.returncode == 0, result.stderr + result.stdout
    aap = load(env_dir, "vars_aap.yml")
    assert aap is not None
    db = platform_db(aap)
    assert db["postgres_storage_class"] == "synology-iscsi-storage"
    assert db["storage_requirements"]["requests"]["storage"] == "20Gi"
    # Hub S3 stays independent of Postgres SC.
    assert aap["aap_ocp_install_hub"]["storage_type"] == "S3"
    assert aap["aap_ocp_install_hub"]["object_storage_s3_secret"] == "hub-s3-secret"


def test_blank_postgres_override_inherits_general_storage(tmp_path: Path) -> None:
    preflight = base_preflight()
    preflight["component_config"]["aap"]["storage"] = "nfs-csi"
    preflight["component_config"]["aap"]["postgres_storage"] = ""
    result, env_dir = run_overlay(tmp_path, preflight)
    assert result.returncode == 0, result.stderr + result.stdout
    db = platform_db(load(env_dir, "vars_aap.yml"))
    assert db["postgres_storage_class"] == "nfs-csi"


def test_blank_postgres_and_general_leaves_storage_class_unset(tmp_path: Path) -> None:
    preflight = base_preflight()
    preflight["component_config"]["aap"]["storage"] = ""
    preflight["component_config"]["aap"]["postgres_storage"] = ""
    result, env_dir = run_overlay(tmp_path, preflight)
    assert result.returncode == 0, result.stderr + result.stdout
    db = platform_db(load(env_dir, "vars_aap.yml"))
    assert "postgres_storage_class" not in db
    assert db["storage_requirements"]["requests"]["storage"] == "20Gi"


def test_external_postgres_uses_database_secret(tmp_path: Path) -> None:
    preflight = base_preflight()
    preflight["component_config"]["aap"]["database_type"] = "external"
    preflight["component_config"]["aap"]["database_secret"] = "ext-pg-secret"
    preflight["component_config"]["aap"]["postgres_storage"] = ""
    result, env_dir = run_overlay(tmp_path, preflight)
    assert result.returncode == 0, result.stderr + result.stdout
    db = platform_db(load(env_dir, "vars_aap.yml"))
    assert db == {"database_secret": "ext-pg-secret"}


def test_existing_platform_manifest_database_keys_are_merged(tmp_path: Path) -> None:
    preflight = base_preflight()
    # Legacy top-level database + already-nested idle flag must both land under spec.
    preflight["component_config"]["aap"]["platform_manifest_overrides"] = {
        "database": {"idle_disabled": True},
        "spec": {"image_pull_policy": "Always"},
    }
    result, env_dir = run_overlay(tmp_path, preflight)
    assert result.returncode == 0, result.stderr + result.stdout
    overrides = load(env_dir, "vars_aap.yml")["aap_ocp_install_platform"][
        "platform_manifest_overrides"
    ]
    assert "database" not in overrides
    assert overrides["spec"]["image_pull_policy"] == "Always"
    assert overrides["spec"]["database"]["idle_disabled"] is True
    assert overrides["spec"]["database"]["postgres_storage_class"] == "synology-iscsi-storage"


def test_aap_utilities_root_combine_simulation_places_database_under_spec(tmp_path: Path) -> None:
    """Document the aap_utilities merge: overrides combine at CR document root."""
    result, env_dir = run_overlay(tmp_path, base_preflight())
    assert result.returncode == 0, result.stderr + result.stdout
    overrides = load(env_dir, "vars_aap.yml")["aap_ocp_install_platform"][
        "platform_manifest_overrides"
    ]
    base_cr = {
        "apiVersion": "aap.ansible.com/v1alpha1",
        "kind": "AnsibleAutomationPlatform",
        "metadata": {"name": "aap-chad", "namespace": "aap-chad"},
        "spec": {
            "controller": {"disabled": False},
            "hub": {"disabled": False},
            "eda": {"disabled": True},
        },
    }

    def deep_merge(a, b):
        out = dict(a)
        for key, value in b.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = deep_merge(out[key], value)
            else:
                out[key] = value
        return out

    merged = deep_merge(base_cr, overrides)
    assert "database" not in merged
    assert merged["spec"]["database"]["postgres_storage_class"] == "synology-iscsi-storage"
    assert merged["spec"]["database"]["storage_requirements"]["requests"]["storage"] == "20Gi"
    assert merged["spec"]["controller"]["disabled"] is False
    assert merged["spec"]["hub"]["disabled"] is False
    assert merged["spec"]["eda"]["disabled"] is True
