# Role: infra.automation_development_office.idm_server

Idm Server automation role. Primary tasks include: Install IDM server; Validate idm_server inputs; Add IDM Server entry.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `idm_server_state` | Desired state used by role tasks when supported. |
| `idm_server_name` | Resource name used by this role. |
| `idm_server_ipaadmin_password` | Endpoint or host value used by this role. |

## 🚀 Role Usage

```yaml
- name: Run idm_server
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.idm_server
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Install IDM server
- Validate idm_server inputs
- Add IDM Server entry

```bash
cd roles/idm_server
molecule test
```

## 📁 Role Structure

```text
roles/idm_server/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
