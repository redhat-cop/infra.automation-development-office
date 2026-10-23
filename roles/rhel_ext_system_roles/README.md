# Role: infra.automation_development_office.rhel_ext_system_roles

Rhel Ext System Roles automation role. Primary tasks include: Gather minimal facts for RHEL System Roles (expanded subset); Normalize wrapper inputs; Normalize SELinux inputs.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- `redhat.rhel_system_roles` installed in the execution environment when
  running RHEL System Roles such as `stig`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhel_ext_system_roles_roles_map` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: Run rhel_ext_system_roles
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhel_ext_system_roles
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Gather minimal facts for RHEL System Roles (expanded subset)
- Normalize wrapper inputs
- Normalize SELinux inputs
- Map selinux_state to role-accepted values
- Invoke selected RHEL System Roles, including `stig` for RHEL STIG hardening

### STIG hardening example

Install the optional STIG dependency when it is not already included in the
execution environment:

```bash
ansible-galaxy collection install -r collections/requirements-stig.yml
```

```yaml
- name: Apply RHEL STIG hardening
  hosts: rhel_servers
  become: true
  gather_facts: true
  roles:
    - role: infra.automation_development_office.rhel_ext_system_roles
      vars:
        sr_apply:
          - stig
        sr_vars:
          stig:
            stig_profile: stig
```

```bash
cd roles/rhel_ext_system_roles
molecule test
```

## 📁 Role Structure

```text
roles/rhel_ext_system_roles/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
