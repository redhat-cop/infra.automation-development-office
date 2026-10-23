# Role: infra.automation_development_office.rhel_cron

Rhel Cron automation role. Primary tasks include: Creating Special Cron Jobs; Control @Annual Cron Jobs; Control @Daily Cron Jobs.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhel_cron_type` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: Run rhel_cron
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhel_cron
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Creating Special Cron Jobs
- Control @Annual Cron Jobs
- Control @Daily Cron Jobs
- Control @Hourly Cron Jobs

```bash
cd roles/rhel_cron
molecule test
```

## 📁 Role Structure

```text
roles/rhel_cron/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
