# Role: infra.automation_development_office.ocp_acs

Ocp Acs automation role. Primary tasks include: Validate required ACS vars; Ensure ACS operand namespace exists; Delete Central CR (clean reinstall).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_acs_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_acs
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_acs
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Validate required ACS vars
- Ensure ACS operand namespace exists
- Delete Central CR (clean reinstall)
- Delete Central route (clean reinstall)

```bash
cd roles/ocp_acs
molecule test
```

## 📁 Role Structure

```text
roles/ocp_acs/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
