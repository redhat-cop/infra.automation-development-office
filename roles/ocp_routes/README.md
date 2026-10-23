# Role: infra.automation_development_office.ocp_routes

Ocp Routes automation role. Primary tasks include: Get Routes for single namespace; Print all Route hostnames (single namespace); Get Routes for each namespace in routes list.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_routes_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

### Bootstrap Usage

#### ado-deploy-and-configure-bootstrap.yml

```yaml
- name: ADO | Install {{ component_friendly_name }}
  hosts: localhost
  gather_facts: false
  vars:
    component: cert_manager
    component_friendly_name: Cert Manager
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
    - role: infra.automation_development_office.ocp_routes
```

#### ado-deploy-and-configure-bootstrap.yml

```yaml
- name: ADO | Install GitLab
  hosts: localhost
  gather_facts: false
  vars:
    component: gitlab
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
    - role: infra.automation_development_office.ocp_routes
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Get Routes for single namespace
- Print all Route hostnames (single namespace)
- Get Routes for each namespace in routes list
- Print all Route hostnames (multiple namespaces)

```bash
cd roles/ocp_routes
molecule test
```

## 📁 Role Structure

```text
roles/ocp_routes/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
