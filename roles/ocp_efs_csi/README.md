# Role: infra.automation_development_office.ocp_efs_csi

Ocp Efs Csi automation role. Primary tasks include: Create Storage Class; EFS CSI Storage Driver.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_efs_csi_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_efs_csi
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_efs_csi
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create Storage Class
- EFS CSI Storage Driver

```bash
cd roles/ocp_efs_csi
molecule test
```

## 📁 Role Structure

```text
roles/ocp_efs_csi/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
