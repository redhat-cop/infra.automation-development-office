# Role: infra.ado.grafana_install

Deploy Grafana on OpenShift using the Grafana Operator, including persistent storage,
admin credentials, an optional Keycloak OIDC integration, and an OpenShift Route.
Optionally use PostgreSQL (`grafana_database_type: postgres`) instead of the default
embedded SQLite — ADO can provision an in-cluster PostgreSQL 15 Deployment or point
at an external database. When `state: absent`, the role removes the Grafana custom
resource, route, and any ADO-managed PostgreSQL resources.

## Role Author

- Chad Elliott
- Automation Development Office

## ✅ Role Requirements

- Red Hat OpenShift 4.x cluster with cluster-admin access
- Grafana Operator (`grafana-operator`) installed in the target namespace
- `kubernetes.core` collection installed
- Namespace, OperatorGroup, and Subscription for the Grafana Operator prepared before
  this role runs when installing from scratch

## 📦 Role Variables

| Variable | Description | Required | Default |
| --- | --- | --- | --- |
| `name_space` | Target OpenShift namespace where Grafana is deployed. | ✅ | — |
| `state` | `present` to install or `absent` to uninstall Grafana. | ❌ | `present` |
| `grafana_install_hostname` | Hostname used for the Grafana Route and server config. | ✅ | — |
| `grafana_install_admin_user` | Grafana admin username. | ✅ | — |
| `grafana_install_admin_password` | Grafana admin password. | ✅ | — |
| `storage_size` | PVC size for Grafana persistence. | ✅ | — |
| `storage_class` | Storage class for the Grafana PVC. | ✅ | — |
| `grafana_database_type` | `sqlite` (default) or `postgres`. | ❌ | `sqlite` |
| `grafana_database_provision` | When postgres: create in-cluster PostgreSQL (default `true`). Set `false` for external DB. | ❌ | `true` |
| `grafana_postgres_storage_class` | Storage class for ADO-managed PostgreSQL PVC (falls back to `storage_class`). | ❌ | — |
| `grafana_postgres_storage_size` | PostgreSQL PVC size. | ❌ | `5Gi` |
| `grafana_postgres_image` | PostgreSQL container image. | ❌ | `registry.redhat.io/rhel9/postgresql-15:latest` |
| `grafana_postgres_database` / `grafana_postgres_user` | DB name and user. | ❌ | `grafana` |
| `grafana_postgres_password` | Password (generated into Secret when empty on provision). Required for external. | ❌ | generated |
| `grafana_postgres_host` | External host:port when `grafana_database_provision=false`. | ❌ | — |
| `grafana_postgres_ssl_mode` | Grafana `database.ssl_mode`. | ❌ | `disable` |
| `grafana_install_validate_certs` | Validate TLS when checking `/api/health`. | ❌ | `false` |
| `grafana_install_route_name` | OpenShift Route name for Grafana. | ❌ | `grafana` |
| `grafana_install_route_backend_svc` | Backend service name for the Route. | ❌ | `grafana-service` |
| `grafana_install_route_tls_termination` | Route TLS termination mode. | ❌ | `edge` |
| `route_insecure_edge_policy` | Route `insecureEdgeTerminationPolicy` value. | ❌ | `Redirect` |
| `oidc` | Optional Keycloak OIDC settings (`enabled`, `client_id`, `role_map`, etc.). | ❌ | — |
| `grafana_install_scope` | `install` (operator+CR), `oidc`, or `email` configure-only patch. | ❌ | `install` |
| `grafana_install_include_oidc` | Apply OIDC during install scope (usually false; use OIDC JT). | ❌ | `oidc.enabled` |
| `grafana_install_include_email` | Apply SMTP during install scope (usually false; use Email JT). | ❌ | `grafana_email.enabled` |
| `grafana_install_bearer_token` | Output fact: Prometheus bearer token set by the role. | ❌ | set by role |

### Auth via environment

Set kube auth via environment before running Molecule or playbooks:

```bash
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="..."
export K8S_AUTH_VERIFY_SSL="no"
```

## 🚀 Role Usage

```yaml
- name: Deploy Grafana using Operator
  hosts: localhost
  gather_facts: false
  vars:
    name_space: grafana
    grafana_install_hostname: grafana.apps.example.com
    grafana_install_admin_user: admin
    grafana_install_admin_password: supersecret
    storage_size: 5Gi
    storage_class: synology-iscsi-storage
    # Optional PostgreSQL (default is sqlite):
    # grafana_database_type: postgres
    # grafana_database_provision: true
    # grafana_postgres_storage_class: synology-iscsi-storage
    state: present
  roles:
    - role: infra.ado.grafana_install

- name: Delete Grafana using Operator
  hosts: localhost
  gather_facts: false
  vars:
    name_space: grafana
    state: absent
  roles:
    - role: infra.ado.grafana_install
```

## 🧪 Role Molecule Testing

This role uses an extension-level integration scenario:

- `extensions/molecule/integration_grafana_install/molecule.yml`

Shared playbooks are located at:

- `extensions/molecule/utils/playbooks/grafana_install_prepare.yml`
- `extensions/molecule/utils/playbooks/grafana_install_converge.yml`
- `extensions/molecule/utils/playbooks/grafana_install_verify.yml`
- `extensions/molecule/utils/playbooks/grafana_install_destroy.yml`

Run from `extensions/molecule`:

```bash
molecule test -s integration_grafana_install
```

Converge is mock-safe by default for CI. Set `GRAFANA_INSTALL_ENABLE_LIVE_CHECKS=true`
and export `K8S_AUTH_*` plus Grafana variables for cluster integration.

A legacy role-local scenario remains at `roles/grafana_install/molecule/default` for
manual OpenShift testing with dependent `ado.openshift.*` roles.

## 📁 Role Structure

```text
grafana_install/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   ├── main.yml
│   ├── install-grafana-operator.yml
│   ├── provision-grafana-postgres.yml
│   ├── resolve-external-postgres.yml
│   └── delete-grafana-operator.yml
├── tests/
│   ├── inventory
│   └── test.yml
└── vars/
    └── main.yml
```
