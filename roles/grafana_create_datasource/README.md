# Role: infra.ado.grafana_create_datasource

Creates Grafana Prometheus datasources via the Grafana HTTP API
(`community.grafana.grafana_datasource`), after ensuring an OpenShift
ServiceAccount token Secret (or using an explicit remote bearer token).
Also imports datasource JSON from optional `grafana_datasource_sources`
(git or path), same pattern as dashboard folders.

## Role Author

Automation Development Office.

## ✅ Role Requirements

- Kubernetes/OpenShift API access when discovering local Prometheus Routes /
  creating SA tokens (not required when `prometheus_url` + `bearer_token` are
  set, or when only importing JSON files).
- `kubernetes.core` and `community.grafana` collections (structured Prometheus DS).
- Grafana admin credentials or `grafana_api_key`.

## 📦 Role Variables

| Variable | Default | Description |
| --- | --- | --- |
| `grafana_datasources` | `[]` | List of Prometheus datasource definitions. |
| `grafana_datasource_sources` | `[]` | Git/path sources of datasource `.json` / `.json.j2` files. |
| `grafana_datasource` | `Openshift-Prod` | Legacy single datasource name when lists are empty. |
| `grafana_hostname` | `""` | Grafana hostname (no scheme). |
| `grafana_admin_user` / `grafana_admin_password` | admin / `""` | Grafana basic auth. |
| `grafana_api_key` | `""` | Optional Grafana API bearer token. |

### `grafana_datasources` item fields

| Field | Description |
| --- | --- |
| `name` | Grafana datasource name (`Openshift-Prod`, `Openshift-Dev`, …). |
| `prometheus_url` | Optional absolute Prometheus URL (skips Route discovery). |
| `bearer_token` | Optional bearer token (skips SA token Secret). |
| `bearer_token_secret` | Optional `{name, namespace, key}` to read the token from a Kubernetes Secret. |
| `prometheus_route_name` / `prometheus_route_namespace` | Route overrides (default `thanos-querier` / `openshift-monitoring`). |

### `grafana_datasource_sources` item fields

| Field | Description |
| --- | --- |
| `name` | Label used for the clone workspace. |
| `source_type` | `git` or `path`. |
| `source` | Git URL or local/repo-relative path. |
| `datasources_path` | Subdirectory containing `.json` / `.json.j2` (default `datasources`). |
| `version` | Optional git ref (default `HEAD`). |

## 🚀 Role Usage

```yaml
- hosts: localhost
  roles:
    - role: infra.ado.grafana_create_datasource
      vars:
        grafana_hostname: grafana.apps.example.com
        grafana_admin_user: admin
        grafana_admin_password: "{{ vault_grafana_admin_password }}"
        grafana_datasources:
          - name: Openshift-Prod
            prometheus_route_name: thanos-querier
        grafana_datasource_sources:
          - name: team-ds
            source_type: git
            source: https://gitlab.example.com/project/datasources.git
            datasources_path: datasources
```

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via Contoller JT
`ado-grafana-deploy-datasource-bootstrap` or the Grafana deploy workflow.

## 📁 Role Structure

```text
grafana_create_datasource/
├── defaults/main.yml
├── tasks/main.yml
├── tasks/grafana-manage-datasource.yml
├── tasks/collect-datasource-files.yml
├── tasks/import-datasource-file.yml
└── README.md
```
