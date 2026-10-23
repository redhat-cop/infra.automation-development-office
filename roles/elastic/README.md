# Role: infra.automation_development_office.elastic

Operational checks/actions for Elasticsearch through a state-driven interface.

## Role Author

Automation Development Office.

## ✅ Role Requirements

- Network access from controller to the Elasticsearch API endpoint.
- Optional elevated privileges when managing Elasticsearch service/process state.

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `elastic_state` | Desired action (`start`, `balance`, `stop`, or `status`), default `status`. |
| `elastic_systemd_enabled` | Use systemd for start/stop actions, default `true`. |
| `elastic_systemd_unit` | Systemd unit name, default `elasticsearch`. |
| `elastic_start_cmd` | Custom start command when not using systemd, default empty. |
| `elastic_pid_file` | PID file path for custom mode, default `/var/run/elasticsearch.pid`. |
| `elastic_url` | Elasticsearch base URL, default `http://localhost:9200`. |
| `elastic_user` | Optional basic-auth username. |
| `elastic_pass` | Optional basic-auth password. |
| `elastic_http_timeout` | Timeout budget in seconds for readiness checks, default `60`. |
| `elastic_enable_live_checks` | Optional Molecule live-check toggle, default `false`. |

Supported states:

- `start` starts Elasticsearch and waits for HTTP readiness.
- `balance` asserts cluster health and shard/pending-task stability.
- `stop` stops Elasticsearch and reports post-stop endpoint probe status.
- `status` queries and prints cluster health summary.

Compatibility aliases retained by `tasks/main.yml`:

- `state` -> `elastic_state`
- `es_systemd_enabled` -> `elastic_systemd_enabled`
- `es_systemd_unit` -> `elastic_systemd_unit`
- `es_start_cmd` -> `elastic_start_cmd`
- `es_pid_file` -> `elastic_pid_file`
- `es_url` -> `elastic_url`
- `es_user` -> `elastic_user`
- `es_pass` -> `elastic_pass`
- `es_http_timeout` -> `elastic_http_timeout`

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.elastic
      vars:
        elastic_state: status
        elastic_url: http://localhost:9200
```

## 🧪 Role Molecule Testing

Run from `extensions/molecule`:

```bash
molecule test -s integration_elastic
```

Optional live checks:

```bash
export ELASTIC_ENABLE_LIVE_CHECKS=true
export ELASTIC_URL="http://localhost:9200"
molecule test -s integration_elastic
```

## 📁 Role Structure

```text
elastic/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   ├── main.yml
│   ├── elastic_start.yml
│   ├── elastic_balance_check.yml
│   ├── elastic_stop.yml
│   └── elastic_status_check.yml
└── vars/
    └── main.yml
```
