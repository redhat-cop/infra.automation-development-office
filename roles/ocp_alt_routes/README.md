# Role: infra.automation_development_office.ocp_alt_routes

Ocp Alt Routes automation role. Primary tasks include: Ensure_alt_routes_from_list Normalize candidates input; Ensure_alt_routes_from_list Set defaults; Ensure_alt_routes_from_list Validate required inputs.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_alt_routes_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_alt_routes
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_alt_routes
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Ensure_alt_routes_from_list Normalize candidates input
- Ensure_alt_routes_from_list Set defaults
- Ensure_alt_routes_from_list Validate required inputs
- Ensure_alt_routes_from_list Debug first candidate shape

```bash
cd roles/ocp_alt_routes
molecule test
```

## 📁 Role Structure

```text
roles/ocp_alt_routes/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
