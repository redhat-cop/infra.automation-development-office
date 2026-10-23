# Role: infra.automation_development_office.ocp_dev_hub

Deploy Red Hat Developer Hub (RHDH) on OpenShift using the RHDH operator,
including Backstage custom resource configuration, optional GitLab catalog
integration, and Keycloak OIDC settings.

## Role Author

- Chad Elliott
- Automation Development Office

## ✅ Role Requirements

- Red Hat OpenShift 4.x cluster with cluster-admin access
- RHDH operator installed in the target namespace
- `kubernetes.core` collection installed
- Keycloak realm and OIDC client when SSO is enabled

## 📦 Role Variables

| Variable | Description | Required | Default |
| --- | --- | --- | --- |
| `state` | `present` to install or `absent` to remove RHDH. | ❌ | `present` |
| `dev_hub_instance_name` | Backstage / RHDH instance name. | ❌ | `chad-lab` |
| `dev_hub_hostname` | Route hostname for Developer Hub. | ✅ | `""` |
| `dev_hub_keycloak_realm` | Keycloak realm for OIDC. | ❌ | `rhlab` |
| `dev_hub_keycloak_client_id` | Keycloak OIDC client ID. | ❌ | `rhdh` |
| `dev_hub_backend_secret` | Backstage backend secret. | ❌ | `changeme-backend-secret` |
| `dev_hub_oidc_client_secret` | Keycloak OIDC client secret. | ❌ | `""` |
| `dev_hub_gitlab_host` | GitLab host for catalog integration. | ❌ | `""` |
| `dev_hub_catalog_url` | Catalog location URL. | ❌ | `""` |
| `dev_hub_gitlab_token` | GitLab token for catalog access. | ❌ | `""` |
| `storage_size` | PVC size for RHDH persistence. | ❌ | `10Gi` |

## 🚀 Role Usage

```yaml
- name: Deploy Red Hat Developer Hub
  hosts: localhost
  gather_facts: false
  vars:
    dev_hub_hostname: devhub.apps.example.com
    dev_hub_oidc_client_secret: "{{ vault_dev_hub_oidc_secret }}"
  roles:
    - role: infra.automation_development_office.ocp_dev_hub
```

## 🧪 Role Molecule Testing

No dedicated Molecule scenario yet. Validate on a lab OpenShift cluster with the
RHDH operator pre-installed.

## 📁 Role Structure

```text
ocp_dev_hub/
├── defaults/main.yml
├── meta/main.yml
├── tasks/
│   ├── main.yml
│   └── install-dev-hub.yml
└── templates/
    ├── app-config.yaml.j2
    └── backstage-cr.yml.j2
```
