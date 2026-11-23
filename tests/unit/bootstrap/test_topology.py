"""Internal infrastructure topology is Vault-encrypted when written to Git.

Covers the router (``ado_topology.py``), the way ``bootstrap_generate_env_vars``
wires it around generation, and that every generated playbook loads the vault
file that holds the topology for the plaintext files it loads (so roles and old
generated playbooks keep working without an edit).

Every hostname, address and token here is invented (``*.example.internal``).
"""
from __future__ import annotations

import copy
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = ROOT / "roles/bootstrap_generate_env_vars/files"
TOPOLOGY = ENV_FILES / "ado_topology.py"
TASKS = ROOT / "roles/bootstrap_generate_env_vars/tasks"
PLAYBOOKS = ROOT / "roles/bootstrap_generate_playbook_repo/files"

_SPEC = importlib.util.spec_from_file_location("ado_topology", TOPOLOGY)
assert _SPEC is not None and _SPEC.loader is not None
topo = importlib.util.module_from_spec(_SPEC)
sys.modules["ado_topology"] = topo
_SPEC.loader.exec_module(topo)

HAVE_ANSIBLE = shutil.which("ansible-vault") is not None and shutil.which("ansible-playbook") is not None

# Invented values. Real environments use their own; none of these resolve.
API = "https://api.lab-a.example.internal:6443"
APPS = "apps.lab-a.example.internal"
GRAFANA = "grafana.apps.lab-a.example.internal"
SMTP = "smtp.relay.lab-a.example.internal"
SAT = "satellite.lab-a.example.internal"
HUB = "hub.apps.lab-a.example.internal"
ADDRESS = "10.20.30.40"
ALL_VALUES = (API, APPS, GRAFANA, SMTP, SAT, HUB, ADDRESS, "lab-a.example.internal")

# example.internal is a documented placeholder, so these tests use a different invented zone.
ZONE = "lab-a.corp.invalid-zone.io"


def zoned(value: str) -> str:
    return value.replace("lab-a.example.internal", ZONE).replace("example.internal", ZONE)


FILES = {
    "infra_config_vars.yml": {
        "api_host": zoned(API),
        "host": zoned(API),
        "domain": ZONE,
        "apps_domain": zoned(APPS),
        "verify_ssl": False,
    },
    "vars_grafana.yml": {
        "hostname": zoned(GRAFANA),
        "components_env": {
            "grafana": {
                "hostname": zoned(GRAFANA),
                "email": {"smtp_host": zoned(SMTP), "port": 587},
                "install": True,
            }
        },
        "grafana_replicas": 2,
        "enable_grafana": True,
    },
    "vars_gitlab.yml": {"hostname": "gitlab.apps." + ZONE, "gitlab_edition": "ee"},
    "vars_satellite.yml": {
        "satellite_hostname": zoned(SAT),
        "capsule_ip": ADDRESS,
        "ds_suffix": "dc=lab-a,dc=corp,dc=invalid-zone,dc=io",
        "redirect_uris": ["https://grafana.apps." + ZONE + "/login/generic_oauth"],
    },
    "aap_config_vars.yml": {
        "bootstrap_controller_hub_hostname": zoned(HUB),
        "bootstrap_controller_organization": "DEV",
    },
    "vault_openshift.yml": {"token": "fake-test-token", "openshift_token": "fake-test-token"},
    "vault_satellite.yml": {"vault_satellite_admin_password": "fake-test-password"},
    "aap_vault.yml": {"vault_controller_hostname": zoned(HUB)},
}
REAL_TOPOLOGY = [
    zoned(API), zoned(APPS), zoned(GRAFANA), zoned(SMTP), zoned(SAT), zoned(HUB), ADDRESS, ZONE,
    "dc=lab-a,dc=corp",
]


def write_env(tmp_path: Path, files=None) -> Path:
    env = tmp_path / "group_vars" / "all" / "lab"
    env.mkdir(parents=True)
    for name, data in (files or FILES).items():
        (env / name).write_text(topo.dump_yaml(data))
    return env


def raw(env: Path, name: str) -> str:
    return (env / name).read_text()


def plaintext_text(env: Path) -> str:
    return "\n".join(
        raw(env, p.name) for p in sorted(env.iterdir())
        if not topo.is_encrypted(p.read_text()) and not topo.is_vault_name(p.name)
    )


# --------------------------------------------------------------------------- detection


