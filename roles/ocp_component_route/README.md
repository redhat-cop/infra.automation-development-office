# Role: infra.automation_development_office.ocp_component_route

Ocp Component Route automation role. Primary tasks include: Validate required framework vars; Resolve component hostname var names; Resolve primary route host from flattened vars.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_component_route_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: ADO | Deploy and Configure Grafana and Grafana dashboards
  hosts: localhost
  gather_facts: false
  vars:
    component: grafana
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks:
    - name: ADO | Resolve vars for component from framework defaults + env overrides
      ansible.builtin.include_role:
        name: infra.automation_development_office.bootstrap_resolve_component
  roles:
    - role: infra.automation_development_office.ocp_component_route
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Validate required framework vars
- Resolve component hostname var names
- Resolve primary route host from flattened vars
- Resolve alt route host (only if app_domain_alt is set)

```bash
cd roles/ocp_component_route
molecule test
```

## 📁 Role Structure

```text
roles/ocp_component_route/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
