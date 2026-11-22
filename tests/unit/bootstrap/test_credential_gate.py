"""Credential gate: no real credentials or Vault password files in Git.

Covers the gate itself (index and commit scans), the generated pre-push hook,
the way ``bootstrap_generate_playbook_repo`` wires the gate before commit and
push, and ``local_components`` taking the Vault password file from the
environment instead of a ``.vault_pass`` inside the checkout.

Every credential here is invented. The gate never prints a value, which the
tests assert.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FILES = ROOT / "roles/bootstrap_generate_playbook_repo/files"
GATE = FILES / "ado_credential_gate.py"
HOOK = FILES / "generated_pre_push_hook.sh"
TASKS = ROOT / "roles/bootstrap_generate_playbook_repo/tasks/main.yml"

_SPEC = importlib.util.spec_from_file_location("ado_credential_gate", GATE)
assert _SPEC is not None and _SPEC.loader is not None
gate = importlib.util.module_from_spec(_SPEC)
sys.modules["ado_credential_gate"] = gate
_SPEC.loader.exec_module(gate)

# Looks like a real value to the gate: long, mixed case, digits, no "fake" words.
REAL_LOOKING = "Zq8Lm4Xv2Rt9Kd5Wn7Bc3Hy6"
REAL_PAT = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout


def _repo(
    tmp_path: Path, files: dict[str, str], stage: bool = True, name: str = "repo"
) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    for name, content in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if stage:
        _git(repo, "add", "-A", "-f")
    return repo


def _scan(repo: Path, profile: str = "repo"):
    return gate.scan_repo(str(repo), profile)


def _rules(findings) -> set[tuple[str, str]]:
    return {(path, rule) for path, rule, _detail in findings}


def test_vault_password_files_are_always_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {
        ".vault_pass": "anything\n",
        "sub/.vault-pass": "anything\n",
        "ado-preflight-dev.json": "{}\n",
        "tmp-ado-preflight-dev-filled.json": "{}\n",
        "ado-extra-vars.json": "{}\n",
    })
    refused = {path for path, rule in _rules(_scan(repo)) if rule == "forbidden-file"}
    assert refused == {
        ".vault_pass", "sub/.vault-pass", "ado-preflight-dev.json",
        "tmp-ado-preflight-dev-filled.json", "ado-extra-vars.json",
    }


def test_ansible_vault_encrypted_files_are_allowed(tmp_path: Path) -> None:
    cipher = "$ANSIBLE_VAULT;1.1;AES256\n6162636465666768696a6b6c6d6e6f70\n"
    repo = _repo(tmp_path, {
        "group_vars/all/dev/vault_grafana.yml": cipher,
        "ado-preflight-dev.json.vault.yml": cipher,
    })
    assert _scan(repo) == []


def test_literal_secret_in_group_vars_is_refused_without_printing_it(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {
        "group_vars/all/dev/vault_app.yml": f"app_admin_password: {REAL_LOOKING}\n",
    })
    code = gate.main(["--repo", str(repo)])
    out = capfd.readouterr()
    assert code == gate.EXIT_FINDINGS
    assert "group_vars/all/dev/vault_app.yml" in out.err
    assert REAL_LOOKING not in out.out + out.err


def test_references_and_vault_tags_pass(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {
        "group_vars/all/dev/vars_app.yml": (
            "app_admin_password: \"{{ vault_app_admin_password }}\"\n"
            "app_token: !vault |\n"
            "  $ANSIBLE_VAULT;1.1;AES256\n"
            "  6162\n"
            "update_password: always\n"
            "bind_password: \"{{ lookup('env', 'BIND_PW') }}\"\n"
        ),
    })
    assert _scan(repo) == []


def test_real_looking_token_is_refused_and_synthetic_token_passes(tmp_path: Path) -> None:
    refused = _repo(tmp_path, {"notes.txt": f"token {REAL_PAT}\n"})
    assert ("notes.txt", "github-token") in _rules(_scan(refused))

    ok = _repo(
        tmp_path,
        {"notes.txt": "token ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE0\n"},
        name="ok",
    )
    assert _scan(ok) == []


def test_private_key_blocks(tmp_path: Path) -> None:
    body = "A" * 70
    real = f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----\n"
    tiny = "-----BEGIN PRIVATE KEY-----\nDEF\n-----END PRIVATE KEY-----\n"
    repo = _repo(tmp_path, {"id.pem": real, "tests/sample.txt": tiny})
    assert _rules(_scan(repo)) == {("id.pem", "private-key")}


def test_synthetic_fixtures_remain_usable(tmp_path: Path) -> None:
    fixture = (
        '{"aap": {"vault_password": "' + REAL_LOOKING + '", '
        '"oauth_token": "' + REAL_LOOKING + '"}}\n'
    )
    repo = _repo(tmp_path, {
        "extensions/molecule/s/ado-preflight-all.fixture.json": fixture,
        "docs/example.md": "vault_password: hunter2hunter2\n",
        "tests/data/creds.yml": "admin_password: example-password\n",
    })
    assert _scan(repo) == []


def test_plain_json_with_same_values_is_not_a_fixture(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {
        "data/export.json": '{"aap": {"vault_password": "' + REAL_LOOKING + '"}}\n',
    })
    assert ("data/export.json", "literal-secret") in _rules(_scan(repo))


def test_allow_list_exempts_content_but_never_credential_file_names(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {
        ".credential-gate-allow": "# reviewed\ndata/export.json\n.vault_pass\n",
        "data/export.json": '{"aap": {"vault_password": "' + REAL_LOOKING + '"}}\n',
        ".vault_pass": "x\n",
    })
    assert _rules(_scan(repo)) == {(".vault_pass", "forbidden-file")}


def test_already_tracked_files_are_refused_not_only_staged_ones(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {".vault-pass": "x\n", "README.md": "hi\n"})
    _git(repo, "commit", "-q", "-m", "history")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    assert (".vault-pass", "forbidden-file") in _rules(_scan(repo))


def test_commit_tree_scan_is_what_pre_push_uses(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {".vault_pass": "x\n"})
    _git(repo, "commit", "-q", "-m", "oops")
    _git(repo, "rm", "-q", "--cached", ".vault_pass")  # index is clean now
    assert _scan(repo) == []
    assert (".vault_pass", "forbidden-file") in _rules(gate.scan_repo(str(repo), "repo", rev="HEAD"))


def test_source_profile_ignores_task_code_but_checks_json(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {
        "roles/x/tasks/main.yml": f"    bind_password: {REAL_LOOKING}\n",
        "roles/x/files/data.json": '{"api_token": "' + REAL_LOOKING + '"}\n',
    })
    assert _rules(_scan(repo, "source")) == {("roles/x/files/data.json", "literal-secret")}
    assert ("roles/x/tasks/main.yml", "literal-secret") in _rules(_scan(repo, "repo"))


def _hooked_clone(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = _repo(tmp_path, files, stage=False)
    hooks = repo / ".githooks"
    hooks.mkdir()
    (hooks / "ado_credential_gate.py").write_bytes(GATE.read_bytes())
    (hooks / "pre-push").write_bytes(HOOK.read_bytes())
    for hook in hooks.iterdir():
        hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", ".githooks")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "checkout", "-q", "-b", "main")
    return repo, remote


def _push(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), "push", "origin", "main"],
        capture_output=True, text=True, check=False,
    )


def test_pre_push_hook_rejects_vault_pass_and_accepts_clean_push(tmp_path: Path) -> None:
    repo, remote = _hooked_clone(tmp_path, {"README.md": "hello\n", ".vault_pass": "x\n"})
    _git(repo, "add", "-A", "-f")
    _git(repo, "commit", "-q", "-m", "bad")
    rejected = _push(repo)
    assert rejected.returncode != 0
    assert ".vault_pass" in rejected.stderr
    refs = subprocess.run(
        ["git", "-C", str(remote), "branch", "--list"], capture_output=True, text=True, check=True
    ).stdout
    assert refs.strip() == ""  # nothing reached the remote

    _git(repo, "rm", "-q", "--cached", ".vault_pass")
    (repo / ".vault_pass").unlink()
    _git(repo, "commit", "-q", "-m", "clean")
    # History still holds the file in the first commit; the tree being pushed is clean.
    assert _push(repo).returncode == 0


def test_pre_push_hook_fails_closed_when_gate_is_missing(tmp_path: Path) -> None:
    repo, _remote = _hooked_clone(tmp_path, {"README.md": "hello\n"})
    (repo / ".githooks/ado_credential_gate.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ok")
    assert _push(repo).returncode != 0


def test_role_runs_the_gate_before_commit_and_before_push() -> None:
    text = TASKS.read_text(encoding="utf-8")
    add = text.index("git add -A")
    gate_in_commit = text.index("ado_credential_gate.py", add)
    commit = text.index('git commit -m "Generate bootstrap playbook repo"')
    assert add < gate_in_commit < commit
    pre_push = text.index("Credential gate before push")
    push = text.index("- name: Generate playbook repo | Push generated repo")
    assert pre_push < push
    assert "--rev" in text[pre_push:push]


def test_role_ignores_every_vault_pass_spelling_in_all_modes() -> None:
    text = TASKS.read_text(encoding="utf-8")
    block_start = text.index("Ignore plaintext preflight secrets")
    block = text[block_start:text.index("Create credential gate directory")]
    for pattern in (".vault_pass", ".vault-pass", "ado-preflight-*.json", "ado-extra-vars.json"):
        assert pattern in block
    assert "when:" not in block  # not limited to push mode


def test_no_vault_password_file_is_tracked_in_this_collection() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True,
    ).stdout.decode().split("\x00")
    gone = [
        name for name in tracked
        if name and (ROOT / name).exists()
        and Path(name).name.lower().replace("-", "_").startswith((".vault_pass", "vault_pass"))
    ]
    assert gone == []


def test_collection_source_passes_the_source_profile() -> None:
    entries = [
        (path, blob) for path, blob in gate.index_entries(str(ROOT))
        if (ROOT / path).exists()  # a deletion the user has not staged yet is not a finding
    ]
    findings = gate.scan_entries(entries, gate.blob_reader(str(ROOT)), [], "source")
    assert findings == [], [f"{p}: {r}" for p, r, _d in findings]


def _local_components():
    spec = importlib.util.spec_from_file_location("lc_vault", FILES / "local_components.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _one_step_commands(module, repo: Path):
    (repo / "playbooks").mkdir(exist_ok=True)
    (repo / "playbooks/a.yml").write_text("---\n", encoding="utf-8")
    plan = {
        "environment": "dev",
        "steps": [{
            "id": "a", "playbook": "playbooks/a.yml", "title": "A", "available": True,
        }],
    }
    return module.commands(repo, plan, {"steps": ["a"]})


def test_local_components_uses_env_vault_file_and_ignores_repo_vault_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _local_components()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".vault_pass").write_text("not-used\n", encoding="utf-8")

    monkeypatch.delenv("ANSIBLE_VAULT_PASSWORD_FILE", raising=False)
    (_step, args), = _one_step_commands(module, repo)
    assert "--vault-password-file" not in args

    outside = tmp_path / "run" / "vault-pass"
    monkeypatch.setenv("ANSIBLE_VAULT_PASSWORD_FILE", str(outside))
    (_step, args), = _one_step_commands(module, repo)
    assert args[args.index("--vault-password-file") + 1] == str(outside)
    assert ".vault_pass" not in args


def test_gate_cli_is_executable_as_a_script(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"README.md": "ok\n"})
    done = subprocess.run(
        [sys.executable, str(GATE), "--repo", str(repo)],
        capture_output=True, text=True, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(
    "line",
    [
        "app_admin_password: changeme",
        "app_admin_password: password123",
        "userPassword: Passw0rd",
        "DATABASE_SECRET_KEY: changeme-secret-key",
        "bindCredential: hunter2hunter2",
    ],
)
def test_well_known_weak_passwords_and_camel_case_keys_are_refused(tmp_path: Path, line: str) -> None:
    """changeme and friends are real values, not markers; camelCase keys are credentials too."""
    repo = _repo(tmp_path, {"group_vars/all/dev/vault_app.yml": f"{line}\n"})
    assert ("group_vars/all/dev/vault_app.yml", "literal-secret") in _rules(_scan(repo)), line
