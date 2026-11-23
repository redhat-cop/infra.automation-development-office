"""Bootstrap lifecycle with encrypted infrastructure topology, end to end and local.

Runs the real generator (``bootstrap_controller`` with ``generate_env_vars``,
``generate_playbooks`` and ``generate_aap_configs``; no AAP, no OpenShift, no Git
remote) against a synthetic preflight export with vault encryption on, then checks
what a Git push and the two execution paths would see:

* nothing internal is readable in the generated tree (group_vars, playbooks, configs,
  job template surveys), and the vault files are ciphertext that still holds it
* a generated playbook, started the way a Controller job template starts it (survey
  answers blank, vault password supplied, ``vars_files`` from the repository), resolves
  its gateway and DNS defaults from the encrypted environment configuration
* the real ``load_controller_configs.yml`` loads the generated Controller configs and
  every reference resolves
* the generated pre-push gate accepts the generated repository and refuses plaintext
  topology in ``group_vars`` or ``configs``
* a second Bootstrap run converges: no plaintext appears and the references stay

It does not launch a job on a real Controller; that needs a live AAP.

Every hostname, address and password is invented.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "data" / "topology-lifecycle-preflight.fixture.json"
TOPOLOGY = ROOT / "roles/bootstrap_generate_env_vars/files/ado_topology.py"
DEPENDENCIES = ROOT / ".ansible" / "collections"
VAULT_PASSWORD = "fake-e2e-vault-password"
ENV = "molecule"

HAVE_ANSIBLE = shutil.which("ansible-playbook") is not None and shutil.which("ansible-vault") is not None
pytestmark = pytest.mark.skipif(
    not HAVE_ANSIBLE or not DEPENDENCIES.is_dir(),
    reason="needs ansible-playbook, ansible-vault and the collection dependencies in .ansible/collections",
)

ZONE = "lab-a.corp.invalid-zone.io"
MARKERS = (ZONE, "10.77.")
GATEWAY = "10.77.0.1"
DNS = ["10.77.0.53", "10.77.0.54"]
API_HOST = f"https://api.ocp.{ZONE}:6443"
GIT_URL = f"https://git.apps.{ZONE}/redhat-lab/bootstrap-sample.git"
SATELLITE = f"satellite.{ZONE}"

CONVERGE = """---
- name: Generate bootstrap content with topology encryption on
  hosts: localhost
  gather_facts: false
  connection: local
  vars:
    env: molecule
    preflight_json: "{{ playbook_dir }}/ado-preflight-all.json"
    generate_env_vars: true
    generate_env_vars_force: true
    generate_playbooks: true
    generate_aap_configs: true
    apply_aap_configs: false
    generate_env_vars_encrypt_vault_files: true
    bootstrap_generate_env_vars_encrypt_vault_files: true
    bootstrap_generate_env_vars_vault_password_file: "{{ lookup('ansible.builtin.env', 'ANSIBLE_VAULT_PASSWORD_FILE') }}"
    generate_env_vars_encrypt_vault: false
    generate_env_vars_vault_encrypt: false
    generate_env_vars_prompt_encrypt_vault_files:
      user_input: "y"
    generate_env_vars_prompt_encrypt_vault:
      user_input: "y"
    generate_playbook_repo_pause_for_push: false
    generate_playbook_repo_git_push: false
    generate_playbook_repo_git_commit: false
  pre_tasks:
    - name: Keep previous output out of this run
      ansible.builtin.file:
        path: "{{ playbook_dir }}/{{ item }}"
        state: absent
      loop: [playbooks, configs, group_vars, inventory, collections, templates, ado-preflight-all.json]
    - name: Write the synthetic preflight JSON
      ansible.builtin.copy:
        src: ado-preflight-all.fixture.json
        dest: "{{ preflight_json }}"
        mode: "0600"
  roles:
    - role: infra.automation_development_office.bootstrap_controller
