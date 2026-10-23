# Role: `rhbk_setup_mapper`

This Ansible role manages LDAP group mapper components in Red Hat build of Keycloak.

It can create or remove mapper components linked to an existing LDAP federation provider.

> **Note:**
> This role uses Keycloak admin REST endpoints via `ansible.builtin.uri`, so API access and admin credentials are required.

## Role Author

Automation Development Office.

## ✅ Role Requirements

- Ansible-managed host or controller with network access to the RHBK admin API.
- Admin credentials with permission to query components and manage LDAP mappers.
- Existing LDAP federation component in the target realm when using `state: present`.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `state` | Role action. Supported values: `present`, `absent`. | Yes | N/A |
| `rhbk_host` | RHBK host used to build API URLs. | Yes | N/A |
| `rhbk_realm` | Target realm where mapper changes are applied. | Yes | N/A |
| `rhbk_admin_user` | Admin username for token retrieval. | Yes | N/A |
| `rhbk_admin_password` | Admin password for token retrieval. | Yes | N/A |
| `rhbk_verify_ssl` | Validate TLS certificates for API requests. | No | `true` |
| `rhbk_federation_name` | LDAP federation component name used to resolve parent component ID (`present` flow). Set via preflight **Federation Name** (`component_config.rhbk.federation_name`). | Yes (`present`) | `LDAP` |
| `ldap_group_config` | Mapper `config` payload for `group-ldap-mapper` component creation (`present` flow). | Yes (`present`) | N/A |
| `ldap_user_mappers` | List of IdM `user-attribute-ldap-mapper` definitions (name + config). | No | From vault template |
| `rhbk_setup_ldap_user_mappers` | When true with `state: present`, create `ldap_user_mappers` after group mapper. | No | `true` |

> **Notes:**
> `state: present` creates mapper `ldap-group-mapper` only when it does not already exist.
> `state: absent` removes mapper `ldap-group-mapper` when found.

## 🚀 Role Usage

### Example 1: Create LDAP group mapper

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_setup_mapper
      vars:
        state: present
        rhbk_host: rhbk.example.com
        rhbk_realm: demo
        rhbk_admin_user: admin
        rhbk_admin_password: "{{ vault_rhbk_admin_password }}"
        rhbk_verify_ssl: false
        rhbk_federation_name: IDM
        ldap_group_config:
          groups.dn:
            - "ou=Groups,dc=example,dc=com"
          mode:
            - "LDAP_ONLY"
          membership.ldap.attribute:
            - "member"
```

### Example 2: Remove LDAP group mapper

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_setup_mapper
      vars:
        state: absent
        rhbk_host: rhbk.example.com
        rhbk_realm: demo
        rhbk_admin_user: admin
        rhbk_admin_password: "{{ vault_rhbk_admin_password }}"
        rhbk_verify_ssl: false
```

## 🔧 Tasks Overview

- **Main Task File** (`tasks/main.yml`):
  - Routes execution by `state`:
    - `present` imports `rhbk_setup_group_mapper.yml` then `rhbk_setup_ldap_user_mappers.yml`
    - `absent` imports `rhbk_remove_group_mapper.yml`
- **Create Flow** (`tasks/rhbk_setup_group_mapper.yml`):
  - Authenticates to obtain admin token.
  - Finds LDAP federation component by `rhbk_federation_name`.
  - Checks existing LDAP mapper components for duplicate mapper name.
  - Creates mapper component when missing.
- **Delete Flow** (`tasks/rhbk_remove_group_mapper.yml`):
  - Authenticates and lists LDAP mapper components.
  - Resolves mapper ID by name.
  - Deletes mapper component when present.

## 🧪 Role Molecule Testing

There is no dedicated extension-level Molecule scenario for this role in the current repository layout.

## 📁 Role Structure

```text
rhbk_setup_mapper/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   ├── main.yml
│   ├── rhbk_setup_group_mapper.yml
│   └── rhbk_remove_group_mapper.yml
└── vars/
    └── main.yml
```

## License

GPL-3.0-or-later
