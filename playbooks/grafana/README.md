# Standalone Grafana content playbooks

Config-only playbooks for an **already installed** Grafana (OpenShift or
RHEL). They do **not** install the operator or RPM.

Copy these into your Contoller project (or vendor the collection and sync
the playbook path), then create Job Templates manually.

| Playbook | Role(s) | Purpose |
| --- | --- | --- |
| `ado-grafana-datasources.yml` | `grafana_create_datasource` | Prometheus DS list and/or JSON from git/path |
| `ado-grafana-folders.yml` | `grafana_manage_folders` | Create folders (incl. General/root) |
| `ado-grafana-dashboards.yml` | `grafana_upload_dashboards` | Upload dashboards from folder sources |
| `ado-grafana-alerts.yml` | `grafana_upload_alerts` | Upload alert JSON from `alerts_path` |
| `ado-grafana-content.yml` | all of the above | One-shot content sync |

## Contoller JT setup (manual)

For each playbook:

1. **Project** - SCM with these files under e.g. `playbooks/grafana/`.
2. **Inventory** - `localhost` (or Contoller "localhost" inventory).
3. **Credentials** - machine cred optional; add OpenShift token cred only if
   datasources should auto-discover thanos-querier / create SA tokens.
4. **Playbook** - path to the file above.
5. **Extra variables / survey** - see below.

Suggested JT names:

- `ADO | Grafana Datasources`
- `ADO | Grafana Folders`
- `ADO | Grafana Dashboards`
- `ADO | Grafana Alerts`

Run order when using separate JTs: **Folders → Datasources → Dashboards → Alerts**.

## Required auth vars

Always set one of:

```yaml
grafana_hostname: grafana.apps.example.com
grafana_admin_user: admin
grafana_admin_password: '***'
# OR
grafana_api_key: 'glsa_***'
```

## Optional: load bootstrap `group_vars`

If the Contoller project is a bootstrap repo and you pass `env: dev` (or
`prod`), the playbooks load:

- `group_vars/all/{{ env }}/infra_config_vars.yml`
- `group_vars/all/{{ env }}/vault_grafana.yml`
- `group_vars/all/{{ env }}/vars_grafana.yml`

Set `grafana_skip_group_vars: true` to force survey/extra_vars only.

## Example extra vars - datasources

```yaml
grafana_hostname: grafana.apps.ocp-dev.dev.rhlab
grafana_admin_user: admin
grafana_admin_password: '***'

grafana_datasources:
  - name: Openshift-Prod
    prometheus_route_name: thanos-querier
  - name: Openshift-Dev
    prometheus_url: https://thanos-querier-openshift-monitoring.apps.ocp-dev.dev.rhlab
    bearer_token: '***'

# Optional: import JSON from git
grafana_datasource_sources:
  - name: team-ds
    source_type: git
    source: https://gitlab.example.com/org/datasource-folder.git
    datasources_path: datasources
```

For remote Prometheus without OpenShift API access, always set
`prometheus_url` + `bearer_token` (do not rely on Route/SA discovery).

## Example extra vars - folders / dashboards / alerts

```yaml
grafana_hostname: grafana.apps.ocp-dev.dev.rhlab
grafana_admin_password: '***'

grafana_folders:
  - name: Openshift
    source_type: git
    source: https://gitlab.example.com/org/dashboards-folder.git
    dashboards_path: dashboards
    alerts_path: alerts
  - name: General
    use_general_folder: true
    source_type: git
    source: https://gitlab.example.com/org/root-dashboards.git
    dashboards_path: dashboards
    alerts_path: alerts
```

- **Folders JT** - creates named folders (skips create for General).
- **Dashboards JT** - uploads from `dashboards_path`.
- **Alerts JT** - uploads from `alerts_path` (forces `grafana_alerts_enabled`).

## CLI smoke test

From a machine with `infra.ado` installed and network to Grafana:

```bash
ansible-playbook playbooks/grafana/ado-grafana-folders.yml \
  -e grafana_hostname=grafana.apps.example.com \
  -e grafana_admin_password='***' \
  -e '{"grafana_folders":[{"name":"Openshift","source_type":"git","source":"https://gitlab.example.com/org/dashboards.git","dashboards_path":"dashboards"}]}'
```

## Collection paths

After `ansible-galaxy collection install` / Hub sync:

`ansible_collections/infra/ado/playbooks/grafana/`

Bootstrap-seeded copies (same roles) also live under the generated repo as
`playbooks/grafana/ado-deploy-*-bootstrap.yml` if you prefer those for SCM.
