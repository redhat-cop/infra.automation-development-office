# Role: infra.automation_development_office.ocp_logging

Ocp Logging automation role. Primary tasks include: Create Cluster Forwarder Splunk Secret; Create/Delete Cluster Forwarder; Cluster Logging.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_logging_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_logging
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_logging
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create Cluster Forwarder Splunk Secret
- Create/Delete Cluster Forwarder
- Cluster Logging

```bash
cd roles/ocp_logging
molecule test
```

## 📁 Role Structure

```text
roles/ocp_logging/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
