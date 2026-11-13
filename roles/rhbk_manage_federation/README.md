# Role: infra.automation_development_office.rhbk_manage_federation

Create or update a Keycloak / RHBK LDAP user federation provider, then validate
connection URL and bind authentication. Does not treat “provider present” as
proof that LDAP sync works.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- `community.general.keycloak_user_federation`
- Reachable Keycloak Admin API (`rhbk_host` / `rhbk_keycloak_base_url`)
- Vault/vars providing LDAP settings (see below)

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ldap_config` | Keycloak LDAP config map (`connectionUrl`, `bindDn`, `usersDn`, `bindCredential`, …). Preferred source. |
| `federation_ldap_url` / `federation_bind_dn` / `federation_users_dn` / `federation_bind_password` | Preflight aliases; used when `ldap_config` fields are blank. |
| `rhbk_federation_name` / `federation_name` | Provider name (default `LDAP`). |
| `rhbk_realm` | Target realm. |
| `rhbk_admin_user` / `rhbk_admin_password` | Master-realm admin for Admin API. |
| `rhbk_federation_test_connection` | Call Keycloak `testLDAPConnection` after apply (default `true`). |
| `rhbk_federation_verify_sync` | Optional changed-users sync check (default `false`). |
| `state` | `present` or `absent`. |

FreeIPA / IdM: when `federation_provider` is FreeIPA/IdM/IPA, or `usersDn`
contains `cn=accounts`, the role applies FreeIPA-oriented defaults
(`uuidLDAPAttribute=ipaUniqueID`, `searchScope=2`, posix object classes) while
keeping Keycloak vendor `rhds` (389 Directory Server). Bind credentials, Base
DN, and server URL are never invented.

## 🚀 Role Usage

```yaml
- name: Configure RHBK LDAP federation
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_manage_federation
      vars:
        state: present
        rhbk_realm: Dev
        rhbk_federation_name: LDAP
        ldap_config:
          connectionUrl: ldap://idm.example.com
          bindDn: uid=bind,cn=users,cn=accounts,dc=example,dc=com
          usersDn: cn=users,cn=accounts,dc=example,dc=com
          bindCredential: "{{ vault_ldap_bind_password }}"
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

```bash
cd roles/rhbk_manage_federation
molecule test
```

Unit coverage for config generation lives in
`tests/unit/bootstrap/test_rhbk_ldap_federation.py`.

## 📁 Role Structure

```text
roles/rhbk_manage_federation/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  vars/
```
