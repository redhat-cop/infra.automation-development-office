# Role: infra.automation_development_office.rhbk_users

Manage Red Hat build of Keycloak users and user-group membership operations.

## Role Author

Automation Development Office.

## ✅ Role Requirements

- Reachable Red Hat build of Keycloak endpoint with admin API access.
- Realm admin credentials for user and group management.
- Current role implementation uses a mix of:
  - `community.general.keycloak_user` for create
  - direct `ansible.builtin.uri` calls for delete and group membership actions
- Red Hat collection path exists for equivalent operations:
  - `redhat.rhbk.keycloak_user`
  - `redhat.rhbk.keycloak_user_group_mapping`

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `state` | Supported values: `present`, `absent`, `add_user_to_group`, `remove_user_from_group`. | Yes | N/A |
| `rhbk_realm` | Target realm. | Yes | N/A |
| `rhbk_verify_ssl` | SSL verification flag for URI-based calls. | No | `true` |
| `rhbk_user_username` | Username to look up. Used for `absent`, `add_user_to_group`, and `remove_user_from_group`. | Yes* | N/A |
| `rhbk_group_name` | Group name to map or unmap for user membership operations. | Yes** | N/A |
| `rhbk_host` | RHBK host used in REST endpoints for URI-based flows. | Yes*** | N/A |
| `rhbk_admin_user` | Admin username for token acquisition in URI-based flows. | Yes*** | N/A |
| `rhbk_admin_password` | Admin password for token acquisition in URI-based flows. | Yes*** | N/A |
| `rhbk_hostname` | Keycloak URL passed to `community.general.keycloak_user`. | Yes**** | N/A |
| `rhbk_username` | Admin username passed to `community.general.keycloak_user`. | Yes**** | N/A |
| `rhbk_password` | Admin password passed to `community.general.keycloak_user`. | Yes**** | N/A |
| `rhbk_new_username` | Username of user to create. | Yes**** | N/A |
| `rhbk_new_firstname` | First name for new user. | No | `undefined` |
| `rhbk_new_lastname` | Last name for new user. | No | `undefined` |
| `rhbk_new_email` | Email for new user. | No | `undefined` |
| `rhbk_user_enabled` | Enable or disable user. | No | `undefined` |
| `rhbk_user_email_verified` | Email verification flag for new user. | No | `undefined` |
| `rhbk_new_user_pwd` | Initial user password value. | Yes**** | N/A |
| `rhbk_user_pwd_temporary` | Temporary-password flag for new user credentials. | No | `undefined` |

> **Notes:**
> \* Required when `state` is `absent`, `add_user_to_group`, or `remove_user_from_group`.
> \*\* Required when `state` is `add_user_to_group` or `remove_user_from_group`.
> \*\*\* Required for URI-based task paths (`absent`, `add_user_to_group`, `remove_user_from_group`).
> \*\*\*\* Required when `state` is `present`.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_users
      vars:
        state: add_user_to_group
        rhbk_host: rhbk.example.com
        rhbk_admin_user: admin
        rhbk_admin_password: "{{ vault_rhbk_admin_password }}"
        rhbk_realm: myrealm
        rhbk_verify_ssl: false
        rhbk_user_username: user1
        rhbk_group_name: platform-admins
```

## 🧪 Role Molecule Testing

There is no dedicated extension-level Molecule scenario for this role in the current repository layout.

## 📁 Role Structure

```text
rhbk_users/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   ├── main.yml
│   ├── rhbk_add_user_to_group.yml
│   ├── rhbk_manage_user.yml
│   ├── rhbk_remove_user.yml
│   └── rhbk_remove_user_from_group.yml
└── vars/
    └── main.yml
```
