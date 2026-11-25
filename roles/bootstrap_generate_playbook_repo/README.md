# Role: infra.automation_development_office.bootstrap_generate_playbook_repo

Create or refresh the generated bootstrap playbook repository structure used by
ADO component automation.

## Role Author

Automation Development Office

## Platform coverage

Playbooks in `bootstrap_generate_playbook_repo_generated_playbooks` set
`target_platform` to `openshift` or `linux`. See the collection
[Bootstrap coverage](https://github.com/redhat-cop/infra.automation-development-office/blob/main/README.md#bootstrap-coverage-openshift-vs-rhel)
tables for a simple OpenShift vs RHEL install/configure checklist.

## ✅ Role Requirements

- Ansible Core
- Write access to the target bootstrap repository directory
- Optional Git remote credentials when automatic commit and push is enabled
- Seed playbook content bundled with this collection

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `bootstrap_generate_playbook_repo_dest` | Destination repository root for generated files. |
| `bootstrap_generate_playbook_repo_seed_src` | Source directory for baseline repository seed files. |
| `bootstrap_generate_playbook_repo_force` | Overwrites generated content when true. |
| `bootstrap_generate_playbook_repo_git_mode` | Git behavior, such as manual or automatic push flow. |
| `bootstrap_generate_playbook_repo_git_remote` | Git remote name to configure or update. |
| `bootstrap_generate_playbook_repo_git_branch` | Branch used for generated repository commits. |
| `bootstrap_generate_playbook_repo_git_message` | Commit message for generated content. |
| `bootstrap_generate_playbook_repo_git_username` | HTTPS git username. An explicit value wins. Otherwise the username generated from preflight JSON (`oauth2`, `x-token-auth`, or the typed name). |
| `bootstrap_generate_playbook_repo_git_token` | Git password. An explicit value wins. Otherwise `vault_controller_git_token` from the generated vault. The token is not written into the remote URL. |
| `bootstrap_generate_playbook_repo_git_auth_mode` | `basic` uses the credential store. `bearer` (Bitbucket) uses a mode 0600 include file. An explicit value wins. |
| `bootstrap_generate_playbook_repo_git_sync_before_push` | Rebase on the remote branch before pushing generated commits. Defaults to `true`. |
| `bootstrap_generate_playbook_repo_write_galaxy_requirements` | Always true: write Hub/Galaxy `collections/requirements.yml` only. Collection trees are never committed to git. |
| `bootstrap_generate_playbook_repo_infra_ado_collection_version` | Unused. Generated `collections/requirements.yml` never pins collection versions. |
| `bootstrap_generate_playbook_repo_component` | Component group to generate, such as `all`, `openshift`, or `rhel`. Used only when `bootstrap_generate_playbook_repo_selected_components` is unset (CLI full catalog). |
| `bootstrap_generate_playbook_repo_selected_components` | Explicit playbook/JT selector list from preflight. An empty list generates no component playbooks (Galaxy / AAP-tabs-only). `all` in the list dumps the catalog. Unset plus `component=all` is the CLI full-catalog path. |
| `bootstrap_generate_playbook_repo_component_map` | Maps component selections to generated playbook groups. |
| `bootstrap_generate_playbook_repo_generated_playbooks` | Manifest of bundled playbooks copied into the generated repository. |

Generated `ansible.cfg` sets `display_skipped_hosts = False` so Controller
and local CLI recaps omit skipped tasks. Set
`ANSIBLE_DISPLAY_SKIPPED_HOSTS=true` on a job or shell when debugging
`when:` conditions.

This role always writes Hub/Galaxy `collections/requirements.yml` and removes
any vendored collection trees from the git playbook repo. Contoller project
sync installs collections from Hub — never from git trees.

## 🚀 Role Usage

```yaml
- name: Generate bootstrap playbook repository
  hosts: localhost
  gather_facts: false
  vars:
    bootstrap_generate_playbook_repo_dest: "{{ playbook_dir }}"
    bootstrap_generate_playbook_repo_component: all
  roles:
    - role: infra.automation_development_office.bootstrap_generate_playbook_repo
```

## 🧪 Role Molecule Testing

`extensions/molecule/integration_git_scm_username` generates Controller SCM
credentials from preflight JSON alone, then writes the git credential file or
Bitbucket Bearer include file. An explicit username parameter is left unchanged.

```bash
ansible-lint --offline roles/bootstrap_generate_playbook_repo
yamllint roles/bootstrap_generate_playbook_repo/tasks
cd extensions/molecule && molecule test -s integration_git_scm_username
```

## 📁 Role Structure

```text
roles/bootstrap_generate_playbook_repo/
  defaults/main.yml
  files/playbook_repo_seed/
  files/playbooks/
  tasks/main.yml
  tasks/configure_git_auth.yml
  README.md
```

### Local component execution

Generation also writes `component-run-plan.json` and `local_components.py`.
The plan includes only selected executable playbooks, excluding supporting task
files. When `cert_manager` is selected, IdM ACME and AWSPCA playbooks are
included only for the matching cert-manager mode, and the default-ingress
playbook only when `update_default_ingress` is enabled (same gates as
Contoller). The ingress keep/drop gate reads
``bootstrap_controller_update_default_ingress`` when set (AAP /
``aap_config_vars.yml``), otherwise falls back to preflight
``component_config.cert_manager.update_default_ingress`` / OpenShift option
``update_default_ingress`` so No-AAP runs that skip ``aap_config_vars.yml``
still emit ``ado-update-default-ingress-cert-bootstrap.yml``. Ingress-only
selection does not keep the Deploy cert-manager playbook; that requires an
explicit Certificate Manager app selection. Cert-manager ``state=absent``
deletes only ADO ClusterIssuers (``idm-acme``, ``root-ca-issuer``, and optional
``bootstrap_cert_manager_extra_clusterissuers``), not every ClusterIssuer
on the cluster. Existing job-template surveys supply step inputs; existing workflow
success edges determine execution order (nested workflows such as
``ADO | RHBK Workflow`` expand so Deploy RHBK runs before OAuth). Selection
order is preserved for independent steps and can be adjusted in the preflight
UI; hard Contoller edges still win. Generation never executes components.

Use a request JSON file outside the Git repository:

```json
{
  "steps": [
    "playbooks/rhbk/ado-deploy-and-configure-bootstrap.yml",
    "playbooks/rhbk/ado-manage-realm-bootstrap.yml"
  ],
  "values": {},
  "extra_args": "--check"
}
```

From the generated repository:

```bash
python3 local_components.py --request /secure/component-request.json --preview
python3 local_components.py --request /secure/component-request.json
```

Select IDs from the generated plan. Required survey inputs belong in
`values[playbook_id][variable]`. Secret survey inputs are masked in previews.
The runner uses `inventory`, the generated environment, `state=present`, and
the Vault password file named by `ANSIBLE_VAULT_PASSWORD_FILE` when it is set.
The runner never looks for a `.vault_pass` inside the repository. Extra arguments apply to each playbook and may
override these defaults. Execution uses subprocess arguments, not shell
interpolation, and stops at the first nonzero exit. Target access and installed
collections remain prerequisites. Never commit a request containing secrets.
Steps with unresolved Controller-templated extra variables are unavailable.

### Credential safety

The generated repository must never receive a Vault password file, a plaintext
Preflight export, or a literal credential.

- `.gitignore` always lists `.vault_pass`, `.vault-pass`, `ado-preflight-*.json`
  (except `*.json.vault.yml`), `tmp-ado-preflight-*.json` and
  `ado-extra-vars.json`. This is a second layer only.
- `.githooks/ado_credential_gate.py` and `.githooks/pre-push` are written into
  the repository. In `push` mode the role sets `core.hooksPath` so the hook runs.
- In `push` mode the role runs the gate after `git add -A` and before the commit
  (tracked and staged files), and again against `HEAD` before `git push`. A
  finding fails the task and names the file and rule, never the value.
- Ansible Vault encrypted files are allowed. Clearly fake values in
  `*.fixture.json` files, documentation, and test folders are allowed. Reviewed
  fixtures can be listed in `.credential-gate-allow`.
- Run it by hand: `python3 .githooks/ado_credential_gate.py --repo . --profile repo`.
  The collection itself uses `--profile source`.
- The gate also refuses **plaintext internal topology** under `group_vars/` and
  `configs/` (rule `plaintext-topology`, `repo` profile only): internal
  hostnames, domains, API endpoints, SMTP relays, LDAP base DNs, IP addresses and
  address ranges. Bootstrap routes these into Ansible Vault (see
  `bootstrap_generate_env_vars`), so a generated repository passes. The finding
  names the key and line, never the value. Example and placeholder values
  (`example.com`, `localhost`, `*.svc`) and public registries pass. A test
  directory *above* `group_vars`/`configs` (for example `tests/` or `molecule/`)
  is exempt; an environment that is itself named `test`, `molecule` or `examples`
  is not. The rules live in `.githooks/ado_topology_rules.py`, which the role
  writes next to the gate; the gate fails closed if that file is missing.
- The rendered `configs/controller_projects.yml` holds the Git URL, so the role
  runs the `bootstrap_generate_env_vars` topology pass (`topology_freeze_configs.yml`)
  right after rendering it. The committed file then carries only a
  `{{ vault_topology_cfg_... }}` reference, with or without AAP. When Vault
  encryption or topology routing is turned off, the gate refuses the file
  (`plaintext-topology`) and says to re-run with vault encryption on.
- Seed playbooks ship no passwords. `playbooks/vpn/ado-manage-vpn-access-bootstrap.yml`
  takes the initial user password from `vault_lab_user_password` (or from the
  request's `new_password` / `temp_password`) and stops with a clear message when
  neither exists. `playbooks/dirsrv/ado-ldap-modify-bootstrap.yml` takes the bind
  password from `vault_ldap_bind_password` and stops when it is missing. A unit
  test fails if a seed playbook defines a literal value for a secret-named variable.
- The raw Controller push steps in `bootstrap_controller` (vars-only, pre-apply and
  post-configs pushes) run the same gate after staging and again on the commit.
- Supply the Vault password at run time with `ANSIBLE_VAULT_PASSWORD_FILE` or
  `--vault-password-file` pointing outside the repository. Preflight Init does
  this with a temporary file in memory-backed storage.
