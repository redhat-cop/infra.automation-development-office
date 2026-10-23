# Role: infra.automation_development_office.ocp_ldap_auth

Ocp Ldap Auth automation role. Primary tasks include: Assert ldap_config is present (from vault); Build ocp_ldap_auth_config from ldap_config (vault) + optional overrides; Skip when LDAP auth disabled.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_ldap_auth_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: ADO | Configure OpenShift LDAP Authentication
  hosts: localhost
  gather_facts: false
  vars:
    component: ldap_auth_openshift
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
    - role: infra.automation_development_office.ocp_ldap_auth
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Assert ldap_config is present (from vault)
- Build ocp_ldap_auth_config from ldap_config (vault) + optional overrides
- Skip when LDAP auth disabled
- Assert required LDAP fields

```bash
cd roles/ocp_ldap_auth
molecule test
```

## 📁 Role Structure

```text
roles/ocp_ldap_auth/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
