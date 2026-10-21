# Role: infra.automation_development_office.rhbk_client

Rhbk Client automation role. Primary tasks include: Create RHBK Client; Delete RHBK client; Assert required inputs are set.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhbk_client_state` | Desired state used by role tasks when supported. |
| `rhbk_default_client_scopes` | Client scope names to attach as defaults after create (e.g. `groups`). |
| `rhbk_attach_default_client_scopes` | When true, attach `rhbk_default_client_scopes` after client create. |

## 🚀 Role Usage

### Bootstrap Usage

#### ado-manage-client-bootstrap.yml

```yaml
- name: ADO | Manage RHBK client
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
    - role: infra.automation_development_office.rhbk_client
```

#### ado-manage-entraid-idp.yml

```yaml
- name: ADO | Manage RHBK Entra ID identity provider
  hosts: localhost
  vars:
    component: rhbk
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  roles:
    - role: infra.automation_development_office.rhbk_client
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create RHBK Client
- Delete RHBK client
- Assert required inputs are set
- Build Keycloak base URL

```bash
cd roles/rhbk_client
molecule test
```

## 📁 Role Structure

```text
roles/rhbk_client/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
