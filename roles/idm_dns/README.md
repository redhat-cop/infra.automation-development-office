# Role: infra.automation_development_office.idm_dns

Idm Dns automation role. Primary tasks include: Add A record to IdM DNS using redhat.rhel_idm.dnsrecord; Add IDM DNS entry.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `idm_dns_state` | Desired state used by role tasks when supported. |
| `idm_dns_ipa_host` | Endpoint or host value used by this role. |
| `idm_dns_ipa_user` | Role input variable used to configure automation behavior. |
| `idm_dns_ipa_pass` | Role input variable used to configure automation behavior. |
| `idm_dns_zone` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: Run idm_dns
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.idm_dns
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Add A record to IdM DNS using redhat.rhel_idm.dnsrecord
- Add IDM DNS entry

```bash
cd roles/idm_dns
molecule test
```

## 📁 Role Structure

```text
roles/idm_dns/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
