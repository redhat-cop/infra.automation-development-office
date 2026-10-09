# Role: infra.ado.ocp_quay

Install or remove Red Hat Quay on OpenShift (namespace, Postgres, registry, route).
Registry blobs default to a local PVC. Set ``ocp_quay_storage_backend=minio`` to
store blobs on an already-installed MinIO (S3-compatible RadosGWStorage). This
role does not install MinIO.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | `present` or `absent`. |
| `name_space` | Quay namespace (default `quay-enterprise`). |
| `ocp_quay_hostname` | Route host. |
| `ocp_quay_admin_user` | Database admin username. Default `quayadmin`. Created with `POST /api/v1/user/initialize` after Quay is up (not from `config.yaml`). |
| `ocp_quay_admin_password` | Database admin password from the Quay tab (`vault_ocp_quay_admin_password`). Reused on reruns; existing user password is reset to this value. |
| `ocp_quay_image` | Quay container image. Default `registry.redhat.io/quay/quay-rhel8:v3.15.4` (not quay.io). |
| `ocp_quay_redis_image` | Redis sidecar. Default `registry.redhat.io/rhel9/redis-6:latest` (not docker.io). |
| `storage` | StorageClass for Postgres and, when not using MinIO, the registry PVC. |
| `ocp_quay_storage_backend` | `local` (PVC LocalStorage) or `minio` (S3-compatible RadosGWStorage). |
| `ocp_quay_s3_hostname` | MinIO API host. Empty inherits `minio.<namespace>.svc` from MinIO vars. |
| `ocp_quay_s3_port` | MinIO API port. Empty inherits `minio_api_port` or `9000`. |
| `ocp_quay_s3_bucket` | Bucket created on MinIO (default `quay`). |
| `ocp_quay_s3_access_key` / `ocp_quay_s3_secret_key` | MinIO root credentials. Empty inherits `minio_root_user` / `minio_root_password` from `vars_minio.yml` / `vault_minio.yml` when those files exist. |
| `ocp_quay_s3_minio_namespace` | MinIO namespace. Empty inherits `minio_namespace` or `minio`. |
| `ocp_quay_minio_mc_image` | Image for the in-cluster bucket Job. Default `registry.redhat.io/ubi9/python-311:latest` (not `quay.io/minio/mc`). |
| `quay_oidc_enabled` | Enable Keycloak OIDC after install. |

## 🚀 Role Usage

```yaml
- name: Run ocp_quay
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_quay
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Delete Quay namespace
- Create Quay Namespace
- Create PVC for Quay storage (skipped when `ocp_quay_storage_backend=minio`)
- Create the Quay bucket on MinIO when that backend is selected
- Set Quay config
- Create or reset the Database admin via ``/api/v1/user/initialize``

```bash
cd roles/ocp_quay
molecule test
```

## 📁 Role Structure

```text
roles/ocp_quay/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```

OIDC issuer resolution accepts an omitted `ocp_quay_oidc_issuer_url` and derives the issuer from the configured RHBK host and realm.
