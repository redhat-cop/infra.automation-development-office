# Role: infra.automation_development_office.bootstrap_flatten_vars

Flatten a named dictionary into top-level Ansible facts for bootstrap playbooks
that expect direct variable names.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- A dictionary variable available in the current play context
- `flatten_var_root` set to the name of the dictionary to export

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `flatten_var_root` | Name of the dictionary variable to flatten into facts. |
| `bootstrap_flatten_vars_component` | Optional component name used for bootstrap context. |
| `component` | Fallback component name when `bootstrap_flatten_vars_component` is not set. |

## 🚀 Role Usage

```yaml
- name: Flatten component defaults
  hosts: localhost
  gather_facts: false
  vars:
    component_defaults:
      namespace: grafana
      state: present
    flatten_var_root: component_defaults
  roles:
    - role: infra.automation_development_office.bootstrap_flatten_vars
```

## 🧪 Role Molecule Testing

Validate this role with a simple local play that provides `flatten_var_root` and
asserts the exported facts.

```bash
ansible-lint --offline roles/bootstrap_flatten_vars
yamllint roles/bootstrap_flatten_vars/tasks roles/bootstrap_flatten_vars/defaults
```

## 📁 Role Structure

```text
roles/bootstrap_flatten_vars/
  defaults/main.yml
  tasks/main.yml
  vars/main.yml
  README.md
```
