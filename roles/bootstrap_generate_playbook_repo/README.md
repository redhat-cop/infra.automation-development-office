# Role: infra.ado.bootstrap_generate_playbook_repo

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
| `bootstrap_generate_playbook_repo_git_token` | Optional token used for non-interactive Git pushes. |
| `bootstrap_generate_playbook_repo_git_sync_before_push` | Rebase on the remote branch before pushing generated commits. Defaults to `true`. |
| `bootstrap_generate_playbook_repo_write_galaxy_requirements` | Always true: write Hub/Galaxy `collections/requirements.yml` only. Collection trees are never committed to git. |
| `bootstrap_generate_playbook_repo_infra_ado_collection_version` | Optional pin used only when Galaxy requirements are written. Empty means latest. |
| `bootstrap_generate_playbook_repo_component` | Component group to generate, such as `all`, `openshift`, or `rhel`. |
| `bootstrap_generate_playbook_repo_component_map` | Maps component selections to generated playbook groups. |
| `bootstrap_generate_playbook_repo_generated_playbooks` | Manifest of bundled playbooks copied into the generated repository. |

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
    - role: infra.ado.bootstrap_generate_playbook_repo
```

## 🧪 Role Molecule Testing

Run focused linting against the role and validate generated content with the
bootstrap sample CLI repository.

```bash
ansible-lint --offline roles/bootstrap_generate_playbook_repo
yamllint roles/bootstrap_generate_playbook_repo/tasks
```

## 📁 Role Structure

```text
roles/bootstrap_generate_playbook_repo/
  defaults/main.yml
  files/playbook_repo_seed/
  files/playbooks/
  tasks/main.yml
  README.md
```

### Local component execution

Generation also writes `component-run-plan.json` and `local_components.py`.
The plan includes only selected executable playbooks, excluding supporting task
files. When `cert_manager` is selected, IdM ACME and AWSPCA playbooks are
included only for the matching cert-manager mode, and the default-ingress
playbook only when `update_default_ingress` is enabled (same gates as
Contoller). Existing job-template surveys supply step inputs; existing workflow
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
`.vault_pass` when available. Extra arguments apply to each playbook and may
override these defaults. Execution uses subprocess arguments, not shell
interpolation, and stops at the first nonzero exit. Target access and installed
collections remain prerequisites. Never commit a request containing secrets.
Steps with unresolved Controller-templated extra variables are unavailable.
