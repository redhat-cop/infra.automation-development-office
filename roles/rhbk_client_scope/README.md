# Role: infra.automation_development_office.rhbk_client_scope

Rhbk Client Scope automation role. Primary tasks include: Create client scope; Delete RHBK client scope; Login to RHBK and get admin token.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhbk_client_scope_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run rhbk_client_scope
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_client_scope
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create client scope
- Delete RHBK client scope
- Login to RHBK and get admin token
- Get list of client scopes

```bash
cd roles/rhbk_client_scope
molecule test
```

## 📁 Role Structure

```text
roles/rhbk_client_scope/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
