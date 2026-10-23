# Role: infra.automation_development_office.rhel_mount

Rhel Mount automation role. Primary tasks include: Use blkid to find the filesystem type; Parse the FSTYPE from blkid output; Display the detected filesystem type.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhel_mount_fstype_detection` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: Run rhel_mount
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhel_mount
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Use blkid to find the filesystem type
- Parse the FSTYPE from blkid output
- Display the detected filesystem type
- Assert rhel_mount_action required variable is defined

```bash
cd roles/rhel_mount
molecule test
```

## 📁 Role Structure

```text
roles/rhel_mount/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
