# Role: infra.automation_development_office.ocp_service_accounts

Ocp Service Accounts automation role. Primary tasks include: Assert per-item inputs; Ensure ocp_service_accounts_exclude_namespaces exists; Use provided target_namespaces if available.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_service_accounts_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_service_accounts
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_service_accounts
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Assert per-item inputs
- Ensure ocp_service_accounts_exclude_namespaces exists
- Use provided target_namespaces if available
- Gather all namespaces (only when name_space == 'all' and target_namespaces not provided)

```bash
cd roles/ocp_service_accounts
molecule test
```

## 📁 Role Structure

```text
roles/ocp_service_accounts/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