"""


class Lifecycle:
    def __init__(self, base: Path):
        self.base = base
        self.repo = base / "repo"
        self.outside = base / "outside"
        self.password_file = self.outside / "vault-pass"
        self.env_dir = self.repo / "group_vars" / "all" / ENV

    def environment(self) -> dict:
        collections = self.base / "cols"
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env.update(
            ANSIBLE_COLLECTIONS_PATH=f"{collections}:{DEPENDENCIES}",
            ANSIBLE_HOST_KEY_CHECKING="false",
            ANSIBLE_FORCE_COLOR="false",
            ANSIBLE_LOCALHOST_WARNING="false",
            ANSIBLE_VAULT_PASSWORD_FILE=str(self.password_file),
            ANSIBLE_HOME=str(self.base / "ansible-home"),
            PYTHONDONTWRITEBYTECODE="1",
        )
        return env

    def run(self, playbook: Path, *extra: str, cwd: Path | None = None, check: bool = True):
        result = subprocess.run(
            ["ansible-playbook", str(playbook), "-i", "localhost,", "-c", "local",
             "--vault-password-file", str(self.password_file), *extra],
            cwd=cwd or self.repo, env=self.environment(), capture_output=True, text=True, check=False,
        )
        if check and result.returncode != 0:
            tail = "\n".join((result.stdout + result.stderr).splitlines()[-40:])
            raise AssertionError(f"ansible-playbook {playbook.name} failed:\n{tail}")
        return result

    def generate(self):
        self.run(self.repo / "converge.yml")

    def plaintext_files(self):
        """Generated files that Git would receive as text."""
        skip_names = {"converge.yml", "ado-preflight-all.json", "ado-preflight-all.fixture.json"}
        for path in sorted(self.repo.rglob("*")):
            if path.is_file() and path.name not in skip_names and not path.name.startswith("_"):
                data = path.read_bytes()
                if not data.startswith(b"$ANSIBLE_VAULT"):
                    yield path, data


@pytest.fixture(scope="module")
def lifecycle(tmp_path_factory):
    base = tmp_path_factory.mktemp("topology-lifecycle")
    state = Lifecycle(base)
    state.repo.mkdir()
    state.outside.mkdir()
    state.password_file.write_text(VAULT_PASSWORD + "\n")
    state.password_file.chmod(0o600)
    (base / "cols" / "ansible_collections" / "infra").mkdir(parents=True)
    (base / "cols" / "ansible_collections" / "infra" / "automation_development_office").symlink_to(ROOT)
    shutil.copy(FIXTURE, state.repo / "ado-preflight-all.fixture.json")
    (state.repo / "converge.yml").write_text(CONVERGE)
    state.generate()
    return state


def test_nothing_internal_is_readable_in_the_generated_repository(lifecycle):
    leaks = [
        str(path.relative_to(lifecycle.repo))
        for path, data in lifecycle.plaintext_files()
        if any(marker.encode() in data for marker in MARKERS)
    ]
    assert leaks == []


def test_audits_report_no_plaintext_topology(lifecycle):
    env = {**os.environ, "ANSIBLE_VAULT_PASSWORD_FILE": str(lifecycle.password_file)}
    for args in (["audit", "--env-dir", str(lifecycle.env_dir)], ["audit-configs", "--configs-dir", str(lifecycle.repo / "configs")]):
        done = subprocess.run([sys.executable, str(TOPOLOGY), *args], capture_output=True, text=True, env=env, check=False)
        assert done.returncode == 0, done.stdout + done.stderr
        assert re.search(r"plaintext topology values(?: in configs)?: 0\b", done.stdout), done.stdout
        assert not any(marker in done.stdout + done.stderr for marker in MARKERS)


def test_vault_files_are_ciphertext_and_still_hold_the_topology(lifecycle):
    for name in ("vault_openshift.yml", "aap_vault.yml"):
        assert (lifecycle.env_dir / name).read_bytes().startswith(b"$ANSIBLE_VAULT"), name
    viewed = subprocess.run(
        ["ansible-vault", "view", str(lifecycle.env_dir / "vault_openshift.yml"), "--vault-password-file", str(lifecycle.password_file)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert API_HOST in viewed
    config_vault = subprocess.run(
        ["ansible-vault", "view", str(lifecycle.env_dir / "aap_vault.yml"), "--vault-password-file", str(lifecycle.password_file)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "vault_topology_cfg_" in config_vault and SATELLITE in config_vault


def test_existing_variable_names_are_kept_and_hold_references(lifecycle):
    infra = yaml.safe_load((lifecycle.env_dir / "infra_config_vars.yml").read_text())
    for name in ("api_host", "apps_domain", "domain"):
        assert str(infra[name]).startswith("{{ vault_topology_infra_config_vars__"), name
    virt = yaml.safe_load((lifecycle.env_dir / "vars_openshift_virt.yml").read_text())
    assert str(virt["provision_openshift_virt_gateway"]).startswith("{{ vault_topology_")
    assert str(virt["openshift_virt_ip_range"]).startswith("{{ vault_topology_")
    assert virt["provision_openshift_virt_prefix_length"] == 24  # sizing stays readable


def test_job_template_survey_defaults_carry_no_topology(lifecycle):
    path = lifecycle.repo / "configs" / "job_templates" / "ado-provision-openshift-virt-vm-bootstrap.jt.yml"
    spec = yaml.safe_load(path.read_text())["controller_templates"][0]["survey_spec"]["spec"]
    by_variable = {q["variable"]: q for q in spec}
    for variable in ("provision_openshift_virt_gateway", "provision_openshift_virt_dns_servers", "provision_openshift_virt_static_ip"):
        assert by_variable[variable]["default"] in ("", None), variable
    assert "10.77" not in json.dumps(spec)
    assert by_variable["provision_openshift_virt_prefix_length"]["default"] == 24


def test_no_generated_job_template_or_workflow_holds_topology(lifecycle):
    env = {**os.environ}
    for sub in ("job_templates", "workflows"):
        files = list((lifecycle.repo / "configs" / sub).glob("*.yml"))
        assert files, sub
    done = subprocess.run(
        [sys.executable, str(TOPOLOGY), "audit-configs", "--configs-dir", str(lifecycle.repo / "configs")],
        capture_output=True, text=True, env=env, check=False,
    )
    assert done.returncode == 0, done.stdout


def test_standalone_playbook_resolves_blank_survey_defaults_from_encrypted_config(lifecycle):
    """A Controller launch passes blank survey answers as extra vars; the playbook must still resolve the defaults."""
    source = lifecycle.repo / "playbooks" / "provision" / "ado-provision-openshift-virt-vm-bootstrap.yml"
    play = yaml.safe_load(source.read_text())[0]
    play.pop("roles", None)
    play["tasks"] = [
        {"ansible.builtin.assert": {"that": [
            f"api_host == {json.dumps(API_HOST)}",
            f"virt_gateway_effective == {json.dumps(GATEWAY)}",
            f"virt_dns_servers_effective == {json.dumps(DNS)}",
            f"'gateway4: {GATEWAY}' in cloud_init_network_data",
            f"'- {DNS[0]}' in cloud_init_network_data and '- {DNS[1]}' in cloud_init_network_data",
            "'vault_topology_' not in cloud_init_network_data",
        ]}},
    ]
    derived = source.with_name("_derived_lifecycle.yml")
    derived.write_text(yaml.safe_dump([play], sort_keys=False))
    lifecycle.run(
        derived, "-e", f"env={ENV}",
        "-e", "provision_openshift_virt_gateway=", "-e", "provision_openshift_virt_dns_servers=",
        "-e", "provision_openshift_virt_static_ip=10.77.0.150",
        cwd=derived.parent,
    )


def test_controller_loads_the_generated_configs_and_every_reference_resolves(lifecycle):
    loader = lifecycle.repo / "_controller_load.yml"
    loader.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"env": ENV},
        "tasks": [
            {"ansible.builtin.include_vars": {"file": f"{lifecycle.env_dir}/aap_vault.yml"}, "no_log": True},
            {"ansible.builtin.find": {"paths": str(lifecycle.env_dir), "patterns": "vault_*.yml"}, "register": "vaults"},
            {"ansible.builtin.include_vars": {"file": "{{ item.path }}"}, "loop": "{{ vaults.files }}", "no_log": True},
            {"ansible.builtin.include_tasks": str(ROOT / "roles/bootstrap_controller/tasks/load_controller_configs.yml")},
            {"ansible.builtin.assert": {"that": [
                f"{json.dumps(SATELLITE)} in (controller_hosts | map(attribute='name') | list)",
                f"{json.dumps(API_HOST)} in (controller_hosts | map(attribute='name') | list)",
                "(controller_hosts | map(attribute='name') | select('search', 'vault_topology_') | list | length) == 0",
                f"controller_projects | map(attribute='scm_url') | select('equalto', {json.dumps(GIT_URL)}) | list | length > 0",
            ]}},
        ],
    }]))
    lifecycle.run(loader, cwd=lifecycle.repo)


def _publication_repo(lifecycle, tmp_path: Path) -> Path:
    repo = tmp_path / "publish"
    shutil.copytree(
        lifecycle.repo, repo,
        ignore=shutil.ignore_patterns("ado-preflight-*.json", "converge.yml", "_*.yml", ".ansible"),
    )
    for name in ("ado_credential_gate.py", "ado_topology_rules.py"):  # shipped by the generator
        assert (repo / ".githooks" / name).is_file(), name
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def _gate(repo: Path):
    subprocess.run(["git", "add", "-A", "-f"], cwd=repo, check=True)
    return subprocess.run(
        [sys.executable, str(repo / ".githooks" / "ado_credential_gate.py"), "--repo", str(repo), "--profile", "repo"],
        capture_output=True, text=True, check=False,
    )


def test_git_publication_accepts_the_generated_repository(lifecycle, tmp_path):
    done = _gate(_publication_repo(lifecycle, tmp_path))
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize(
    ("relative", "reference_key"),
    [
        ("group_vars/all/molecule/infra_config_vars.yml", "api_host"),
        ("configs/controller/hosts.yml", "name"),
    ],
)
def test_git_publication_rejects_plaintext_topology_introduced_later(lifecycle, tmp_path, relative, reference_key):
    repo = _publication_repo(lifecycle, tmp_path)
    target = repo / relative
    data = yaml.safe_load(target.read_text())
    holder = data[next(iter(data))] if relative.startswith("configs") else data
    if isinstance(holder, list):
        holder[1][reference_key] = SATELLITE
    else:
        holder[reference_key] = API_HOST
    target.write_text(yaml.safe_dump(data))
    done = _gate(repo)
    assert done.returncode == 3, done.stdout + done.stderr
    assert "plaintext-topology" in done.stderr
    assert not any(marker in done.stdout + done.stderr for marker in MARKERS)


def test_a_second_bootstrap_run_converges_without_plaintext(lifecycle):
    before = yaml.safe_load((lifecycle.env_dir / "vars_openshift_virt.yml").read_text())
    lifecycle.generate()
    assert [path for path, data in lifecycle.plaintext_files() if any(m.encode() in data for m in MARKERS)] == []
    after = yaml.safe_load((lifecycle.env_dir / "vars_openshift_virt.yml").read_text())
    assert after == before
    assert (lifecycle.env_dir / "aap_vault.yml").read_bytes().startswith(b"$ANSIBLE_VAULT")
    env = {**os.environ, "ANSIBLE_VAULT_PASSWORD_FILE": str(lifecycle.password_file)}
    done = subprocess.run(
        [sys.executable, str(TOPOLOGY), "audit-configs", "--configs-dir", str(lifecycle.repo / "configs")],
        capture_output=True, text=True, env=env, check=False,
    )
    assert done.returncode == 0
