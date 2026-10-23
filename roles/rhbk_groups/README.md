# Role: infra.automation_development_office.rhbk_groups

Rhbk Groups automation role. Primary tasks include: Create RHBK group; Delete RHBK group; Create a Keycloak group, authentication with credentials.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhbk_groups_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run rhbk_groups
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_groups
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create RHBK group
- Delete RHBK group
- Create a Keycloak group, authentication with credentials
- Login to RHBK and get admin token

```bash
cd roles/rhbk_groups
molecule test
```

## 📁 Role Structure

```text
roles/rhbk_groups/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
