# Role: infra.automation_development_office.rhbk_realm

Rhbk Realm automation role. Primary tasks include: Create RHBK realm; Delete RHBK realm; Create or update Keycloak realm.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhbk_realm_verify_ssl` | Validation or TLS verification setting used by this role. |

## 🚀 Role Usage

### Bootstrap Usage

#### ado-manage-realm-bootstrap.yml

```yaml
- name: ADO | Manage RHBK realm
  hosts: localhost
  gather_facts: false
  vars:
    component: rhbk
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  no_log: false
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks:
    - name: ADO | Resolve vars for component from framework defaults + env overrides
      ansible.builtin.include_role:
        name: infra.automation_development_office.bootstrap_resolve_component
  roles:
    - role: infra.automation_development_office.rhbk_realm
```

#### ado-realm-bootstrap.yml

```yaml
- name: ADO | Configure RHBK realm
  hosts: localhost
  gather_facts: false
  vars:
    component: rhbk
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  no_log: false
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks:
    - name: ADO | Resolve vars for component from framework defaults + env overrides
      ansible.builtin.include_role:
        name: infra.automation_development_office.bootstrap_resolve_component
  roles:
    - role: infra.automation_development_office.rhbk_realm
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create RHBK realm
- Delete RHBK realm
- Create or update Keycloak realm
- Login to RHBK and get admin token

```bash
cd roles/rhbk_realm
molecule test
```

## 📁 Role Structure

```text
roles/rhbk_realm/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
