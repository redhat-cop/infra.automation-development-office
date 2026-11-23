# SPDX-License-Identifier: GPL-3.0-or-later
"""Roles that need a credential obtain one; none ships a working default.

ocp_quay: supplied value, then the credentials Secret, then the config of an earlier install,
then a generated value. An existing database whose password is unknown stops the run.
install_dirsrv / ocp_dev_hub: the value is supplied, found in the cluster, or generated.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

ROLES = Path(__file__).resolve().parents[3] / "roles"
QUAY_VALUES = ROLES / "ocp_quay" / "tasks" / "resolve_db_credentials_values.yml"

ANSIBLE = shutil.which("ansible-playbook") or str(Path.home() / ".local" / "bin" / "ansible-playbook")


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _run_quay(tmp_path: Path, **inputs) -> subprocess.CompletedProcess[str]:
    play = tmp_path / "play.yml"
    play.write_text(
        textwrap.dedent(
            f"""
            - hosts: localhost
              gather_facts: false
              vars:
                ocp_quay_db_credentials_secret: quay-db-credentials
              tasks:
                - ansible.builtin.include_tasks: {QUAY_VALUES}
                  vars: {json.dumps(inputs)}
                - ansible.builtin.copy:
                    dest: {tmp_path}/out.json
                    content: >-
                      {{{{ {{'password': ocp_quay_db_password_effective,
                      'key': ocp_quay_database_secret_key_effective}} | to_json }}}}
                  no_log: true
            """
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "ANSIBLE_LOCALHOST_WARNING": "False", "ANSIBLE_HOME": str(tmp_path / "ah")}
    return subprocess.run([ANSIBLE, str(play)], capture_output=True, text=True, env=env, check=False)


def _result(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "out.json").read_text())


@pytest.mark.skipif(not Path(ANSIBLE).exists(), reason="ansible-playbook not installed")
class TestQuayDatabaseCredentials:
    base = {"ocp_quay_db_credentials_data": {}, "ocp_quay_existing_config_data": {}}

    def test_fresh_install_generates_strong_values(self, tmp_path: Path) -> None:
        proc = _run_quay(tmp_path, **self.base, ocp_quay_postgres_exists=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        out = _result(tmp_path)
        assert len(out["password"]) >= 32 and len(out["key"]) >= 48
        assert out["password"].isalnum() and out["key"].isalnum()

    def test_supplied_values_win(self, tmp_path: Path) -> None:
        proc = _run_quay(
            tmp_path,
            **self.base,
            ocp_quay_postgres_exists=False,
            ocp_quay_db_password="synthetic-supplied-password",
            ocp_quay_database_secret_key="synthetic-supplied-key",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _result(tmp_path) == {"password": "synthetic-supplied-password", "key": "synthetic-supplied-key"}

    def test_stored_secret_is_reused_so_reruns_do_not_rotate(self, tmp_path: Path) -> None:
        proc = _run_quay(
            tmp_path,
            ocp_quay_db_credentials_data={
                "db-password": _b64("synthetic-stored-password"),
                "database-secret-key": _b64("synthetic-stored-key"),
            },
            ocp_quay_existing_config_data={},
            ocp_quay_postgres_exists=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _result(tmp_path) == {"password": "synthetic-stored-password", "key": "synthetic-stored-key"}

    def test_earlier_install_credentials_are_adopted(self, tmp_path: Path) -> None:
        legacy = yaml.safe_dump(
            {
                "DB_URI": "postgresql://quay:synthetic-legacy-password@postgres-db:5432/quay",
                "DATABASE_SECRET_KEY": "synthetic-legacy-key",
            }
        )
        proc = _run_quay(
            tmp_path,
            ocp_quay_db_credentials_data={},
            ocp_quay_existing_config_data={"config.yaml": _b64(legacy)},
            ocp_quay_postgres_exists=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _result(tmp_path) == {"password": "synthetic-legacy-password", "key": "synthetic-legacy-key"}

    def test_existing_database_with_unknown_password_fails_clearly(self, tmp_path: Path) -> None:
        proc = _run_quay(tmp_path, **self.base, ocp_quay_postgres_exists=True)
        assert proc.returncode != 0
        assert "password could not be found" in proc.stdout + proc.stderr
        assert "ocp_quay_db_password" in proc.stdout + proc.stderr


def _text(*parts: str) -> str:
    return (ROLES.joinpath(*parts)).read_text(encoding="utf-8")


def test_quay_postgres_reads_its_password_from_the_credentials_secret() -> None:
    tasks = _text("ocp_quay", "tasks", "install-quay-operator.yml")
    assert "secretKeyRef" in tasks
    assert "quaypass" not in tasks
    template = _text("ocp_quay", "templates", "quay-config.yaml.j2")
    assert "ocp_quay_db_password_effective" in template
    assert "ocp_quay_database_secret_key_effective" in template


def test_quay_config_render_never_prints_the_database_credentials() -> None:
    for name in ("install-quay-operator.yml", "configure-quay-oidc.yml"):
        doc = yaml.safe_load(_text("ocp_quay", "tasks", name))

        def walk(node):
            if isinstance(node, dict):
                if "ansible.builtin.set_fact" in node and "quay-config.yaml.j2" in json.dumps(node):
                    yield node
                for value in node.values():
                    yield from walk(value)
            elif isinstance(node, list):
                for item in node:
                    yield from walk(item)

        renders = list(walk(doc))
        assert renders, name
        assert all(task.get("no_log") is True for task in renders), name


def test_dirsrv_test_user_password_is_supplied_or_generated() -> None:
    template = _text("install_dirsrv", "templates", "test-user.ldif.j2")
    assert "install_dirsrv_test_user_password_effective" in template
    tasks = _text("install_dirsrv", "tasks", "main.yml")
    assert "test_user_password" in tasks
    assert "ansible.builtin.password" in tasks
    assert "rm -f /tmp/test-user.ldif" in tasks


def test_dev_hub_backend_secret_has_no_shipped_default() -> None:
    defaults = yaml.safe_load(_text("ocp_dev_hub", "defaults", "main.yml"))
    assert defaults["dev_hub_backend_secret"] == ""
    tasks = _text("ocp_dev_hub", "tasks", "install-dev-hub.yml")
    assert "ocp_dev_hub_backend_secret_effective" in tasks
    assert 'BACKEND_SECRET: "{{ dev_hub_backend_secret }}"' not in tasks
    vault = _text("bootstrap_generate_env_vars", "templates", "component_vault.yml.j2")
    assert "changeme" not in vault.lower()
