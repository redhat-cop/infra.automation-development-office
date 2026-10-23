# Role: infra.automation_development_office.ocp_devspaces_user_config

Ocp Devspaces User Config automation role. Primary tasks include: Create Certificate Secret; Create bashrc config map; Create PVC.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_devspaces_user_config_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_devspaces_user_config
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_devspaces_user_config
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create Certificate Secret
- Create bashrc config map
- Create PVC
- Create ssh_config Secret

```bash
cd roles/ocp_devspaces_user_config
molecule test
```

## 📁 Role Structure

```text
roles/ocp_devspaces_user_config/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
