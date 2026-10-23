# Role: infra.automation_development_office.install_postfix

Install Postfix automation role. Primary tasks include: Ensure namespace exists; Create Secret for relay authentication; Create ConfigMap for Postfix main.cf.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `install_postfix_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run install_postfix
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.install_postfix
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Ensure namespace exists
- Create Secret for relay authentication
- Create ConfigMap for Postfix main.cf
- Delete existing Postfix Pod (if any)

```bash
cd roles/install_postfix
molecule test
```

## 📁 Role Structure

```text
roles/install_postfix/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
