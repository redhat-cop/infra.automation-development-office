# Role: infra.automation_development_office.bootstrap_framework_defaults

Load shared bootstrap framework defaults before component-specific roles resolve
their effective configuration.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Bootstrap playbooks that use the ADO component default and override model
- Inventory or extra vars that define the target environment

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `env` | Target environment name, such as `dev`, `test`, or `prod`. |
| `component` | Optional component being prepared by the bootstrap framework. |
| `components_env` | Environment-specific component override mapping. |
| `components_override` | Highest-precedence component override mapping. |

## 🚀 Role Usage

```yaml
- name: Load bootstrap framework defaults
  hosts: localhost
  gather_facts: false
  vars:
    env: prod
  roles:
    - role: infra.automation_development_office.bootstrap_framework_defaults
```

## 🧪 Role Molecule Testing

This role is checked with bootstrap role linting and playbook-level bootstrap
tests.

```bash
ansible-lint --offline roles/bootstrap_framework_defaults
yamllint roles/bootstrap_framework_defaults/tasks
```

## 📁 Role Structure

```text
roles/bootstrap_framework_defaults/
  defaults/main.yml
  tasks/main.yml
  vars/main.yml
  README.md
```
