"""Regression tests for bootstrap git username resolution.

The rule lives in
roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2
and must stay aligned with ado-preflight-ui/git-username.js:

    typed git.username wins
    blank Bitbucket -> x-token-auth
    blank GitLab/GitHub -> oauth2
"""
from __future__ import annotations

import re
from pathlib import Path

import jinja2

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2"
PLAYBOOK_REPO_TASKS = (
    REPO / "roles/bootstrap_generate_playbook_repo/tasks/configure_git_auth.yml"
)
PLAYBOOK_REPO_DEFAULTS = REPO / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
TOKEN = "glpat-regression-do-not-log"


def resolve_git_username(scm_tool: str, username: str) -> str:
    trimmed = (username or "").strip()
    if trimmed:
        return trimmed
    if (scm_tool or "").strip().lower() == "bitbucket":
        return "x-token-auth"
    return "oauth2"


def _username_block() -> str:
    text = TEMPLATE.read_text()
    match = re.search(
        r"\{% set bootstrap_generate_env_vars_git_username_raw = \("
        r".*?"
        r"\{% set bootstrap_generate_env_vars_git_scm_username = \("
        r".*?"
        r"\) %\}",
        text,
        re.S,
    )
    assert match, "git username resolution block missing from aap_config_vars.yml.j2"
    return (
        match.group(0)
        + "\n{{ bootstrap_generate_env_vars_git_scm_username }}"
    )


def render_scm_username(*, scm_tool: str, username: str) -> str:
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    template = env.from_string(_username_block())
    return template.render(
        bootstrap_generate_env_vars_preflight={"git": {"username": username}},
        preflight_git={"username": username},
        bootstrap_generate_env_vars_scm_tool=scm_tool,
    ).strip()


def test_gitlab_blank_username_uses_oauth2() -> None:
    assert resolve_git_username("gitlab", "") == "oauth2"
    assert render_scm_username(scm_tool="gitlab", username="") == "oauth2"
    assert render_scm_username(scm_tool="github", username="   ") == "oauth2"


def test_gitlab_supplied_username_is_used() -> None:
    assert resolve_git_username("gitlab", "saml-user") == "saml-user"
    assert render_scm_username(scm_tool="gitlab", username=" saml-user ") == "saml-user"


def test_bitbucket_blank_username_uses_x_token_auth() -> None:
    assert resolve_git_username("bitbucket", "") == "x-token-auth"
    assert render_scm_username(scm_tool="bitbucket", username="") == "x-token-auth"


def test_controller_scm_credential_uses_resolved_username() -> None:
    text = TEMPLATE.read_text()
    resolved = render_scm_username(scm_tool="gitlab", username="saml-user")
    assert resolved == "saml-user"
    credential = re.search(
        r"credential_type: Source Control\n"
        r"    inputs:\n"
        r"      username: \"\{\{ bootstrap_generate_env_vars_git_scm_username \}\}\"\n"
        r"      password: .*",
        text,
    )
    assert credential, "Controller SCM credential must use the resolved username"
    assert "vault_controller_git_token" in credential.group(0)
    assert TOKEN not in text
    assert "generate_playbook_repo_git_username: \"{{ bootstrap_generate_env_vars_git_scm_username }}\"" in text


def test_git_token_is_not_written_to_non_vault_tasks() -> None:
    tasks = PLAYBOOK_REPO_TASKS.read_text()
    write = tasks.split("Write git credentials (basic auth)", 1)[1].split("- name:", 1)[0]
    assert "no_log: true" in write
    assert "vault_controller_git_token" not in write
    assert TOKEN not in tasks
    assert ".git-credentials" in tasks
    assert "name: http.extraHeader" not in tasks
    assert "name: include.path" in tasks
    bearer = tasks.split("Write Bearer auth include file", 1)[1].split("- name:", 1)[0]
    assert "no_log: true" in bearer


def test_cli_username_default_follows_generated_var_without_overriding_callers() -> None:
    defaults = PLAYBOOK_REPO_DEFAULTS.read_text()
    assert (
        "generate_playbook_repo_git_username | default('oauth2', true)"
        in defaults
    )
    assert "vault_controller_git_token | default('', true)" in defaults
    assert (
        "generate_playbook_repo_git_auth_mode | default('basic', true)"
        in defaults
    )
    assert "bootstrap_generate_playbook_repo_git_username: oauth2\n" not in defaults
    main = (
        REPO / "roles/bootstrap_generate_playbook_repo/tasks/main.yml"
    ).read_text()
    assert "include_tasks: configure_git_auth.yml" in main
