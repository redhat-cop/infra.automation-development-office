# Role: infra.automation_development_office.ocp_oidc_auth

Ocp Oidc Auth automation role. Primary tasks include: Assert required OIDC inputs are set; Build Keycloak URLs; Try to get Keycloak client secret via module.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_oidc_auth_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: ADO | Configure OpenShift OAuth with RHBK
  hosts: localhost
  gather_facts: false
  vars:
    component: rhbk
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks:
    - name: Resolve vars for component from framework defaults + env overrides
      ansible.builtin.include_role:
        name: infra.automation_development_office.bootstrap_resolve_component
  roles:
    - role: infra.automation_development_office.ocp_oidc_auth
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Assert required OIDC inputs are set
- Build Keycloak URLs
- Try to get Keycloak client secret via module
- Extract Keycloak client secret from module result

```bash
cd roles/ocp_oidc_auth
molecule test
```

## 📁 Role Structure

```text
roles/ocp_oidc_auth/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
