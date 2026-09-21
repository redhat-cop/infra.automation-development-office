# Role: infra.ado.grafana_upload_alerts

Uploads Grafana alert rule JSON (``.json`` / ``.json.j2``) from
``grafana_folders`` entries (git or path + ``alerts_path``).

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
| `grafana_folders` | Folder sources; uses ``alerts_path`` (default ``alerts``). |
| `grafana_alerts_enabled` | When false, role ends without uploading. |
| `grafana_api_key` | Optional Bearer token. |
| `grafana_admin_user` / `grafana_admin_password` | Basic auth when API key unset. |

## 🚀 Role Usage

```yaml
- hosts: localhost
  roles:
    - role: infra.ado.grafana_upload_alerts
      vars:
        grafana_hostname: grafana.apps.example.com
        grafana_admin_password: "{{ vault_grafana_admin_password }}"
        grafana_alerts_enabled: true
        grafana_folders:
          - name: Openshift
            source_type: git
            source: https://gitlab.example.com/project/alerts.git
            alerts_path: alerts
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
    └── upload-alert-file.yml
```
