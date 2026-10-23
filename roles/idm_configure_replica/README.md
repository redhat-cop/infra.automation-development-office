# Role: infra.automation_development_office.idm_configure_replica

Idm Configure Replica automation role. Primary tasks include: Install IdM replica; Add IdM configure replica entry.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `idm_configure_replica_state` | Desired state used by role tasks when supported. |
| `idm_configure_replica_setup_dns` | Role input variable used to configure automation behavior. |
| `idm_configure_replica_setup_ca` | Role input variable used to configure automation behavior. |
| `idm_configure_replica_no_host_dns` | Endpoint or host value used by this role. |
| `idm_configure_replica_no_ntp` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: Run idm_configure_replica
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.idm_configure_replica
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Install IdM replica
- Add IdM configure replica entry

```bash
cd roles/idm_configure_replica
molecule test
```

## 📁 Role Structure

```text
roles/idm_configure_replica/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
