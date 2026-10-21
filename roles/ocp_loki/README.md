# Role: infra.automation_development_office.ocp_loki

Ocp Loki automation role. Primary tasks include: Create/Delete Loki Stack; Loki Stack task.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_loki_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_loki
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_loki
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create/Delete Loki Stack
- Loki Stack task

```bash
cd roles/ocp_loki
molecule test
```

## 📁 Role Structure

```text
roles/ocp_loki/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
