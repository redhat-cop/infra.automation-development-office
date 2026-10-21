# Role: infra.automation_development_office.rhel_facts

Rhel Facts automation role. Primary tasks include: Tuned status; Firewalld status; Memory used/total (MB).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhel_facts_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run rhel_facts
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhel_facts
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Tuned status
- Firewalld status
- Memory used/total (MB)
- Redhat release

```bash
cd roles/rhel_facts
molecule test
```

## 📁 Role Structure

```text
roles/rhel_facts/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
