"""CSV wait matching for ocp_wait_operator.

Renders the role's real ``until`` expression. A string variable named
``namespace`` is set on purpose: Jinja ``namespace()`` must not be used.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

ROLE_TASKS = (
    Path(__file__).resolve().parents[3] / "roles/ocp_wait_operator/tasks/main.yml"
)


def _task_code() -> str:
    return "\n".join(
        line
        for line in ROLE_TASKS.read_text().splitlines()
        if not line.lstrip().startswith("#")
    )


def _until_expression() -> str:
    text = _task_code()
    assert "namespace(" not in text, "ocp_wait_operator still calls Jinja namespace()"
    match = re.search(
        r"- name: Wait for Operator CSV to appear\n"
        r"          kubernetes\.core\.k8s_info:.*?until: >-\n"
        r"(?P<body>.*?)\n"
        r"          retries:",
        text,
        re.S,
    )
    assert match, "CSV until expression missing from ocp_wait_operator"
    body = textwrap.dedent(match.group("body"))
    assert "regex_escape" in body
    assert "ocp_wait_operator__csv_match_alt" in body
    return body


def _csv(name: str, phase: str | None) -> dict:
    item = {"metadata": {"name": name}}
    if phase is not None:
        item["status"] = {"phase": phase}
    return item


def _ready(resources: list, substring: str, alt: str, expected: bool) -> bool:
    expr = textwrap.indent(_until_expression().strip(), "            ")
    play = (
        textwrap.dedent(
            f"""
            ---
            - hosts: localhost
              gather_facts: false
              vars:
                namespace: openshift-cnv
                expected_csv_ready: {str(expected).lower()}
                ocp_wait_operator_name_substring: {json.dumps(substring)}
                ocp_wait_operator__csv_match_alt: {json.dumps(alt)}
                ocp_wait_operator__installed_operator_csvs:
                  resources: {json.dumps(resources)}
              tasks:
                - name: CSV wait expression matches expected state
                  ansible.builtin.assert:
                    that:
                      - >-
            """
        )
        + expr
        + "\n                        == expected_csv_ready\n"
    )
    # Unique workdir — pyproject runs pytest with xdist (-n 2).
    with tempfile.TemporaryDirectory(prefix="ado-csv-match-") as tmp:
        work = Path(tmp)
        play_path = work / "play.yml"
        play_path.write_text(play)
        (work / "ansible.cfg").write_text(
            "[defaults]\ncollections_path = "
            + os.path.expanduser("~/.ansible/collections")
            + "\n"
        )
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
        env["ANSIBLE_COLLECTIONS_PATH"] = os.path.expanduser("~/.ansible/collections")
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
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            raise AssertionError(output)
    return True


def test_role_does_not_call_jinja_namespace() -> None:
    text = _task_code()
    assert "namespace(" not in text
    assert text.count("regex_escape") >= 2


@pytest.mark.parametrize(
    ("resources", "substring", "alt", "expected"),
    [
        ([], "kubevirt-hyperconverged", "kubevirthyperconverged", False),
        (
            [_csv("kubevirt-hyperconverged-operator.v4.18.0", "Installing")],
            "kubevirt-hyperconverged",
            "kubevirthyperconverged",
            False,
        ),
        (
            [_csv("kubevirt-hyperconverged-operator.v4.18.0", "Failed")],
            "kubevirt-hyperconverged",
            "kubevirthyperconverged",
            False,
        ),
        (
            [_csv("kubevirt-hyperconverged-operator.v4.18.0", "Succeeded")],
            "kubevirt-hyperconverged",
            "kubevirthyperconverged",
            True,
        ),
        (
            [_csv("cert-manager-operator.v1.15.0", "Succeeded")],
            "kubevirt-hyperconverged",
            "kubevirthyperconverged",
            False,
        ),
        (
            [_csv("kubevirthyperconvergedoperator.v4.18.0", "Succeeded")],
            "kubevirt-hyperconverged",
            "kubevirthyperconverged",
            True,
        ),
        (
            [
                _csv("cert-manager-operator.v1.15.0", "Succeeded"),
                _csv("kubevirt-hyperconverged-operator.v4.18.0", "Installing"),
            ],
            "kubevirt-hyperconverged",
            "kubevirthyperconverged",
            False,
        ),
        (
            [_csv("pack.name+operator.v1", "Succeeded")],
            "name+operator",
            "name+operator",
            True,
        ),
        (
            [_csv("nameXoperator.v1", "Succeeded")],
            "name+operator",
            "name+operator",
            False,
        ),
        (
            [_csv("something.v1", None)],
            "something",
            "something",
            False,
        ),
    ],
)
def test_csv_wait_states(resources, substring, alt, expected) -> None:
    assert _ready(resources, substring, alt, expected)
