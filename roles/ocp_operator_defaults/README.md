# Role: infra.automation_development_office.ocp_operator_defaults

Ocp Operator Defaults automation role. Primary tasks include: Get list of all PackageManifests; Build list of matching operators; Fail if no matching operators found.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_operator_defaults_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_operator_defaults
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_operator_defaults
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Get list of all PackageManifests
- Build list of matching operators
- Fail if no matching operators found
- Show all matching operator packages

```bash
cd roles/ocp_operator_defaults
molecule test
```

## 📁 Role Structure

```text
roles/ocp_operator_defaults/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
