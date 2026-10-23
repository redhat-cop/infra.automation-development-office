# Role: infra.automation_development_office.rhbk_manage_idp

Configure and remove identity provider settings for Red Hat build of Keycloak.

## Role Author

Automation Development Office.

## ✅ Role Requirements

- Reachable Red Hat build of Keycloak endpoint.
- Admin credentials with permission to manage realm identity providers.
- `community.general` collection for `community.general.keycloak_identity_provider`.

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `state` | Role action (`present` to configure identity provider, `absent` to remove it). |
| `rhbk_host` | RHBK host used for admin API requests. |
| `rhbk_realm` | Target realm. |
| `rhbk_admin_user` | Admin username. |
| `rhbk_admin_password` | Admin password. |
| `rhbk_verify_ssl` | SSL validation flag (`true`/`false`). |
| `rhbk_setup_idp_entra_discovery_url` | OIDC issuer/discovery base URL used by create path. |
| `entra_idp_alias` | Identity provider alias to create/delete. |
| `entra_client_id` | OIDC client ID. |
| `entra_client_secret` | OIDC client secret. |

Delete path behavior (`state: absent`):

- Removes OIDC identity provider alias `entra_idp_alias` from `rhbk_realm`.
- Uses the same module/auth contract as the create path.

Notes:

- `defaults/main.yml` and `vars/main.yml` currently do not define role defaults.
- Role tasks no longer require caller-provided bearer token facts.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.rhbk_manage_idp
      vars:
        state: present
        rhbk_host: rhbk.example.com
        rhbk_realm: myrealm
        rhbk_admin_user: admin
        rhbk_admin_password: "{{ vault_rhbk_admin_password }}"
        rhbk_verify_ssl: false
        rhbk_setup_idp_entra_discovery_url: "https://login.microsoftonline.com/<tenant>/v2.0"
        entra_idp_alias: entra
        entra_client_id: "{{ vault_entra_client_id }}"
        entra_client_secret: "{{ vault_entra_client_secret }}"
```

## 🧪 Role Molecule Testing

There is no dedicated extension-level Molecule scenario for this role in the
current repository layout.

## 📁 Role Structure

```text
rhbk_manage_idp/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   ├── main.yml
│   ├── rhbk_manage_idp.yml
│   └── rhbk_delete_idp.yml
└── vars/
    └── main.yml
```
