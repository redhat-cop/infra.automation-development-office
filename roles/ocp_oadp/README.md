# Role: infra.automation_development_office.ocp_oadp

Ocp Oadp automation role. Primary tasks include: OADP | Skip configuration when disabled; OADP | Configure DataProtectionApplication (optional STS).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_oadp_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_oadp
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_oadp
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- OADP | Skip configuration when disabled
- OADP | Configure DataProtectionApplication (optional STS)

```bash
cd roles/ocp_oadp
molecule test
```

## 📁 Role Structure

```text
roles/ocp_oadp/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
