"""Bootstrap must never ship a well-known default admin password.

The user has to set admin/root passwords in the bootstrap (preflight JSON or
form). The overlay stops with a clear message when one is missing, and roles
assert on it. These tests keep ``redhat123`` and similar fallbacks from coming
back.
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
OVERLAY = ROOT / "roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py"
VAULT_TEMPLATE = ROOT / "roles/bootstrap_generate_env_vars/templates/component_vault.yml.j2"
REGISTRY = ROOT / "roles/bootstrap_resolve_component/files/components_defaults.yml"
SEEDS = ROOT / "roles/bootstrap_generate_playbook_repo/files/playbooks"
JOB_TEMPLATES = ROOT / "roles/bootstrap_controller/files/job_templates"

LITERAL = "redhat123"
# Historic wording in overlay error text / comments that explains the removed default.
ALLOWED_TEXT = ("no silent redhat123 default", "admin_htpasswd: redhat123 from old templates")


def run_overlay(tmp_path: Path, component: str, config: dict, options: list[str] | None = None):
    env_dir = tmp_path / "env"
    env_dir.mkdir(exist_ok=True)
    preflight: dict = {
        "environment": "t",
        "components": [component],
        "component_config": {component: config},
    }
    if options:
        preflight["component_options"] = {component: options}
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(OVERLAY)],
        env={
            **os.environ,
            "ADO_PREFLIGHT_JSON": str(preflight_path),
            "ADO_ENV_DIR": str(env_dir),
            "ADO_SELECTED_COMPONENTS": json.dumps([component]),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, env_dir


def source_files() -> list[Path]:
    """Runtime source under roles/, excluding test fixtures and docs."""
    suffixes = {".yml", ".yaml", ".j2", ".py", ".sh"}
    found = []
    for path in (ROOT / "roles").rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts & {"molecule", "tests", "__pycache__"}:
            continue
        found.append(path)
    return found


def test_runtime_source_has_no_default_password_literal() -> None:
    offenders = []
    for path in source_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LITERAL in line and not any(text in line for text in ALLOWED_TEXT):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, "default password literal reintroduced:\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    ("component", "config", "options", "field"),
    [
        ("grafana", {"hostname": "grafana.example"}, None, "component_config.grafana.admin_password"),
        ("gitlab", {"hostname": "gitlab.example"}, None, "component_config.gitlab.root_password"),
        ("quay", {"hostname": "quay.example"}, None, "component_config.quay.admin_password"),
        (
            "minio",
            {"hostname": "minio.example", "oidc_enabled": False},
            None,
            "component_config.minio.root_password",
        ),
        ("acs", {"hostname": "central.example"}, None, "component_config.acs.admin_password"),
    ],
)
def test_overlay_fails_without_password(tmp_path, component, config, options, field) -> None:
    result = run_overlay(tmp_path, component, config, options)[0]
    assert result.returncode != 0
    assert "no password was provided" in result.stderr
    assert field in result.stderr
    assert "there is no default password" in result.stderr


@pytest.mark.parametrize(
    ("component", "config", "options", "vault_file"),
    [
        ("grafana", {"hostname": "g.example", "admin_password": "Chosen-1"}, None, "vault_grafana.yml"),
        (
            "grafana",
            {"hostname": "g.example", "standalone_admin_password": "Chosen-1"},
            ["standalone"],
            "vault_grafana.yml",
        ),
        ("gitlab", {"hostname": "g.example", "root_password": "Chosen-1"}, None, "vault_gitlab.yml"),
        ("quay", {"hostname": "q.example", "admin_password": "Chosen-1"}, None, "vault_quay.yml"),
        (
            "minio",
            {"hostname": "m.example", "oidc_enabled": False, "root_password": "Chosen-1"},
            None,
            "vault_minio.yml",
        ),
        ("acs", {"hostname": "a.example", "admin_password": "Chosen-1"}, None, "vault_acs.yml"),
    ],
)
def test_overlay_keeps_user_supplied_password(tmp_path, component, config, options, vault_file) -> None:
    result, env_dir = run_overlay(tmp_path, component, config, options)
    assert result.returncode == 0, result.stderr
    vault = (env_dir / vault_file).read_text(encoding="utf-8")
    assert "Chosen-1" in vault
    assert LITERAL not in vault


def test_quay_minio_storage_requires_s3_secret(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "quay",
        {"hostname": "q.example", "admin_password": "Chosen-1", "storage_backend": "minio"},
        ["minio"],
    )[0]
    assert result.returncode != 0
    assert "Quay (MinIO-backed storage)" in result.stderr


def test_registry_has_blank_password_defaults() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    components = yaml.safe_load(text)["components_defaults"]
    blank = {
        ("gitlab", "gitlab_install_root_password"),
        ("gitlab", "gitlab_install_admin_password"),
        ("grafana", "grafana_admin_password"),
        ("grafana", "grafana_install_admin_password"),
        ("grafana_standalone", "install_grafana_admin_password"),
        ("quay", "quay_admin_password"),
        ("quay", "ocp_quay_admin_password"),
        ("zabbix", "zabbix_admin_password"),
        ("minio", "minio_root_password"),
    }
    for component, key in blank:
        assert components[component][key] == "", f"{component}.{key} must not carry a default"


def test_playbook_seeds_do_not_default_passwords() -> None:
    for seed in (
        SEEDS / "gitlab/ado-deploy-and-configure-bootstrap.yml",
        SEEDS / "quay/ado-deploy-install-bootstrap.yml",
        SEEDS / "quay/ado-deploy-and-configure-bootstrap.yml",
    ):
        assert LITERAL not in seed.read_text(encoding="utf-8"), seed.name


@pytest.mark.parametrize(
    ("jt_name", "variable", "required"),
    [
        ("ado-install-gitlab-standalone-bootstrap.jt.yml", "gitlab_root_password", True),
        ("ado-install-grafana-standalone-bootstrap.jt.yml", "grafana_admin_password", True),
        ("ado-install-rhbk-standalone-bootstrap.jt.yml", "rhbk_admin_password", True),
        ("ado-deploy-bookstack-bootstrap.jt.yml", "bookstack_admin_password", True),
    ],
)
def test_survey_password_is_required_without_default(jt_name, variable, required) -> None:
    jt = yaml.safe_load((JOB_TEMPLATES / jt_name).read_text(encoding="utf-8"))
    questions = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("variable") == variable:
                questions.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(jt)
    assert questions, f"{variable} survey question missing in {jt_name}"
    for question in questions:
        assert question.get("default", "") == ""
        assert question.get("required") is required


def test_vault_template_emits_no_default_admin_password() -> None:
    text = VAULT_TEMPLATE.read_text(encoding="utf-8")
    assert LITERAL not in text
    assert "zabbix_admin_password: zabbix" not in text
    assert "rootpass123" not in text
    assert "zabbixpass" not in text
    assert "changeme-db" not in text
    assert "change-me-db" not in text


def test_zabbix_overlay_requires_non_default_passwords(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "zabbix",
        {"hostname": "zabbix.example"},
    )[0]
    assert result.returncode != 0
    assert "zabbix" in result.stderr.lower()
    assert "no password was provided" in result.stderr


def test_zabbix_overlay_rejects_upstream_default_admin_password(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "zabbix",
        {
            "hostname": "zabbix.example",
            "admin_password": "zabbix",
            "db_password": "Chosen-db-1",
            "db_root_password": "Chosen-root-1",
        },
    )[0]
    assert result.returncode != 0
    assert "zabbix" in result.stderr.lower()


def test_rhbk_overlay_requires_admin_and_db_password(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "rhbk",
        {"hostname": "keycloak.example"},
    )[0]
    assert result.returncode != 0
    assert "no password was provided" in result.stderr


def test_rhbk_overlay_rejects_changeme_db(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "rhbk",
        {
            "hostname": "keycloak.example",
            "admin_password": "Chosen-admin-1",
            "db_password": "changeme-db",
        },
    )[0]
    assert result.returncode != 0
    assert "changeme-db" in result.stderr


def test_aap_overlay_fails_without_admin_password(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "aap",
        {"hostname": "aap.example", "namespace": "aap"},
    )[0]
    assert result.returncode != 0
    assert "no password was provided" in result.stderr
    assert "aap" in result.stderr.lower()


def test_aap_overlay_preserves_existing_vault_password(tmp_path) -> None:
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vault_aap.yml").write_text(
        "---\naap_admin_password: Existing-keep-me\n",
        encoding="utf-8",
    )
    (env_dir / "vars_aap.yml").write_text("---\n", encoding="utf-8")
    result, out_dir = run_overlay(
        tmp_path,
        "aap",
        {"hostname": "aap.example", "namespace": "aap", "admin_password": ""},
    )
    assert result.returncode == 0, result.stderr
    vault = yaml.safe_load((out_dir / "vault_aap.yml").read_text(encoding="utf-8"))
    assert vault.get("aap_admin_password") == "Existing-keep-me"


def test_dirsrv_overlay_fails_without_manager_password(tmp_path) -> None:
    result = run_overlay(
        tmp_path,
        "389ds",
        {"hostname": "dirsrv.example"},
    )[0]
    assert result.returncode != 0
    assert "no password was provided" in result.stderr
    assert "389ds" in result.stderr


def test_dirsrv_overlay_preserves_existing_manager_password(tmp_path) -> None:
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "vault_dirsrv.yml").write_text(
        "---\ndirsrv:\n  ocp_dirsrv_manager_password: Existing-dm\n  repl_manager_password: ''\n",
        encoding="utf-8",
    )
    (env_dir / "vars_dirsrv.yml").write_text("---\n", encoding="utf-8")
    result, out_dir = run_overlay(
        tmp_path,
        "389ds",
        {"hostname": "dirsrv.example", "ocp_dirsrv_manager_password": ""},
    )
    assert result.returncode == 0, result.stderr
    vault = yaml.safe_load((out_dir / "vault_dirsrv.yml").read_text(encoding="utf-8"))
    assert vault["dirsrv"]["ocp_dirsrv_manager_password"] == "Existing-dm"


def test_registry_rhbk_db_password_blank() -> None:
    components = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["components_defaults"]
    assert components["rhbk"]["rhbk_db_password"] == ""
    assert "changeme" not in str(components["rhbk"].get("rhbk_db_password", "")).lower()
