"""Generated Controller configs: topology goes to Vault, raw-read files must hold none.

``configs/controller/*.yml`` are loaded with ``include_vars`` and can hold references.
``configs/job_templates`` and ``configs/workflows`` are read as raw YAML and cannot, so
topology there is an error. Every value here is invented.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TOPOLOGY = ROOT / "roles/bootstrap_generate_env_vars/files/ado_topology.py"
GATE = ROOT / "roles/bootstrap_generate_playbook_repo/files/ado_credential_gate.py"

_SPEC = importlib.util.spec_from_file_location("ado_topology_configs", TOPOLOGY)
assert _SPEC is not None and _SPEC.loader is not None
topo = importlib.util.module_from_spec(_SPEC)
sys.modules["ado_topology_configs"] = topo
_SPEC.loader.exec_module(topo)

_GATE_SPEC = importlib.util.spec_from_file_location("ado_credential_gate_configs", GATE)
assert _GATE_SPEC is not None and _GATE_SPEC.loader is not None
gate = importlib.util.module_from_spec(_GATE_SPEC)
sys.modules["ado_credential_gate_configs"] = gate
_GATE_SPEC.loader.exec_module(gate)

HAVE_VAULT = shutil.which("ansible-vault") is not None
ZONE = "lab-a.corp.invalid-zone.io"
HOST = f"satellite.{ZONE}"
HOST_B = f"hub.{ZONE}"
GIT = f"https://git.apps.{ZONE}/org/repo.git"


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


@pytest.fixture
def tree(tmp_path):
    configs, env = tmp_path / "configs", tmp_path / "group_vars" / "all" / "dev"
    env.mkdir(parents=True)
    write(configs / "controller" / "hosts.yml", {"controller_hosts": [{"name": HOST, "enabled": True}, {"name": HOST_B}]})
    write(configs / "controller" / "projects.yml", {"controller_projects": [{"name": "p", "scm_url": GIT, "scm_branch": "main"}]})
    return configs, env


@pytest.fixture
def vault_pass(tmp_path):
    path = tmp_path / "vault-pass"
    path.write_text("fake-vault-password-for-tests\n")
    path.chmod(0o600)
    return str(path)


def test_controller_configs_keep_their_keys_and_gain_references(tree):
    configs, env = tree
    report = topo.freeze_configs(configs, env)
    assert report["routed"] == 3
    hosts = yaml.safe_load((configs / "controller" / "hosts.yml").read_text())["controller_hosts"]
    assert hosts[0]["enabled"] is True
    assert all(str(host["name"]).startswith("{{ vault_topology_cfg_controller_hosts__") for host in hosts)
    vault = yaml.safe_load((env / "aap_vault.yml").read_text())
    assert set(vault.values()) == {HOST, HOST_B, GIT}
    assert all(name.startswith("vault_topology_cfg_") for name in vault)
    for text in ((configs / "controller" / "hosts.yml").read_text(), (configs / "controller" / "projects.yml").read_text()):
        assert ZONE not in text


def test_audit_reports_leaves_without_values_and_passes_after_freeze(tree, capsys):
    configs, env = tree
    assert topo.main(["audit-configs", "--configs-dir", str(configs)]) == 3
    assert ZONE not in capsys.readouterr().out
    topo.freeze_configs(configs, env)
    assert topo.main(["audit-configs", "--configs-dir", str(configs)]) == 0


def test_topology_in_raw_read_job_templates_is_an_error_naming_file_and_key_only(tree):
    configs, env = tree
    write(configs / "job_templates" / "x.jt.yml", {"controller_templates": [{"name": "x", "extra_vars": {"gateway_host": HOST}}]})
    with pytest.raises(topo.TopologyError) as error:
        topo.freeze_configs(configs, env)
    message = str(error.value)
    assert "job_templates/x.jt.yml" in message and "gateway_host" in message
    assert ZONE not in message
    assert not (env / "aap_vault.yml").exists()
    assert topo.main(["audit-configs", "--configs-dir", str(configs)]) == 3


def test_workflows_are_raw_read_too(tree):
    configs, env = tree
    write(configs / "workflows" / "w.wf.yml", {"controller_workflows": [{"name": "w", "extra_vars": {"portal_url": f"https://{HOST}/"}}]})
    with pytest.raises(topo.TopologyError):
        topo.freeze_configs(configs, env)


def test_stale_entries_are_removed_and_other_vault_content_is_kept(tree):
    configs, env = tree
    write(env / "aap_vault.yml", {"vault_aap_admin_password": "fake-pw", "vault_topology_cfg_old__thing": "gone.example.invalid"})
    topo.freeze_configs(configs, env)
    vault = yaml.safe_load((env / "aap_vault.yml").read_text())
    assert vault["vault_aap_admin_password"] == "fake-pw"
    assert "vault_topology_cfg_old__thing" not in vault
    # A fresh generation with one host fewer drops that host's entry.
    write(configs / "controller" / "hosts.yml", {"controller_hosts": [{"name": HOST}]})
    topo.freeze_configs(configs, env)
    vault = yaml.safe_load((env / "aap_vault.yml").read_text())
    assert HOST_B not in vault.values() and HOST in vault.values()


def test_group_vars_freeze_does_not_remove_config_entries(tree):
    configs, env = tree
    topo.freeze_configs(configs, env)
    before = yaml.safe_load((env / "aap_vault.yml").read_text())
    write(env / "infra_config_vars.yml", {"api_host": f"https://api.{ZONE}:6443"})
    topo.freeze(env)
    after = yaml.safe_load((env / "aap_vault.yml").read_text()) if (env / "aap_vault.yml").exists() else {}
    merged = {**after}
    for name, value in before.items():
        assert merged.get(name) == value, name


@pytest.mark.skipif(not HAVE_VAULT, reason="needs ansible-vault")
def test_an_encrypted_vault_whose_entries_are_current_is_left_untouched(tree, vault_pass):
    configs, env = tree
    topo.freeze_configs(configs, env, vault_pass)
    assert topo.encrypt_files(env, ["aap_vault.yml"], vault_pass) == ["aap_vault.yml"]
    ciphertext = (env / "aap_vault.yml").read_bytes()
    # The generator writes the configs again with plaintext values on the next run.
    write(configs / "controller" / "hosts.yml", {"controller_hosts": [{"name": HOST, "enabled": True}, {"name": HOST_B}]})
    write(configs / "controller" / "projects.yml", {"controller_projects": [{"name": "p", "scm_url": GIT, "scm_branch": "main"}]})
    report = topo.freeze_configs(configs, env, vault_pass)
    assert report["written"] == []
    assert (env / "aap_vault.yml").read_bytes() == ciphertext
    assert ZONE not in (configs / "controller" / "hosts.yml").read_text()


@pytest.mark.skipif(not HAVE_VAULT, reason="needs ansible-vault")
def test_a_changed_value_is_merged_into_the_encrypted_vault(tree, vault_pass):
    configs, env = tree
    topo.freeze_configs(configs, env, vault_pass)
    topo.encrypt_files(env, ["aap_vault.yml"], vault_pass)
    write(configs / "controller" / "hosts.yml", {"controller_hosts": [{"name": f"other.{ZONE}"}, {"name": HOST_B}]})
    write(configs / "controller" / "projects.yml", {"controller_projects": [{"name": "p", "scm_url": GIT, "scm_branch": "main"}]})
    report = topo.freeze_configs(configs, env, vault_pass)
    assert report["written"] == ["aap_vault.yml"]
    values = topo.read_vault_mapping(env / "aap_vault.yml", vault_pass).values()
    assert f"other.{ZONE}" in values and HOST not in values


@pytest.mark.skipif(not HAVE_VAULT, reason="needs ansible-vault")
def test_the_top_level_project_config_the_playbook_repo_renders_is_routed_too(tmp_path, vault_pass):
    """``configs/controller_projects.yml`` sits beside, not inside, ``configs/controller/``.

    bootstrap_generate_playbook_repo renders it with the real Git URL and commits it. A
    No-AAP run never reaches the Controller pass, so the playbook repo role runs the same
    freeze pass right after rendering. The credential gate must then find nothing.
    """
    repo = tmp_path / "repo"
    env = repo / "group_vars" / "all" / "dev"
    env.mkdir(parents=True)
    rendered = write(
        repo / "configs" / "controller_projects.yml",
        {"controller_projects": [{"name": "p", "scm_type": "git", "scm_url": GIT, "scm_branch": "main"}]},
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A", "-f"], check=True)
    assert [f[2] for f in topology_findings(repo)] == ["scm_url line 4"], "precondition: the gate refuses the plaintext file"

    report = topo.freeze_configs(repo / "configs", env, vault_pass)
    assert report["routed"] == 1
    topo.encrypt_files(env, ["aap_vault.yml"], vault_pass)
    assert ZONE not in rendered.read_text()
    assert "{{ vault_topology_cfg_" in rendered.read_text()
    assert ZONE not in (env / "aap_vault.yml").read_text(), "the vault file is ciphertext"
    subprocess.run(["git", "-C", str(repo), "add", "-A", "-f"], check=True)
    assert topology_findings(repo) == []


# --------------------------------------------------------------------------- gate scope


def stage(tmp_path: Path, relative: str, data) -> Path:
    repo = tmp_path / "repo"
    write(repo / relative, data)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A", "-f"], check=True)
    return repo


def topology_findings(repo: Path):
    return [f for f in gate.scan_repo(str(repo), "repo") if f[1] == "plaintext-topology"]


@pytest.mark.parametrize("relative", [
    "configs/controller/hosts.yml",
    "group_vars/all/prod/vars_x.yml",
    "group_vars/all/test/vars_x.yml",       # an environment named "test" is a real environment
    "group_vars/all/molecule/vars_x.yml",   # so is one named "molecule"
    "group_vars/all/examples/vars_x.yml",
])
def test_gate_checks_every_environment_name(tmp_path, relative):
    repo = stage(tmp_path, relative, {"gateway_host": HOST})
    assert topology_findings(repo)


@pytest.mark.parametrize("relative", [
    "tests/fixtures/group_vars/all/dev/vars_x.yml",
    "molecule/default/group_vars/all/vars_x.yml",
])
def test_gate_exempts_a_test_directory_above_group_vars(tmp_path, relative):
    repo = stage(tmp_path, relative, {"gateway_host": HOST})
    assert not topology_findings(repo)


def test_gate_flags_ip_ranges_and_host_lists_under_host_like_keys(tmp_path):
    repo = stage(tmp_path, "group_vars/all/dev/vars_x.yml", {
        "pool_range": "10.77.0.100-10.77.0.200",
        "dns_servers": f"ns1.{ZONE}, ns2.{ZONE}",
        "description": "plain words, not hosts",
    })
    keys = {detail.split(" line ")[0] for _p, _r, detail in topology_findings(repo)}
    assert keys == {"pool_range", "dns_servers"}


@pytest.mark.parametrize("task", ["generate_gateway_auth.yml", "generate_onboard_keycloak.yml"])
def test_tasks_that_merge_into_aap_vault_never_overwrite_ciphertext(task):
    text = (ROOT / "roles/bootstrap_generate_env_vars/tasks" / task).read_text()
    guard = text.index('startswith("$ANSIBLE_VAULT")')
    assert guard < text.index("yaml.safe_load(vault_path.read_text())")


def _rules():
    spec = importlib.util.spec_from_file_location("ado_topology_rules_seed", ROOT / "roles/bootstrap_generate_playbook_repo/files/ado_topology_rules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("folder", ["job_templates", "workflows"])
def test_job_template_and_workflow_seeds_carry_no_topology(folder):
    """The seeds are copied into configs/ and read as raw YAML, so they can never hold topology."""
    rules = _rules()
    seeds = sorted((ROOT / "roles/bootstrap_controller/files" / folder).glob("*.yml"))
    assert len(seeds) > 10
    offenders = []
    for seed in seeds:
        text = seed.read_text()
        if "{{" in text:  # Jinja seeds are rendered by the generator and checked by the lifecycle test
            continue
        offenders += [f"{seed.name}:{key}" for _line, key in rules.scan_yaml_topology(text)]
    assert offenders == []
