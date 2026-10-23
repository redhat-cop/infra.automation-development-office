# Role: infra.automation_development_office.grafana_upload_alerts

Uploads Grafana alert rule JSON (``.json`` / ``.json.j2``) from
``grafana_alert_folders`` (git or path + ``alerts_path``). When that
list is empty, the role falls back to ``grafana_folders``.

## Role Author

Automation Development Office.

## ✅ Role Requirements

- Grafana reachable over HTTPS.
- ``grafana_api_key`` **or** ``grafana_admin_user`` / ``grafana_admin_password``.
- ``grafana_alerts_enabled: true`` (set by preflight Alerts option / alerts JT).

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `grafana_hostname` | Grafana host (no scheme). |
| `grafana_alert_folders` | Alert folder sources. Default folder is ``Alerts`` at ``alerts/Alerts``. |
| `grafana_folders` | Used only when ``grafana_alert_folders`` is empty. |
| `grafana_alerts_enabled` | When false, role ends without uploading. |
| `grafana_api_key` | Optional Bearer token. |
| `grafana_admin_user` / `grafana_admin_password` | Basic auth when API key unset. |
| `grafana_alert_datasource_names` | Prometheus datasource names, list or comma-separated. Blank uses every Prometheus datasource. |
| `grafana_alert_email_to` | Email addresses for the ADO OpenShift contact point. Blank skips email routing. |
| `grafana_alert_send_test` | When true, post one short-lived test alert per rule type. |

## 🚀 Role Usage

```yaml
- hosts: localhost
  roles:
    - role: infra.automation_development_office.grafana_upload_alerts
      vars:
        grafana_hostname: grafana.apps.example.com
        grafana_admin_password: "{{ vault_grafana_admin_password }}"
        grafana_alerts_enabled: true
        grafana_alert_folders:
          - name: Alerts
            source_type: path
            source: "."
            alerts_path: alerts/Alerts
```

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via Contoller JT
``ado-grafana-deploy-alerts-bootstrap``.

## 📁 Role Structure

```text
grafana_upload_alerts/
├── README.md
├── meta/
└── tasks/
    ├── main.yml
    ├── collect-folder-alerts.yml
    ├── upload-datasource-alerts.yml
    ├── upload-alert-file.yml
    └── configure-alert-email.yml
```
