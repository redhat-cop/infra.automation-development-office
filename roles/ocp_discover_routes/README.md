# Role: infra.automation_development_office.ocp_discover_routes

Ocp Discover Routes automation role. Primary tasks include: Discover Routes | Gather all routes in cluster; Discover Routes | Start empty candidate list; Discover Routes | Append candidates (primary domain, not already -alt).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_discover_routes_primary_suffix` | Role input variable used to configure automation behavior. |
| `ocp_discover_routes_alt_suffix` | Role input variable used to configure automation behavior. |
| `ocp_discover_routes_filter_primary_suffix` | Role input variable used to configure automation behavior. |
| `ocp_discover_routes_exclude_namespaces` | OpenShift namespace value used by this role. |
| `ocp_discover_routes_alt_exclude_name_regex` | Resource name used by this role. |

## 🚀 Role Usage

```yaml
- name: ADO | Discover alternate routes
  hosts: localhost
  gather_facts: false
  vars:
    component: routes
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
    - role: infra.automation_development_office.ocp_discover_routes
      vars:
        infra.automation_development_office.ocp_discover_routes_route_alt_primary_suffix: '{{ app_domain }}'
        infra.automation_development_office.ocp_discover_routes_route_alt_suffix: '{{ app_domain_alt }}'
        infra.automation_development_office.ocp_discover_routes_route_alt_output_var: route_alt_candidates
        infra.automation_development_office.ocp_discover_routes_route_alt_print: true
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Discover Routes | Gather all routes in cluster
- Discover Routes | Start empty candidate list
- Discover Routes | Append candidates (primary domain, not already -alt)
- Discover Routes | Print summary

```bash
cd roles/ocp_discover_routes
molecule test
```

## 📁 Role Structure

```text
roles/ocp_discover_routes/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
