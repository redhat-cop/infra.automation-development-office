# Role: infra.automation_development_office.idm_client

Idm Client automation role. Primary tasks include: Register IPA client; Register IDM Client.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `idm_client_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run idm_client
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.idm_client
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Register IPA client
- Register IDM Client

```bash
cd roles/idm_client
molecule test
```

## 📁 Role Structure

```text
roles/idm_client/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
