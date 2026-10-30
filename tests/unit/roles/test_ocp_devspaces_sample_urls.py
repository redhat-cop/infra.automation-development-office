"""Blank Dev Spaces sample URLs must not call Jinja namespace()."""
from __future__ import annotations

import os
import pwd
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

ROLE_TASKS = Path(__file__).resolve().parents[3] / "roles/ocp_devspaces/tasks"
FILL = ROLE_TASKS / "fill-custom-sample-urls.yml"
INSTALL = ROLE_TASKS / "install-devspaces.yml"


def test_sample_url_tasks_do_not_call_jinja_namespace() -> None:
    # Comments may mention namespace(); only executable YAML must stay clean.
    text = FILL.read_text() + "\n" + INSTALL.read_text()
    code = re.sub(r"(?m)^\s*#.*$", "", text)
    assert "namespace(" not in code


def _write_and_run(play: str) -> None:
    # Unique workdir per call — pyproject runs pytest with xdist (-n 2).
    with tempfile.TemporaryDirectory(prefix="ado-devspaces-samples-") as tmp:
        work = Path(tmp)
        play_path = work / "play.yml"
        play_path.write_text(play)
        (work / "ansible.cfg").write_text("[defaults]\nhost_key_checking = false\n")
        env = os.environ.copy()
        env.pop("PYTHONNOUSERSITE", None)
        env.pop("PYTHONSAFEPATH", None)
        home = pwd.getpwuid(os.getuid()).pw_dir
        py = f"python{sys.version_info.major}.{sys.version_info.minor}"
        user_site = str(Path(home) / f".local/lib/{py}/site-packages")
        if Path(user_site).is_dir():
            env["PYTHONPATH"] = user_site + os.pathsep + env.get("PYTHONPATH", "")
            env["HOME"] = home
        env["ANSIBLE_CONFIG"] = str(work / "ansible.cfg")
        env["ANSIBLE_LOCAL_TEMP"] = str(work / "ansible-tmp")
        env["ANSIBLE_STDOUT_CALLBACK"] = "default"
        env["ANSIBLE_NOCOLOR"] = "1"
        Path(env["ANSIBLE_LOCAL_TEMP"]).mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["ansible-playbook", str(play_path)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)


@pytest.mark.parametrize("with_namespace", [True, False])
def test_blank_url_is_filled_and_existing_url_is_kept(with_namespace: bool) -> None:
    vars_lines = []
    if with_namespace:
        vars_lines.append("namespace: devspaces")
    vars_lines.extend(
        [
            "ocp_devspaces_hostname: https://che.example.test",
            "ocp_devspaces_custom_samples:",
            "  - displayName: ADO",
            '    url: ""',
            "  - displayName: Kept",
            "    url: https://example.test/mine.yaml",
        ]
    )
    vars_block = "\n".join(f"    {line}" for line in vars_lines)
    play = textwrap.dedent(
        f"""
        ---
        - hosts: localhost
          gather_facts: false
          vars:
            __VARS__
          tasks:
            - ansible.builtin.include_tasks: {FILL}
            - ansible.builtin.assert:
                that:
                  - ocp_devspaces_custom_samples | length == 2
                  - ocp_devspaces_custom_samples[0].url == 'https://che.example.test/dashboard/devfile-registry/devfiles/empty.yaml'
                  - ocp_devspaces_custom_samples[0].displayName == 'ADO'
                  - ocp_devspaces_custom_samples[1].url == 'https://example.test/mine.yaml'
        """
    ).replace("    __VARS__\n", vars_block + "\n")
    _write_and_run(play)


def test_empty_custom_samples_stay_empty() -> None:
    play = textwrap.dedent(
        f"""
        ---
        - hosts: localhost
          gather_facts: false
          vars:
            namespace: devspaces
            ocp_devspaces_hostname: che.example.test
            ocp_devspaces_custom_samples: []
          tasks:
            - ansible.builtin.include_tasks: {FILL}
            - ansible.builtin.assert:
                that:
                  - ocp_devspaces_custom_samples | length == 0
        """
    )
    _write_and_run(play)
