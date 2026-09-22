# Role: infra.ado.ocp_minio

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
| `minio_oidc_enabled` | Enable console OpenID (also `oidc.enabled` from registry) |
| `minio_oidc_client_id` | Keycloak client id |
| `minio_oidc_client_secret` | Leave empty to fetch after client create |
| `minio_keycloak_realm` | Realm name (lab dev often `Dev`) |
| `minio_oidc_policy_value` | Token claim value for MinIO policy (default `consoleAdmin`) |

When OIDC is enabled the role creates/updates a Keycloak client, adds a policy
claim mapper, and stores OpenID env vars in Secret `minio-oidc`.

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
    - role: infra.ado.ocp_namespace
    - role: infra.ado.ocp_minio
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
  tasks/
    main.yml
    install-minio.yml
    delete-minio.yml
    configure-keycloak-oidc.yml
    configure-minio-oidc.yml
```

Service manifests render numeric port values as YAML integers, including when Ansible uses non-native templating.
