"""Custom CPU topology for ocp_virtualization + preference compatibility.

KubeVirt VirtualMachineClusterPreference ``rhel.9`` requires sockets (>=1).
Setting only ``domain.cpu.cores`` yields 0 sockets and admission rejects the VM.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest
import yaml

CREATE_VM = (
    Path(__file__).resolve().parents[3]
    / "roles/ocp_virtualization/tasks/create_vm.yml"
)
DEFAULTS = (
    Path(__file__).resolve().parents[3]
    / "roles/ocp_virtualization/defaults/main.yml"
)


def _custom_compute_task() -> dict:
    tasks = yaml.safe_load(CREATE_VM.read_text())
    matches = [
        t
        for t in tasks
        if isinstance(t, dict)
        and t.get("name") == "Add custom compute when no instance type is selected"
    ]
    assert len(matches) == 1, "custom compute task missing from create_vm.yml"
    return matches[0]


def test_custom_compute_sets_sockets_cores_threads_not_cores_only():
    task = _custom_compute_task()
    expr = task["ansible.builtin.set_fact"]["ocp_virtualization_vm_spec"]
    assert "sockets" in expr
    assert "cpu_cores_per_socket" in expr
    assert "cpu_threads" in expr
    # Old cores-only shape (rejected by rhel.9 preference admission).
    assert "{'cores': cpu_cores" not in expr.replace(" ", "")
    assert task.get("when")


def test_defaults_expose_topology_vars_from_provision_prefix():
    defaults = yaml.safe_load(DEFAULTS.read_text())
    assert "cpu_sockets" in defaults
    assert "cpu_cores_per_socket" in defaults
    assert "cpu_threads" in defaults
    assert "provision_openshift_virt_cpu_sockets" in str(defaults["cpu_sockets"])


def _render_custom_cpu(cpu_cores: int = 2) -> dict:
    """Evaluate the role's combine expression the same way Ansible would."""
    with tempfile.TemporaryDirectory() as tmp:
        result_path = Path(tmp) / "out.json"
        play_path = Path(tmp) / "play.yml"
        play_path.write_text(
            textwrap.dedent(
                f"""
                ---
                - hosts: localhost
                  gather_facts: false
                  vars:
                    result_path: {json.dumps(str(result_path))}
                    cpu_cores: {cpu_cores}
                    cpu_sockets: {cpu_cores}
                    cpu_cores_per_socket: 1
                    cpu_threads: 1
                    memory: 4Gi
                    ocp_virtualization_vm_spec:
                      template:
                        spec:
                          domain:
                            devices: {{}}
                  tasks:
                    - name: Add custom compute when no instance type is selected
                      ansible.builtin.set_fact:
                        ocp_virtualization_vm_spec: >-
                          {{{{
                            ocp_virtualization_vm_spec | combine(
                              {{
                                'template': {{
                                  'spec': {{
                                    'domain': {{
                                      'cpu': {{
                                        'sockets': (
                                          cpu_sockets
                                          | default(cpu_cores | default(2), true)
                                          | int
                                        ),
                                        'cores': (cpu_cores_per_socket | default(1) | int),
                                        'threads': (cpu_threads | default(1) | int)
                                      }},
                                      'memory': {{'guest': memory | default('8Gi')}}
                                    }}
                                  }}
                                }}
                              }},
                              recursive=True
                            )
                          }}}}

                    - name: Attach preference like create_vm assemble step
                      ansible.builtin.set_fact:
                        ocp_virtualization_vm_definition:
                          spec: >-
                            {{{{
                              ocp_virtualization_vm_spec
                              | combine(
                                  {{
                                    'preference': {{
                                      'name': 'rhel.9',
                                      'kind': 'VirtualMachineClusterPreference'
                                    }}
                                  }},
                                  recursive=True
                                )
                            }}}}

                    - name: Write result
                      ansible.builtin.copy:
                        dest: "{{{{ result_path }}}}"
                        content: "{{{{ ocp_virtualization_vm_definition | to_nice_json }}}}"
                """
            )
        )
        env = os.environ.copy()
        env["HOME"] = tmp
        env["XDG_CACHE_HOME"] = str(Path(tmp) / "xdg-cache")
        env["ANSIBLE_LOCAL_TMP"] = str(Path(tmp) / "ansible-tmp")
        env["ANSIBLE_REMOTE_TMP"] = str(Path(tmp) / "ansible-tmp")
        proc = subprocess.run(
            [
                "ansible-playbook",
                str(play_path),
                "-i",
                "localhost,",
                "-c",
                "local",
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "ansible-playbook failed:\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        return json.loads(result_path.read_text())


@pytest.mark.parametrize("vcpus", [1, 2, 4])
def test_rendered_custom_topology_satisfies_rhel9_socket_requirement(vcpus: int):
    rendered = _render_custom_cpu(vcpus)
    cpu = rendered["spec"]["template"]["spec"]["domain"]["cpu"]
    assert cpu["sockets"] == vcpus
    assert cpu["cores"] == 1
    assert cpu["threads"] == 1
    assert cpu["sockets"] * cpu["cores"] * cpu["threads"] == vcpus
    assert rendered["spec"]["template"]["spec"]["domain"]["memory"]["guest"] == "4Gi"
    assert rendered["spec"]["preference"]["name"] == "rhel.9"
