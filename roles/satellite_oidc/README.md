# Role: infra.automation_development_office.satellite_oidc

Wire a Red Hat Satellite server to Keycloak / Red Hat build of Keycloak (RHBK)
for OpenID Connect login.

The role creates the confidential OIDC client with `infra.automation_development_office.rhbk_client`
(default client id `ado-satellite` in realm `rhlab`), fetches the client secret,
enables Foreman Keycloak on the Satellite host, and applies Satellite OIDC
settings (`authorize_login_delegation`, issuer, audience, JWKS, logout URL).

Run this role against the Satellite server after install. Keycloak API calls
are delegated to localhost. Satellite API credentials are required for Hammer
settings.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible >= 2.16
- Target host: Red Hat Satellite server
- Privileged access on the Satellite host (`become: true`) for
  `satellite-installer`, Apache, and Hammer
- Required collections: `infra.automation_development_office` (`rhbk_client`), `community.general`
- Keycloak admin credentials when creating or fetching the client secret
- Satellite administrator credentials for Hammer OIDC settings

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `satellite_oidc_state` | `present` or `absent`. Default `present`. |
| `satellite_oidc_create_client` | Create/update the Keycloak client with `infra.automation_development_office.rhbk_client`. Default `true`. |
| `satellite_oidc_configure_satellite` | Enable OIDC on the Satellite host. Default `true`. |
| `satellite_oidc_client_id` | Keycloak client id. Default `ado-satellite`. |
| `satellite_oidc_realm` | Keycloak realm. Default `rhlab`. |
| `satellite_oidc_keycloak_url` | Keycloak base URL. Default `https://keycloak.apps.ocp.prod.rhlab`. |
| `satellite_oidc_issuer` | OIDC issuer URL. Derived from hostname + realm when empty. |
| `satellite_oidc_client_secret` | Existing client secret. Fetched from Keycloak when empty. |
| `satellite_oidc_admin_user` | Keycloak admin user. Falls back to `rhbk_admin_user` / `admin`. |
| `satellite_oidc_admin_password` | Keycloak admin password. Falls back to `rhbk_admin_password`. |
| `satellite_oidc_server_url` | Satellite URL used for redirect URIs and API. |
| `satellite_oidc_username` | Satellite API username. Default `admin`. |
| `satellite_oidc_password` | Satellite API password. |
| `satellite_oidc_run_installer` | Run `satellite-installer --foreman-keycloak`. Default `true`. |
| `satellite_oidc_audience` | JWT audiences Foreman accepts. Empty defaults to client id plus Keycloak `account`. |

`rhbk_hostname`, `rhbk_realm`, `rhbk_admin_user`, and `rhbk_admin_password`
from the RHBK bootstrap vars are accepted as fallbacks.

## 🚀 Role Usage

### Bootstrap Usage

#### ado-configure-satellite-oidc-bootstrap.yml

```yaml
- name: ADO | Configure Satellite Keycloak OIDC
  hosts: all
  gather_facts: true
  become: true
  vars_files:
    - group_vars/all/{{ env }}/vault_satellite.yml
    - group_vars/all/{{ env }}/vars_satellite.yml
  roles:
    - role: infra.automation_development_office.satellite_oidc
```

Sign in at `https://<satellite>/users/extlogin` after the role completes.

## 🧪 Role Molecule Testing

No dedicated Molecule scenario. Validate against a lab Satellite and the
existing `rhlab` realm.

```bash
ansible-playbook -i sat.server.lab, \
  playbooks/satellite/ado-configure-satellite-oidc-bootstrap.yml
```

## 📁 Role Structure

```text
roles/satellite_oidc/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
    main.yml
    create_client.yml
    fetch_secret.yml
    configure_satellite.yml
    disable.yml
  templates/
    oidc-apache.conf.j2
```
