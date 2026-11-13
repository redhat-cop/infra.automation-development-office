# Role: infra.automation_development_office.ocp_oidc_auth

Ocp Oidc Auth automation role. Primary tasks include: Assert required OIDC inputs are set; Build Keycloak URLs; Show the effective Keycloak target; Try to get Keycloak client secret via module.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_oidc_auth_state` | Desired state used by role tasks when supported. |
| `ocp_rhbk_verify_ssl` | Verify the Keycloak TLS certificate. Unset, null or blank means on. `true` / `yes` / `on` / `1` verify. `false` / `no` / `off` / `0` turn verification off. Any other value is an error; it is never read as false. |
| `ocp_oidc_auth_ca_pem` | PEM of the CA that issued Keycloak's certificate. Optional. Used to verify Keycloak and, as before, given to OpenShift's oauth-server. |
| `openshift_oidc_auth.openshift_oidc_mapping_method` | OpenShift OAuth mapping method. Default `add` so a Keycloak username that already exists (htpasswd `admin`) can sign in. `claim` fails with `Could not create user` when that User already exists. |

### Existing Keycloak client and failure behavior

The OpenShift OAuth callback path is the exact URI
`https://oauth-openshift.<apps_domain>/oauth2callback/<idp_name>`, where
`idp_name` is `openshift_oidc_auth.openshift_oidc_idp_name` (default
`Keycloak`). OpenShift oauth-server redirects to that path with no extra
segment; a Keycloak trailing `/*` does not match it. Preflight and overlay
register that exact URI on managed OpenShift clients. When the OpenShift
Keycloak client is externally managed (`create_client: false`), this role
still configures the cluster OAuth identity provider but does **not**
change redirect URIs on the existing Keycloak client. Register the exact
callback URI on the external client before login will succeed. Overlay
writes it as `openshift_oidc_auth.openshift_oauth_redirect_uri`.

When `rhbk_hostname` and `rhbk_realm` are set (RHBK is in the run), this role
uses those values and ignores leftover `ocp_oidc_auth_rhbk_hostname` /
`ocp_oidc_auth_rhbk_realm` overrides from an earlier generate. That keeps
OpenShift OAuth on the same Keycloak the RHBK Client job used. Without RHBK
vars, the role uses its own `ocp_oidc_auth_rhbk_*` connection settings.

The play prints the effective Keycloak hostname, realm, and client ID before
it contacts Keycloak. Missing hostname, realm, admin credentials, or client ID
stop the play at that point.

The role reads the client secret of a Keycloak client that **already exists**,
using the Keycloak admin credentials. It never creates, updates or deletes a
Keycloak client or realm. When the secret cannot be read the play stops, before
anything is written to OpenShift, with one of these messages:

| Situation | Message starts with |
|----------|---------------------|
| Wrong admin user/password | `Cannot read Keycloak client '<id>': admin login to <url> ... failed` |
| Keycloak certificate not trusted (verification is on) | `Keycloak TLS certificate verification failed` |
| Unrecognized `ocp_rhbk_verify_ssl` (`garbage`, `tru`, `flase`, `2`, ...) | `ocp_rhbk_verify_ssl has the value '...', which is not recognized` |
| `ocp_oidc_auth_ca_pem` is set but is not a PEM certificate | `ocp_oidc_auth_ca_pem is set but is not a PEM certificate` |
| Keycloak realm does not exist | `Keycloak realm '<realm>' does not exist` |
| Admin account may not list clients in the realm | `Keycloak did not allow user '<user>' to list clients in realm '<realm>'` |
| Client ID not in the realm | `Keycloak client '<id>' not found in realm '<realm>'` |
| Account may not read the client secret | `Keycloak did not allow user '<user>' to read the secret of client` |
| Client is public or has no secret | `Failed to retrieve Keycloak client secret for client_id=<id>` |
| OpenShift console `Could not create user` after Keycloak login | OpenShift `mappingMethod` is `claim` and that username already exists (htpasswd `admin`). Use `add`. |

Messages never contain passwords, tokens or secrets.

### Keycloak TLS verification

Verification of the Keycloak certificate is **on by default**, for Keycloak
installed by ADO and for an existing (external) Keycloak. A private or internal
CA is supported without turning verification off; verification and trust are
separate:

- *Verification* is on unless `ocp_rhbk_verify_ssl` is an explicit `false` /
  `no` / `off` / `0`. An existing configuration with that explicit value keeps
  working unchanged. Unrecognized values (`garbage`, `tru`, `flase`, `2`, ...)
  stop the play before any Keycloak request; Ansible's `bool` filter is never
  used on the raw value, because it would treat those as false. Keycloak HTTPS
  calls receive `validate_certs: true` or `false` (not Jinja `True` / `False`).
- *Trust* is discovered **before** admin / client-secret API calls, then reused
  for the OpenShift oauth-server CA ConfigMap. Order:
  1. `ocp_oidc_auth_ca_pem` when set (must be PEM)
  2. `idm.ca_bundle_pem` / `idm_ca_bundle_pem` (IdM ACME / lab IdM)
  3. Keycloak TLS Secret `ca.crt`, else intermediates from `tls.crt` (leaf dropped)
  4. cert-manager Issuer / ClusterIssuer ACME `caBundle`
  5. `openshift-config-managed/default-ingress-cert` (last resort)
  6. Empty → process trust store (public CAs / EE image)

The discovered PEM is written to a temporary `0600` file for the run and
removed afterwards. It is passed as `ca_path` to REST calls and as
`SSL_CERT_FILE` to `keycloak_clientsecret_info` (no CA module option). A
leaf-only `tls.crt` is never used as a trust anchor.

If the certificate is still not trusted the play stops with
`Keycloak TLS certificate verification failed` (includes the trust source)
before anything is written to OpenShift. It does not retry with verification
off. For production, keep verification on and fix the CA chain
(`idm_ca_bundle_pem`, Secret `ca.crt`, or `ocp_oidc_auth_ca_pem`).
## 🚀 Role Usage

```yaml
- name: ADO | Configure OpenShift OAuth with RHBK
  hosts: localhost
  gather_facts: false
  vars:
    component: rhbk
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks:
    - name: Resolve vars for component from framework defaults + env overrides
      ansible.builtin.include_role:
        name: infra.automation_development_office.bootstrap_resolve_component
  roles:
    - role: infra.automation_development_office.ocp_oidc_auth
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Assert required OIDC inputs are set
- Build Keycloak URLs
- Show the effective Keycloak target
- Discover Keycloak TLS trust bundle before API calls
- Try to get Keycloak client secret via module
- Extract Keycloak client secret from module result

```bash
cd roles/ocp_oidc_auth
molecule test
```

## 📁 Role Structure

```text
roles/ocp_oidc_auth/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
    main.yml
    resolve_keycloak_trust.yml
  tests/
  vars/
```
