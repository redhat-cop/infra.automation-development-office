# Role: infra.ado.keycloak_login_events_exporter

Poll the Keycloak/RHBK user-event store and publish Prometheus gauges for
successful `LOGIN` and failed `LOGIN_ERROR` events, including username. Native
`keycloak_user_events_total` does not include username. These are gauges of the
current Admin event window, not persistent counters.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Reachable Keycloak/RHBK admin API and OpenShift credentials (`host`/`token`)
- Realm user events enabled (`eventsEnabled`) so the exporter has history to read

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `keycloak_login_events_exporter_enabled` | When false, the role exits without changing the cluster. Default `true`. |
| `keycloak_login_events_keycloak_url` | Keycloak base URL. Inherits `rhbk_url` when unset. |
| `keycloak_login_events_admin_user` | Admin user for `admin-cli`. Inherits `rhbk_admin_user`. |
| `keycloak_login_events_admin_password` | Admin password. Inherits `rhbk_admin_password`. |
| `keycloak_login_events_realms` | Comma-separated realms to poll. Inherits `rhbk_realm`. |
| `keycloak_login_events_token_realm` | Realm used to obtain the admin token. Default `master`. |
| `keycloak_login_events_exporter_namespace` | Namespace for Deployment/ServiceMonitor. Default `grafana`. |
| `keycloak_login_events_exporter_image` | Exporter image. Default `registry.redhat.io/ubi9/python-311:latest`. |
| `keycloak_login_events_enable_realm_store` | When true, enable `LOGIN` / `LOGIN_ERROR` on each realm. Default `true`. |

## 🚀 Role Usage

```yaml
- name: Run keycloak_login_events_exporter
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.keycloak_login_events_exporter
```

Day-2 refresh (does not reinstall RHBK):

```bash
ansible-playbook playbooks/rhbk/ado-rhbk-login-events-exporter.yml
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from `extensions/molecule`. This scenario runs the
exporter classification unit tests (no cluster).

This role runs tasks such as:

- Obtain a Keycloak admin token
- Enable realm user-event storage for LOGIN and LOGIN_ERROR
- Deploy the exporter ConfigMap, Secret, Deployment, Service, and ServiceMonitor

```bash
cd extensions/molecule
ln -sfn . molecule
molecule test -s keycloak_login_events_exporter
```

## 📁 Role Structure

```text
roles/keycloak_login_events_exporter/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
  files/
```
