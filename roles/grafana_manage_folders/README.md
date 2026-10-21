# Role: infra.automation_development_office.grafana_manage_folders

Grafana Manage Folders automation role. Primary tasks include: Create/Update a Folder in Grafana; Normalize grafana_manage_folders variables; Create grafana folder.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `grafana_manage_folders_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run grafana_manage_folders
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.grafana_manage_folders
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create/Update a Folder in Grafana
- Normalize grafana_manage_folders variables
- Create grafana folder

```bash
cd roles/grafana_manage_folders
molecule test
```

## 📁 Role Structure

```text
roles/grafana_manage_folders/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
