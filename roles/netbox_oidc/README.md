# Role: infra.ado.netbox_oidc

Wire NetBox login to Keycloak / Red Hat build of Keycloak (RHBK) OIDC by
updating the existing NetBox ConfigMap (no full Helm redeploy).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Collection: `kubernetes.core`
- OpenShift/Kubernetes credentials via `K8S_AUTH_*` or kubeconfig
- An existing NetBox Helm release (ConfigMap `netbox` in the target namespace)
- A confidential Keycloak client (default id `netbox` in realm `rhlab`) with a
  client secret

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `netbox_oidc_state` | Desired state. Default `present`. |
| `netbox_oidc_namespace` | Namespace of the NetBox release. Default `netbox`. |
| `netbox_oidc_release` | Helm release name (documentation / audit). Default `netbox`. |
| `netbox_oidc_validate_certs` | Verify the Kubernetes API TLS certificate. Default `true`. |
| `netbox_oidc_issuer` | OIDC issuer URL. Default `https://keycloak.apps.ocp.prod.rhlab/realms/rhlab`. |
| `netbox_oidc_client_id` | Keycloak client id. Default `netbox`. |
| `netbox_oidc_client_secret` | Confidential client secret (required when state is `present`). |
| `netbox_oidc_login_required` | When true, NetBox requires login. Default `false`. |
| `netbox_oidc_auto_create_user` | Reserved for future NetBox auto-create mapping. Default `true`. |
| `netbox_oidc_secret_name` | Kubernetes Secret that stores OIDC key/secret. Default `netbox-oidc`. |
| `netbox_oidc_ca_bundle` | Optional PEM CA bundle for Keycloak TLS trust. |
| `netbox_oidc_ca_configmap` | ConfigMap name for the CA bundle. Default `netbox-lab-ca`. |
| `netbox_oidc_verify_ssl` | When false, social-auth skips TLS verify for OIDC discovery. Default `false`. |

## 🚀 Role Usage

### Bootstrap Usage

#### ado-configure-netbox-oidc-bootstrap.yml

```yaml
- name: ADO | Configure NetBox OIDC (Keycloak RHLAB)
  hosts: localhost
  gather_facts: false
  vars:
    netbox_oidc_state: "{{ state | default('present') }}"
    netbox_oidc_issuer: https://keycloak.apps.ocp.prod.rhlab/realms/rhlab
    netbox_oidc_client_id: netbox
    netbox_oidc_client_secret: "{{ vault_netbox_oidc_client_secret }}"
  environment:
    K8S_AUTH_HOST: "{{ host | default(api_host) }}"
    K8S_AUTH_API_KEY: "{{ token }}"
    K8S_AUTH_VERIFY_SSL: "{{ (verify_ssl | bool) | ternary('yes', 'no') }}"
  roles:
    - role: infra.ado.netbox_oidc
```

Create the Keycloak client first (or reuse `infra.ado.rhbk_client`). Then sign
in at the NetBox login page with OpenID Connect.

## 🧪 Role Molecule Testing

No dedicated Molecule scenario. Validate against a lab NetBox namespace and the
existing `rhlab` realm.

```bash
ansible-playbook playbooks/netbox/ado-configure-netbox-oidc-bootstrap.yml \
  -e env=prod \
  --vault-password-file .vault_pass
```

## 📁 Role Structure

```text
roles/netbox_oidc/
  README.md
  defaults/
  meta/
  tasks/
    main.yml
```

This role configures an existing NetBox installation; it does not install NetBox. The namespace defaults to `netbox_namespace`, then `name_space`, then `netbox`; `netbox_oidc_namespace` overrides it. Preflight `component_config.netbox.namespace` is propagated to OIDC. Missing namespaces fail before credential lookup or mutation.
