# Role: infra.automation_development_office.rhbk_manage_federation

Rhbk Manage Federation automation role. Primary tasks include: Create RHBK federation; Delete RHBK federation; Ensure LDAP federation provider is absent.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhbk_manage_federation_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run rhbk_manage_federation
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_manage_federation
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create RHBK federation
- Delete RHBK federation
- Ensure LDAP federation provider is absent
- Ensure LDAP federation provider exists

```bash
cd roles/rhbk_manage_federation
molecule test
```

## 📁 Role Structure

```text
roles/rhbk_manage_federation/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
