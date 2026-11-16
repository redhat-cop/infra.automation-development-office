# Role: infra.automation_development_office.bookstack_openshift

Deploy **BookStack** (internal Confluence-style docs) on OpenShift with MariaDB,
PVCs, Secrets, Service, Route, probes, and idempotent updates. Optional RHBK OIDC
is configured via `bookstack_oidc_enabled` or the split `configure-oidc` tag path.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible 2.16+
- Collection: `kubernetes.core`
- OpenShift cluster credentials via `K8S_AUTH_*` / kubeconfig
- Ability to pull container images (or mirrored images for disconnected)

```yaml
collections:
  - name: kubernetes.core
```

Creates namespace `bookstack`, MariaDB + app Deployments, PVCs, Route (TLS edge),
and Secrets for DB credentials and APP_KEY.

## 📦 Role Variables

See `defaults/main.yml`. Common overrides:

| Variable | Description |
|----------|-------------|
| `bookstack_namespace` | Target namespace (default `bookstack`) |
| `bookstack_route_host` | Route hostname |
| `bookstack_storage_class` | PVC StorageClass |
| `bookstack_use_anyuid` | SCC anyuid for MariaDB on NFS (lab default `true`) |
| `bookstack_db_password` / `bookstack_app_key` | Generated once into Secrets when empty |
| `bookstack_oidc_enabled` | Enable RHBK OIDC (also `oidc.enabled` from registry) |
| `bookstack_oidc_client_id` | Keycloak client id |
| `bookstack_oidc_client_secret` | Confidential client secret; fetched from Keycloak when empty |
| `bookstack_oidc_issuer` | OIDC issuer URL (realm) |

Default images: `solidnerd/bookstack:24.12.1` (port 8080), `mariadb:11`.

## 🚀 Role Usage

```yaml
---
- name: Deploy BookStack to OpenShift
  hosts: localhost
  gather_facts: false
  environment:
    K8S_AUTH_HOST: "{{ host }}"
    K8S_AUTH_API_KEY: "{{ token }}"
    K8S_AUTH_VERIFY_SSL: "no"
  roles:
    - role: infra.automation_development_office.bookstack_openshift
      vars:
        bookstack_validate_certs: false
        bookstack_apps_domain: apps.ocp.prod.rhlab
        bookstack_route_host: bookstack.apps.ocp.prod.rhlab
        bookstack_storage_class: synology-nfs-csi
        bookstack_use_anyuid: true
        bookstack_oidc_enabled: true
```

Contoller / bootstrap:

- Playbook: `bootstrap_generate_playbook_repo/files/playbooks/docs/ado-deploy-bookstack-bootstrap.yml`
- OIDC JT: `ado-bookstack-deploy-oidc-bootstrap.jt.yml`
- Component registry key: `bookstack` in `bootstrap_resolve_component`

OIDC secret handling: `bookstack_oidc_client_secret` is used when set. When it is
empty, `ocp_rhbk_client_secrets` reads the Keycloak client secret before the
`bookstack-app` Secret or OIDC environment is applied. That read is allowed when
`create_client` is false (ownership controls Keycloak mutations, not secret
retrieval). The role does not create or update the Keycloak client. An existing
`bookstack-app` `oidc-client-secret` is reused only when `oidc-client-id` in that
Secret matches `bookstack_oidc_client_id`. Changing the client ID does not keep
the previous client's secret. Missing client, denied admin access, a client-ID
mismatch with no Keycloak secret, or an empty confidential-client secret fails
the job; an empty value is not written.

Tags: `bookstack`, `bookstack_namespace`, `bookstack_database`, `bookstack_app`,
`bookstack_route`, `bookstack_oidc`, `bookstack_configure_oidc`.

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via OpenShift workflow
**Deploy BookStack** / **Configure BookStack OIDC** JTs after bootstrap.

## 📁 Role Structure

```text
roles/bookstack_openshift/
  README.md
  defaults/main.yml
  meta/main.yml
  tasks/
    main.yml
    namespace.yml
    database.yml
    bookstack.yml
    route.yml
    admin.yml
    oidc.yml
    resolve-oidc-secret.yml
    configure-oidc.yml
    validate.yml
    remove.yml
```

Upgrade: re-run the role; PVCs and APP_KEY are preserved. Set `state: absent`
to remove Deployments/Services/Route/Secrets (PVCs kept unless
`bookstack_purge_storage: true`).