@pytest.mark.parametrize(
    "value,hint,expected",
    [
        ("https://api.corp-lab.internal:6443", False, True),
        ("ldaps://idm.corp-lab.internal", False, True),
        ("10.20.30.40", False, True),
        ("10.128.0.0/14", False, True),
        ("dc=corp,dc=lab", False, True),
        ("grafana.apps.corp-lab.internal", True, True),
        ("smtp.corp-lab.internal:587", True, True),
        # Not topology
        ("grafana.apps.corp-lab.internal", False, False),  # bare name needs a host-like key
        ("ansible.builtin.copy", False, False),
        ("ansible.builtin.copy", True, False),
        ("release.yml", True, False),
        ("ca-bundle.crt", True, False),
        ("{{ vault_topology_vars_grafana__hostname }}", True, False),
        ("{{ apps_domain }}", True, False),
        ("", True, False),
        ("localhost", True, False),
        ("http://localhost:8080", False, False),
        ("127.0.0.1", False, False),
        ("0.0.0.0", False, False),
        ("api.example.com", True, False),
        ("api.lab.example.internal", True, False),
        ("grafana.svc.cluster.local", True, False),
        ("https://registry.redhat.io/ubi9", False, False),
        ("https://github.com/org/repo.git", False, False),
        ("4.14.2", False, False),
        ("999.1.1.1", False, False),
        (True, True, False),
        (443, True, False),
    ],
)
def test_detection(value, hint, expected):
    assert topo.is_topology_value(value, hint) is expected


def test_key_hints_cover_snake_and_camel_case():
    for key in ("api_host", "apps_domain", "smtpHost", "oidc_issuer", "hub_hostname", "redirect_uris", "standalone_ip"):
        assert topo.key_hints_topology(key), key
    for key in ("component", "enable_grafana", "replicas", "channel", "storage_class"):
        assert not topo.key_hints_topology(key), key


# --------------------------------------------------------------------------- freeze / thaw


def test_freeze_encrypts_topology_values_and_keeps_names(tmp_path):
    env = write_env(tmp_path)
    report = topo.freeze(env)
    assert report["routed"] > 8

    plain = plaintext_text(env)
    for secret in REAL_TOPOLOGY:
        assert secret not in plain, "topology value left in a plaintext file"

    grafana = yaml.safe_load(raw(env, "vars_grafana.yml"))
    assert list(grafana) == ["hostname", "components_env", "grafana_replicas", "enable_grafana"]
    assert grafana["grafana_replicas"] == 2 and grafana["enable_grafana"] is True
    assert grafana["components_env"]["grafana"]["install"] is True
    assert grafana["components_env"]["grafana"]["email"]["port"] == 587
    assert topo.REF_RE.match(grafana["hostname"])
    assert topo.REF_RE.match(grafana["components_env"]["grafana"]["email"]["smtp_host"])

    # Non-sensitive settings stay readable.
    infra = yaml.safe_load(raw(env, "infra_config_vars.yml"))
    assert infra["verify_ssl"] is False
    assert yaml.safe_load(raw(env, "vars_gitlab.yml"))["gitlab_edition"] == "ee"
    # Existing vault content is preserved.
    vault_openshift = yaml.safe_load(raw(env, "vault_openshift.yml"))
    assert vault_openshift["token"] == "fake-test-token"


