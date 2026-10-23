# Role: infra.automation_development_office.install_dirsrv

Install Dirsrv automation role. Primary tasks include: DirSrv Normalize inputs (component vars + vault); DirSrv Assert required component vars; DirSrv Guard bootstrap inputs (vault).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `install_dirsrv_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run install_dirsrv
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.install_dirsrv
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- DirSrv Normalize inputs (component vars + vault)
- DirSrv Assert required component vars
- DirSrv Guard bootstrap inputs (vault)
- Dirsrv Guard replication inputs (vault)

```bash
cd roles/install_dirsrv
molecule test
```

## 📁 Role Structure

```text
roles/install_dirsrv/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
