# Role: infra.automation_development_office.install_elastic

Install Elastic automation role. Primary tasks include: ECK Set derived vars; ECK Ensure operator namespace exists; ECK Ensure operand namespace exists (only when creating CR).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `install_elastic_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: ADO | Deploy ECK Operator
  hosts: localhost
  gather_facts: false
  vars:
    component: eck
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
    - role: infra.automation_development_office.install_elastic
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- ECK Set derived vars
- ECK Ensure operator namespace exists
- ECK Ensure operand namespace exists (only when creating CR)
- ECK Install operator (openshift_tools_operator_groups + Subscription)

```bash
cd roles/install_elastic
molecule test
```

## 📁 Role Structure

```text
roles/install_elastic/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
