# Role: infra.automation_development_office.rhel_services_management

Rhel Services Management automation role. Primary tasks include: Read RHEL major version (raw); Parse major version from raw output; Choose path booleans from major.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhel_services_management_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run rhel_services_management
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhel_services_management
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Read RHEL major version (raw)
- Parse major version from raw output
- Choose path booleans from major
- Gather service facts (RHEL 9/10)

```bash
cd roles/rhel_services_management
molecule test
```

## 📁 Role Structure

```text
roles/rhel_services_management/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