def test_top_level_hostname_in_two_components_do_not_collide(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    grafana = yaml.safe_load(raw(env, "vars_grafana.yml"))["hostname"]
    gitlab = yaml.safe_load(raw(env, "vars_gitlab.yml"))["hostname"]
    assert grafana != gitlab
    home = yaml.safe_load(raw(env, "vault_openshift.yml"))
    name = topo.REF_RE.match(grafana).group(1)
    other = topo.REF_RE.match(gitlab).group(1)
    assert home[name] == zoned(GRAFANA)
    assert home[other] == "gitlab.apps." + ZONE


def test_topology_goes_to_the_vault_file_the_playbooks_load_with_it(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    sat_vault = yaml.safe_load(raw(env, "vault_satellite.yml"))
    assert any(k.startswith("vault_topology_vars_satellite__") for k in sat_vault)
    assert sat_vault["vault_satellite_admin_password"] == "fake-test-password"
    aap_vault = yaml.safe_load(raw(env, "aap_vault.yml"))
    assert any(k.startswith("vault_topology_aap_config_vars__") for k in aap_vault)
    openshift = yaml.safe_load(raw(env, "vault_openshift.yml"))
    assert any(k.startswith("vault_topology_infra_config_vars__") for k in openshift)
    assert not any(k.startswith("vault_topology_vars_satellite__") for k in openshift)


def test_component_without_its_own_vault_falls_back_to_vault_openshift():
    assert topo.home_for("vars_satellite", {"vault_satellite.yml"}) == "vault_satellite.yml"
    assert topo.home_for("vars_satellite", {"vault_openshift.yml"}) == "vault_openshift.yml"
    assert topo.home_for("vars_grafana", {"vault_grafana.yml"}) == "vault_openshift.yml"
    assert topo.home_for("aap_config_vars") == "aap_vault.yml"
    assert topo.home_for("infra_config_vars") == "vault_openshift.yml"


def test_thaw_restores_original_values_exactly(tmp_path):
    env = write_env(tmp_path)
    before = {n: yaml.safe_load(raw(env, n)) for n in FILES if not n.startswith("vault") and n != "aap_vault.yml"}
    topo.freeze(env)
    topo.thaw(env)
    after = {n: yaml.safe_load(raw(env, n)) for n in before}
    assert after == before


def test_freeze_is_idempotent_and_leaves_no_diff(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    snapshot = {p.name: p.read_bytes() for p in env.iterdir()}
    again = topo.freeze(env)
    assert again["written"] == [] or all(name in again["vault_files"] for name in again["written"])
    assert {p.name: p.read_bytes() for p in env.iterdir()} == snapshot


def test_generator_cycle_thaw_generate_freeze_converges(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    frozen = {p.name: p.read_bytes() for p in env.iterdir()}
    # Next run: thaw, the generator touches nothing, freeze again.
    topo.thaw(env)
    assert zoned(GRAFANA) in raw(env, "vars_grafana.yml")
    topo.freeze(env)
    assert {p.name: p.read_bytes() for p in env.iterdir()} == frozen


def test_changed_value_is_rerouted(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    topo.thaw(env)
    data = yaml.safe_load(raw(env, "vars_grafana.yml"))
    data["hostname"] = "grafana.apps.other-zone.invalid-zone.io"
    (env / "vars_grafana.yml").write_text(topo.dump_yaml(data))
    topo.freeze(env)
    assert "other-zone" not in plaintext_text(env)
    home = yaml.safe_load(raw(env, "vault_openshift.yml"))
    assert "grafana.apps.other-zone.invalid-zone.io" in home.values()
    assert zoned(GRAFANA) in home.values()  # the nested copy is unchanged


def test_removed_files_do_not_leave_stale_topology_in_plaintext_vault(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    (env / "vars_gitlab.yml").unlink()
    topo.freeze(env)
    home = yaml.safe_load(raw(env, "vault_openshift.yml"))
    assert not any("vars_gitlab__" in key for key in home)


def test_missing_reference_fails_closed_without_naming_values(tmp_path):
    env = write_env(tmp_path)
    topo.freeze(env)
    data = yaml.safe_load(raw(env, "vault_openshift.yml"))
    victim = next(k for k in data if k.startswith("vault_topology_vars_grafana__hostname"))
    del data[victim]
    (env / "vault_openshift.yml").write_text(topo.dump_yaml(data))
    with pytest.raises(topo.TopologyError) as excinfo:
        topo.thaw(env)
    assert zoned(GRAFANA) not in str(excinfo.value)


def test_non_dict_and_empty_files_are_left_alone(tmp_path):
    env = write_env(tmp_path, {"vars_empty.yml": {}, "vars_list.yml": ["a", "b"], **FILES})
    topo.freeze(env)
    assert yaml.safe_load(raw(env, "vars_list.yml")) == ["a", "b"]


def test_templated_values_are_never_routed(tmp_path):
    env = write_env(tmp_path, {"vars_x.yml": {"hostname": "{{ app }}.{{ apps_domain }}", "url": "https://{{ host }}/x"}})
    report = topo.freeze(env)
    assert report["routed"] == 0
    assert not (env / "vault_openshift.yml").exists()


def test_cli_never_prints_topology_values(tmp_path):
    env = write_env(tmp_path)
    for command in ("audit", "freeze", "status", "thaw"):
        result = subprocess.run(
            [sys.executable, str(TOPOLOGY), command, "--env-dir", str(env)],
            capture_output=True, text=True, check=False,
        )
        out = result.stdout + result.stderr
        for secret in REAL_TOPOLOGY:
            assert secret not in out, (command, "printed a topology value")


def test_audit_reports_plaintext_topology_by_key_path(tmp_path):
    env = write_env(tmp_path)
    result = subprocess.run(
        [sys.executable, str(TOPOLOGY), "audit", "--env-dir", str(env)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 3
    assert "vars_grafana.yml: components_env.grafana.email.smtp_host" in result.stdout
    topo.freeze(env)
    after = subprocess.run(
        [sys.executable, str(TOPOLOGY), "audit", "--env-dir", str(env)], capture_output=True, text=True, check=False
    )
    assert after.returncode == 0


# --------------------------------------------------------------------------- Ansible Vault


@pytest.fixture
def vault_pass(tmp_path):
    path = tmp_path / "vault-pass"
    path.write_text("fake-vault-password-for-tests\n")
    path.chmod(0o600)
    return str(path)


def encrypt_all(env: Path, vault_pass: str):
    for path in sorted(env.iterdir()):
        if path.name.startswith("vault") or path.name == "aap_vault.yml":
            if not topo.is_encrypted(path.read_text()):
                subprocess.run(
                    ["ansible-vault", "encrypt", str(path), "--vault-password-file", vault_pass],
                    check=True, capture_output=True,
                )


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_encrypted_vault_files_are_untouched_when_nothing_changed(tmp_path, vault_pass):
    env = write_env(tmp_path)
    topo.freeze(env, vault_pass)
    encrypt_all(env, vault_pass)
    snapshot = {p.name: p.read_bytes() for p in env.iterdir()}
    for name in ("vault_openshift.yml", "vault_satellite.yml", "aap_vault.yml"):
        assert topo.is_encrypted(raw(env, name))
    topo.thaw(env, vault_pass)
    assert zoned(GRAFANA) in raw(env, "vars_grafana.yml")
    report = topo.freeze(env, vault_pass)
    assert report["written"] == []
    assert {p.name: p.read_bytes() for p in env.iterdir()} == snapshot


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_encrypted_topology_needs_the_vault_password_and_reports_clearly(tmp_path, vault_pass):
    env = write_env(tmp_path)
    topo.freeze(env, vault_pass)
    encrypt_all(env, vault_pass)
    with pytest.raises(topo.TopologyError, match="ciphertext"):
        topo.thaw(env, None)
    wrong = tmp_path / "wrong"
    wrong.write_text("not-the-password\n")
    with pytest.raises(topo.TopologyError, match="could not decrypt"):
        topo.thaw(env, str(wrong))


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_encrypted_topology_changes_are_merged_into_ciphertext(tmp_path, vault_pass):
    env = write_env(tmp_path)
    topo.freeze(env, vault_pass)
    encrypt_all(env, vault_pass)
    topo.thaw(env, vault_pass)
    data = yaml.safe_load(raw(env, "vars_grafana.yml"))
    data["hostname"] = "grafana.apps.new-zone.invalid-zone.io"
    (env / "vars_grafana.yml").write_text(topo.dump_yaml(data))
    report = topo.freeze(env, vault_pass)
    assert "vault_openshift.yml" in report["written"]
    assert "vault_satellite.yml" not in report["written"]
    assert "new-zone" not in plaintext_text(env)
    topo.encrypt_files(env, report["written"], vault_pass)
    assert topo.is_encrypted(raw(env, "vault_openshift.yml"))
    view = topo.read_vault_mapping(env / "vault_openshift.yml", vault_pass)
    assert "grafana.apps.new-zone.invalid-zone.io" in view.values()
    assert view["token"] == "fake-test-token"


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_ansible_resolves_frozen_names_so_roles_need_no_change(tmp_path, vault_pass):
    """The same variable names resolve to the same values after freezing, in a real play."""
    env = write_env(tmp_path)
    expected = {
        "api_host": FILES["infra_config_vars.yml"]["api_host"],
        "domain": ZONE,
        "grafana_smtp": FILES["vars_grafana.yml"]["components_env"]["grafana"]["email"]["smtp_host"],
        "hub": FILES["aap_config_vars.yml"]["bootstrap_controller_hub_hostname"],
    }
    topo.freeze(env, vault_pass)
    encrypt_all(env, vault_pass)
    for secret in REAL_TOPOLOGY:
        assert secret not in "\n".join(p.read_text() for p in env.iterdir()), "plaintext topology in a committed file"

    play = tmp_path / "check.yml"
    play.write_text(
        """---
- hosts: localhost
  gather_facts: false
  vars_files:
    - "{{ lookup('env', 'ENVDIR') }}/infra_config_vars.yml"
    - "{{ lookup('env', 'ENVDIR') }}/vault_openshift.yml"
    - "{{ lookup('env', 'ENVDIR') }}/aap_config_vars.yml"
    - "{{ lookup('env', 'ENVDIR') }}/aap_vault.yml"
    - "{{ lookup('env', 'ENVDIR') }}/vars_grafana.yml"
  tasks:
    - ansible.builtin.copy:
        dest: "{{ lookup('env', 'OUTFILE') }}"
        mode: "0600"
        content: >-
          {{ {'api_host': api_host, 'domain': domain,
              'grafana_smtp': components_env.grafana.email.smtp_host,
              'hub': bootstrap_controller_hub_hostname,
              'host_fallback': (host | default(api_host)),
              'verify_ssl': verify_ssl} | to_json }}
      no_log: true
"""
    )
    out = tmp_path / "resolved.json"
    env_vars = dict(os.environ, ENVDIR=str(env), OUTFILE=str(out), ANSIBLE_CONFIG=str(tmp_path / "none.cfg"),
                    ANSIBLE_LOCALHOST_WARNING="false", ANSIBLE_INVENTORY_UNPARSED_WARNING="false")
    env_vars.pop("ANSIBLE_VAULT_PASSWORD_FILE", None)
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play), "--vault-password-file", vault_pass],
        capture_output=True, text=True, env=env_vars, check=False, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    import json
    resolved = json.loads(out.read_text())
    assert resolved["api_host"] == expected["api_host"]
    assert resolved["domain"] == expected["domain"]
    assert resolved["grafana_smtp"] == expected["grafana_smtp"]
    assert resolved["hub"] == expected["hub"]
    assert resolved["host_fallback"] == expected["api_host"]
    assert resolved["verify_ssl"] is False
    # Normal task output never shows a topology value.
    assert zoned(GRAFANA) not in result.stdout


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_two_environments_stay_isolated(tmp_path, vault_pass):
    a = write_env(tmp_path / "a")
    other = copy.deepcopy(FILES)
    other["infra_config_vars.yml"]["api_host"] = "https://api.lab-b.invalid-zone.io:6443"
    b = write_env(tmp_path / "b", other)
    topo.freeze(a, vault_pass)
    topo.freeze(b, vault_pass)
    encrypt_all(a, vault_pass)
    encrypt_all(b, vault_pass)
    a_values = topo.read_vault_mapping(a / "vault_openshift.yml", vault_pass)
    b_values = topo.read_vault_mapping(b / "vault_openshift.yml", vault_pass)
    assert "https://api.lab-b.invalid-zone.io:6443" in b_values.values()
    assert "https://api.lab-b.invalid-zone.io:6443" not in a_values.values()
    assert zoned(API) in a_values.values()


# --------------------------------------------------------------------------- generator wiring


def test_generator_thaws_before_generation_and_freezes_before_encryption():
    main = (TASKS / "main.yml").read_text()
    thaw_at = main.index("topology_thaw.yml")
    first_write = main.index("Write shared OpenShift infra_config_vars.yml")
    freeze_at = main.index("topology_freeze.yml")
    encrypt_at = main.index("- name: Find generated vault files")
    assert thaw_at < first_write < freeze_at < encrypt_at


def test_generator_keeps_vault_files_that_hold_topology():
    main = (TASKS / "main.yml").read_text()
    # Topology lives inside the ordinary vault_*.yml files, so the stale-file cleanup needs no exception,
    # and no separate unencrypted file is written.
    assert "vault_topology.yml" not in main
    freeze = (TASKS / "topology_freeze.yml").read_text()
    assert "ado_topology.py" in freeze and "freeze" in freeze
    assert "encrypt_vault_files" in freeze


def test_generator_passes_a_password_file_path_never_the_password():
    for name in ("topology_thaw.yml", "topology_freeze.yml"):
        text = (TASKS / name).read_text()
        for match in re.finditer(r"- --vault-password-file\n\s+- \"([^\"]+)\"", text):
            assert "password_file" in match.group(1), match.group(1)
        # The only debug output is a count; stdout of the script is never echoed.
        assert "var: bootstrap_generate_env_vars_topology_thawed" not in text
        assert "stdout_lines" not in text


# --------------------------------------------------------------------------- generated playbooks


PLAYBOOK_PATTERN = re.compile(r"group_vars/all/\{\{[^}]*\}\}/([A-Za-z0-9_{}' .|-]+?\.yml)")


def _plays():
    for path in sorted(list(PLAYBOOKS.glob("playbooks/**/*.yml")) + list(PLAYBOOKS.glob("playbook_repo_seed/**/*.yml"))):
        try:
            docs = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(docs, list):
            continue
        for index, play in enumerate(docs):
            if isinstance(play, dict):
                yield path, index, play


def _loaded_files(play) -> set[str]:
    text = yaml.dump(play, width=100000)
    component = (play.get("vars") or {}).get("component", "")
    names = set()
    for match in PLAYBOOK_PATTERN.finditer(text):
        names.add(re.sub(r"\{\{\s*component\s*\}\}", component, match.group(1).replace(" ", "")))
    return names


# Plays that load infra_config_vars.yml with only the AWS vault. They never read the OpenShift
# endpoints in it, so the references stay unresolved and unused.
AWS_ONLY = re.compile(r"/aws/")


def test_every_play_loads_the_vault_file_that_holds_its_plaintext_files_topology():
    checked = 0
    problems = []
    for path, index, play in _plays():
        loaded = _loaded_files(play)
        vaults = {n for n in loaded if topo.is_vault_name(n)}
        for name in sorted(loaded):
            if topo.is_vault_name(name) or "{" in name:
                continue
            stem = Path(name).stem
            home = topo.home_for(stem, vaults)
            if home not in loaded:
                if AWS_ONLY.search(str(path)) and stem == "infra_config_vars":
                    continue
                problems.append(f"{path.relative_to(PLAYBOOKS)}#{index}: loads {name} but not {home}")
            checked += 1
    assert checked > 100
    assert not problems, "\n".join(problems)


def test_bootstrap_controller_reads_virt_vars_through_ansible_so_references_resolve():
    text = (ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml").read_text()
    assert "name: bootstrap_controller_virt_vars" in text
    assert 'safe_load(virt_vars_path' not in text


def test_aap_config_topology_is_stored_where_the_controller_loads_it():
    # aap_config_vars.yml is always loaded next to aap_vault.yml (scaffolding pre_tasks and
    # generate_aap_configs.yml), so the references resolve whenever the file is used.
    controller = (ROOT / "roles/bootstrap_controller/tasks/generate_aap_configs.yml").read_text()
    assert "aap_config_vars.yml" in controller and "aap_vault.yml" in controller
    assert topo.home_for("aap_config_vars") == "aap_vault.yml"


# --------------------------------------------------------------------------- Git publication gate

GATE_PATH = PLAYBOOKS / "ado_credential_gate.py"
_GATE_SPEC = importlib.util.spec_from_file_location("ado_credential_gate_topology", GATE_PATH)
assert _GATE_SPEC is not None and _GATE_SPEC.loader is not None
gate = importlib.util.module_from_spec(_GATE_SPEC)
sys.modules["ado_credential_gate_topology"] = gate
_GATE_SPEC.loader.exec_module(gate)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def stage_repo(tmp_path: Path, env: Path) -> Path:
    """A git repo whose group_vars/ is a copy of ``env``, staged the way the Bootstrap push stages it."""
    repo = tmp_path / "published"
    target = repo / "group_vars" / "all" / env.name
    shutil.copytree(env, target)
    git(tmp_path, "init", "-q", str(repo))
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "Test")
    git(repo, "add", "-A", "-f")
    return repo


def topology_findings(repo: Path):
    return [f for f in gate.scan_repo(str(repo), "repo") if f[1] == "plaintext-topology"]


def test_gate_rejects_plaintext_topology_in_generated_group_vars(tmp_path):
    repo = stage_repo(tmp_path, write_env(tmp_path))
    findings = topology_findings(repo)
    assert findings
    keys = {detail.split(" line ")[0] for _p, _r, detail in findings}
    assert {"hostname", "api_host", "apps_domain", "bootstrap_controller_hub_hostname"} <= keys


def test_gate_findings_never_contain_a_topology_value(tmp_path):
    repo = stage_repo(tmp_path, write_env(tmp_path))
    rendered = repr(gate.scan_repo(str(repo), "repo"))
    for value in REAL_TOPOLOGY:
        assert value not in rendered


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_gate_accepts_the_frozen_and_encrypted_output(tmp_path, vault_pass):
    env = write_env(tmp_path)
    topo.freeze(env, vault_pass)
    encrypt_all(env, vault_pass)
    repo = stage_repo(tmp_path, env)
    assert topology_findings(repo) == []
    assert gate.scan_repo(str(repo), "repo") == []
    for name in ("vault_openshift.yml", "vault_satellite.yml", "aap_vault.yml"):
        assert "$ANSIBLE_VAULT" in raw(repo / "group_vars" / "all" / "lab", name)


def test_gate_flags_a_plaintext_copy_left_in_a_vault_file(tmp_path):
    # Frozen but not encrypted: the vault file holds the real values in plaintext.
    env = write_env(tmp_path)
    topo.freeze(env, None)
    repo = stage_repo(tmp_path, env)
    paths = {path for path, _r, _d in topology_findings(repo)}
    assert any(path.endswith("vault_openshift.yml") for path in paths)
    assert not any(path.endswith("vars_grafana.yml") for path in paths)


def test_gate_ignores_the_source_profile_and_example_values(tmp_path):
    env = write_env(tmp_path, {"vars_x.yml": {"hostname": "app.example.com", "api": "https://api.example.org:6443"}})
    repo = stage_repo(tmp_path, env)
    assert topology_findings(repo) == []
    repo2 = stage_repo(tmp_path / "other", write_env(tmp_path / "other"))
    assert [f for f in gate.scan_repo(str(repo2), "source") if f[1] == "plaintext-topology"] == []


def test_gate_keeps_ordinary_options_and_sizing_in_plaintext(tmp_path):
    data = {"vars_x.yml": {"replicas": 3, "storage": "10Gi", "enable_sso": True, "channel": "stable", "name": "Grafana"}}
    repo = stage_repo(tmp_path, write_env(tmp_path, data))
    assert gate.scan_repo(str(repo), "repo") == []


def test_generated_hook_refuses_a_push_with_plaintext_topology(tmp_path):
    repo = stage_repo(tmp_path, write_env(tmp_path))
    hooks = repo / ".githooks"
    hooks.mkdir()
    shutil.copy(PLAYBOOKS / "ado_credential_gate.py", hooks)
    shutil.copy(PLAYBOOKS / "ado_topology_rules.py", hooks)
    shutil.copy(PLAYBOOKS / "generated_pre_push_hook.sh", hooks / "pre-push")
    (hooks / "pre-push").chmod(0o755)
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-q", "-m", "x")
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    done = subprocess.run(
        [str(hooks / "pre-push")], input=f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n",
        cwd=repo, capture_output=True, text=True, check=False,
    )
    assert done.returncode == 3
    assert "plaintext-topology" in done.stderr
    for value in REAL_TOPOLOGY:
        assert value not in done.stderr + done.stdout


def test_generated_repo_receives_the_topology_rules_next_to_the_gate():
    tasks = (ROOT / "roles/bootstrap_generate_playbook_repo/tasks/main.yml").read_text()
    assert "src: ado_topology_rules.py" in tasks
    assert (PLAYBOOKS / "ado_topology_rules.py").exists()


def test_rules_module_has_no_third_party_imports():
    # The gate runs in generated repos and on workstations where PyYAML may be absent.
    text = (PLAYBOOKS / "ado_topology_rules.py").read_text()
    imports = set(re.findall(r"^(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M))
    assert imports <= {"__future__", "ipaddress", "re"}


@pytest.mark.skipif(not HAVE_ANSIBLE, reason="ansible is not installed")
def test_existing_credential_encryption_still_works_alongside_topology(tmp_path, vault_pass):
    env = write_env(tmp_path)
    topo.freeze(env, vault_pass)
    encrypt_all(env, vault_pass)
    # Credentials in the vault files are ciphertext, and the gate's credential rules still fire on a plaintext one.
    assert "fake-test-token" not in raw(env, "vault_openshift.yml")
    leaked = write_env(tmp_path / "leak", {"vault_x.yml": {"admin_password": "Zq8Lm4Xv2Rt9Kd5Wn7Bc3Hy6"}})
    repo = stage_repo(tmp_path / "leak", leaked)
    assert any(rule == "literal-secret" for _p, rule, _d in gate.scan_repo(str(repo), "repo"))
