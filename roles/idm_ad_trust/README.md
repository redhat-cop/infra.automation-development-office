# Role: infra.automation_development_office.idm_ad_trust

Establish IdM ↔ Active Directory trust and map AD-only users into IdM POSIX
groups and sudo so they can SSH and sudo on IdM-enrolled Linux clients.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core on the IdM server (role uses ``redhat.rhel_idm`` modules)
- Collections: ``redhat.rhel_idm``, ``ansible.posix``
- Same-collection role ``infra.automation_development_office.rhel_services_management`` for smb / named / sssd
- IdM admin credentials (`vault_idm_admin_password` or `ipaadmin_password`)
- AD Domain Admin credentials (`vault_ad_trust_admin_password`)
- For two-way trust: AD DNS conditional forwarder for the IdM domain so AD can
  resolve IdM SRV records (for example `dev.rhlab` → IdM DC IP)
- Lab reference (2026-08-11): IdM `idm-trust.dev.rhlab` (192.168.0.63),
  AD DC `adwindows.ad.lab` (192.168.0.61), realm `AD.LAB`

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `idm_ad_trust_state` | Desired trust state. Default `present`. |
| `idm_ad_trust_two_way` | When true, establish two-way trust (requires AD DNS forwarder). Default `true`. |
| `idm_ad_trust_ad_domain` | AD DNS domain. Default `ad.lab`. |
| `idm_ad_trust_ad_realm` | AD Kerberos realm. Default derived from `idm_ad_trust_ad_domain`. |
| `idm_ad_trust_ad_dc_hostname` | AD domain controller hostname. |
| `idm_ad_trust_ad_dc_ip` | AD domain controller IP for `/etc/hosts` hint and forward zone. |
| `idm_ad_trust_ad_admin` | AD admin username for trust establish. Default `Administrator`. |
| `idm_ad_trust_ad_admin_password` | AD admin password from vault or extra-vars. |
| `idm_ad_trust_ipa_admin_password` | IdM admin password for ``redhat.rhel_idm`` modules. |
| `idm_ad_trust_configure_groups` | Map AD external groups to POSIX groups and sudo. Default `true`. |
| `idm_ad_trust_map_ad_admins_group` | AD group mapped for admin sudo (for example `Domain Admins@AD.LAB`). |
| `idm_ad_trust_sudo_ad_users` | Optional list of AD users granted sudo (user@REALM). |

## 🚀 Role Usage

```yaml
- hosts: idm_servers
  become: true
  vars:
    idm_ad_trust_ipa_admin_password: "{{ vault_idm_admin_password }}"
    idm_ad_trust_ad_admin_password: "{{ vault_ad_trust_admin_password }}"
    idm_ad_trust_ad_domain: ad.lab
    idm_ad_trust_ad_dc_hostname: adwindows.ad.lab
    idm_ad_trust_ad_dc_ip: 192.168.0.61
    idm_ad_trust_map_ad_admins_group: "Domain Admins@AD.LAB"
    idm_ad_trust_sudo_ad_users:
      - "Administrator@AD.LAB"
  roles:
    - role: infra.automation_development_office.idm_ad_trust
```

Bootstrap playbook: `playbooks/idm/ado-manage-ad-trust-bootstrap.yml`

AAP job template: `ADO | IdM Manage AD Trust` (app option `idm_ad_trust_install`)

After trust, IdM clients need DNS resolution for `AD.LAB`, SSSD IdM domain
configuration, and optional `krb5_validate = False` on the IdM domain stanza
when SSH account checks fail after successful password auth.

## 🧪 Role Molecule Testing

This role is validated against a live IdM/AD lab pair. No Molecule scenario is
shipped; run the bootstrap job template or the usage playbook against lab IdM
and AD hosts.

```bash
ansible-playbook playbooks/idm/ado-manage-ad-trust-bootstrap.yml \
  -e env=dev \
  --vault-password-file .vault_pass
```

## 📁 Role Structure

```text
roles/idm_ad_trust/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
    main.yml
    map_groups_sudo.yml
```
