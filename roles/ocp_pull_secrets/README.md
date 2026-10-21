# Role: infra.automation_development_office.ocp_pull_secrets

Ocp Pull Secrets automation role. Primary tasks include: Assert state is provided via -e or AAP survey; Normalize state; Set defaults for pull secret target.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_pull_secrets_name` | Resource name used by this role. |
| `ocp_pull_secrets_namespace` | OpenShift namespace value used by this role. |
| `ocp_pull_secrets_registry_host` | Endpoint or host value used by this role. |
| `ocp_pull_secrets_registry_username` | Resource name used by this role. |
| `ocp_pull_secrets_registry_password` | Sensitive credential value used by this role. |

## 🚀 Role Usage

```yaml
- name: ADO | Update OpenShift pull secret
  hosts: localhost
  gather_facts: false
  vars:
    component: pull_secret
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks: null
  roles:
    - role: infra.automation_development_office.ocp_pull_secrets
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Assert state is provided via -e or AAP survey
- Normalize state
- Set defaults for pull secret target
- Read current pull-secret

```bash
cd roles/ocp_pull_secrets
molecule test
```

## 📁 Role Structure

```text
roles/ocp_pull_secrets/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
