# Role: infra.ado.ocp_zabbix

Deploy a Zabbix monitoring stack on OpenShift (dedicated PostgreSQL, Zabbix
server, and web UI) with persistent storage and an OpenShift Route.

Existing MariaDB installs are left on MariaDB unless you set
`zabbix_database_type=postgres` and `zabbix_database_force=true`.

## Role Author

- Chad Elliott
- Automation Development Office

## ✅ Role Requirements

- Red Hat OpenShift 4.x cluster with cluster-admin access
- `kubernetes.core` collection installed
- Pull access to PostgreSQL (or MariaDB) and Zabbix container images
- A StorageClass when provisioning in-cluster PostgreSQL

## 📦 Role Variables

| Variable | Description | Required | Default |
| --- | --- | --- | --- |
| `state` | `present` to install or `absent` to remove Zabbix. | ❌ | `present` |
| `zabbix_hostname` | Route hostname for the Zabbix web UI. | ✅ | `""` |
| `zabbix_storage_size` | PVC size for Zabbix data. | ❌ | `20Gi` |
| `zabbix_database_type` | `postgres` (default) or `mysql` / `mariadb`. | ❌ | `postgres` |
| `zabbix_database_provision` | Provision ADO-managed PostgreSQL when type is `postgres`. | ❌ | `true` |
| `zabbix_postgres_image` | PostgreSQL container image. | ❌ | `registry.redhat.io/rhel9/postgresql-15:latest` |
| `zabbix_postgres_storage_size` | PVC size for dedicated PostgreSQL. | ❌ | `10Gi` |
| `zabbix_postgres_storage_class` | StorageClass for dedicated PostgreSQL. Falls back to `storage`. | ❌ | `""` |
| `zabbix_postgres_host` | External PostgreSQL host when provision is `false`. | ❌ | `""` |
| `zabbix_mariadb_image` | MariaDB container image (mysql path). | ❌ | `registry.redhat.io/rhel9/mariadb-105:latest` |
| `zabbix_server_image` | Zabbix server container image. | ❌ | `zabbix/zabbix-server-pgsql:ubuntu-7.0-latest` |
| `zabbix_web_image` | Zabbix web UI container image. | ❌ | `zabbix/zabbix-web-nginx-pgsql:ubuntu-7.0-latest` |
| `zabbix_db_user` | Zabbix database user. | ❌ | `zabbix` |
| `zabbix_db_name` | Zabbix database name. | ❌ | `zabbix` |
| `zabbix_db_root_password` | MariaDB root password (mysql path). | ❌ | set in defaults |
| `zabbix_db_password` | Zabbix database user password. | ❌ | set in defaults |

## 🚀 Role Usage

```yaml
- name: Deploy Zabbix on OpenShift
  hosts: localhost
  gather_facts: false
  vars:
    zabbix_hostname: zabbix.apps.example.com
    storage_class: ocs-storagecluster-ceph-rbd
    zabbix_db_password: "{{ vault_zabbix_db_password }}"
  roles:
    - role: infra.ado.ocp_zabbix
```

## 🧪 Role Molecule Testing

No dedicated Molecule scenario yet. Validate on a lab OpenShift cluster.

## 📁 Role Structure

```text
ocp_zabbix/
├── defaults/main.yml
├── meta/main.yml
├── tasks/
│   ├── configure-admin-password.yml
│   ├── configure-sso.yml
│   ├── install-zabbix.yml
│   ├── main.yml
│   └── provision-zabbix-postgres.yml
└── templates/
    ├── db-init-job.yml.j2
    ├── mariadb-pvc.yml.j2
    ├── mariadb.yml.j2
    ├── zabbix-server.yml.j2
    └── zabbix-web.yml.j2
```
