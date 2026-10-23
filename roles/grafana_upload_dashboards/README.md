# Role: infra.automation_development_office.grafana_upload_dashboards

Grafana Upload Dashboards automation role. Primary tasks include: Render dashboard templates to /tmp; Replace datasource with Openshift in rendered JSON; Import Grafana dashboard.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `grafana_upload_dashboards_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run grafana_upload_dashboards
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.grafana_upload_dashboards
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Render dashboard templates to /tmp
- Replace datasource with Openshift in rendered JSON
- Import Grafana dashboard
- Setup upload dashboards

```bash
cd roles/grafana_upload_dashboards
molecule test
```

## 📁 Role Structure

```text
roles/grafana_upload_dashboards/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
