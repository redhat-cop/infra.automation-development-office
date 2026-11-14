# Role: infra.automation_development_office.ocp_minio

Deploy **MinIO** object storage on OpenShift (Deployment, PVC, Service, API + console
Routes) with optional **Keycloak OIDC** for the web console.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible 2.16+
- Collection: `kubernetes.core`
- OpenShift cluster credentials via `K8S_AUTH_*` / kubeconfig
- For OIDC: RHBK/Keycloak reachable from the cluster (lab: realm `Dev` or `rhlab`)

```yaml
collections:
  - name: kubernetes.core
  - name: community.general   # Keycloak client create (optional OIDC path)
```

## 📦 Role Variables

See `defaults/main.yml`. Common overrides:

| Variable | Description |
|----------|-------------|
| `state` | `present` or `absent` |
| `name_space` | Target namespace |
| `storage` / `storage_class` | PVC StorageClass |
| `minio_storage_size` | PVC size (default `20Gi`) |
| `minio_root_user` / `minio_root_password` | S3 root credentials (Secret `minio-creds`) |
| `minio_console_hostname` / `minio_api_hostname` | Route hosts |
| `minio_container_name` | Container name to patch for OIDC (default `minio`) |
| `minio_oidc_enabled` | Enable console OpenID (also `oidc.enabled` from registry) |
| `minio_oidc_client_id` | Keycloak client id |
| `minio_oidc_client_secret` | Leave empty to fetch after client create |
| `minio_keycloak_realm` | Realm name (lab often `rhlab` / `Dev`) |
| `minio_keycloak_hostname` | Existing Keycloak host when RHBK is not in the run (Preflight `component_config.minio.keycloak_hostname`) |
| `minio_keycloak_admin_user` / `minio_keycloak_admin_password` | Admin API credentials for client create/secret fetch without selecting RHBK |
| `minio_oidc_policy_value` | Token claim value for MinIO policy (default `consoleAdmin`) |
| `minio_oidc_create_keycloak_client` | Create/update the Keycloak client. Default `true`. A matching `clients[].create_client: false` row wins and disables every Keycloak mutation. |
| `minio_oidc_create_policy_mapper` | Add the MinIO policy claim mapper when ADO manages the client. Default `true`. Ignored when the client is unmanaged. |

When RHBK is selected in Preflight, hostname/realm/admin credentials are
inherited from the RHBK component. When RHBK is not selected, set the MinIO
Existing Keycloak fields; selecting RHBK is not required. This role still
does not deploy or reconfigure the Keycloak server itself.

When OIDC is enabled and ADO manages the client, this role is the only
provisioner: it creates/updates the Keycloak client, adds the policy claim
mapper, and stores OpenID env vars in Secret `minio-oidc`. Overlay does not
put that client id in `rhbk_clients`, so `ADO | Deploy RHBK Client` cannot
double-create it.

When the matching Keycloak row has `create_client: false`, ADO does not
create, update, or add mappers to that client. Application OIDC (issuer,
client id, secret fetch, MinIO env) still runs. Configure the existing
client in Keycloak with an OIDC hardcoded-claim mapper:

- claim name: `policy` (or `minio_oidc_claim_name`)
- claim value: `consoleAdmin` (or `minio_oidc_policy_value`)
- include the claim on the ID token, access token, and userinfo

Missing `create_client` still means managed.

OIDC patches the **live** MinIO Deployment (full object) so `envFrom` gains
Secret `minio-oidc` without replacing the `containers` array. Do not use JSON
merge with a partial container definition for this step.

## 🚀 Role Usage

```yaml
---
- name: Deploy MinIO to OpenShift
  hosts: localhost
  gather_facts: false
  environment:
    K8S_AUTH_HOST: "{{ host }}"
    K8S_AUTH_API_KEY: "{{ token }}"
    K8S_AUTH_VERIFY_SSL: "no"
  roles:
    - role: infra.automation_development_office.ocp_namespace
    - role: infra.automation_development_office.ocp_minio
      vars:
        name_space: minio
        apps_domain: ocp-dev.dev.rhlab
        minio_console_hostname: minio-console-minio.apps.ocp-dev.dev.rhlab
        minio_api_hostname: minio-api-minio.apps.ocp-dev.dev.rhlab
        minio_oidc_enabled: true
        minio_oidc_client_id: minio
        minio_keycloak_realm: Dev
        keycloak_hostname: keycloak.apps.ocp-dev.dev.rhlab
```

Contoller / bootstrap:

- Playbook: `bootstrap_generate_playbook_repo/files/playbooks/minio/ado-deploy-and-configure-bootstrap.yml`
- JT seeds: `ado-minio-deploy-and-configure-bootstrap`, `ado-minio-deploy-oidc-bootstrap`
- Component registry key: `minio` in `bootstrap_resolve_component`
- Preflight UI: OpenShift app **MinIO**

Set `state: absent` to remove workloads. PVC is kept unless `minio_delete_pvc: true`.

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via OpenShift workflow
MinIO deploy / OIDC JTs after bootstrap.

## 📁 Role Structure

```text
roles/ocp_minio/
  README.md
  defaults/main.yml
  meta/main.yml
  files/
    minio_oidc_deployment_patch.py
  tasks/
    main.yml
    install-minio.yml
    delete-minio.yml
    configure-keycloak-oidc.yml
    configure-minio-oidc.yml
```

Service manifests render numeric port values as YAML integers, including when Ansible uses non-native templating.
