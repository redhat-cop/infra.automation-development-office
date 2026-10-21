# Role: infra.automation_development_office.ocp_search_dirsrv

Ocp Search Dirsrv automation role. Primary tasks include: Find a running dirsrv pod # noqa; Fail if no dirsrv pods found; Pick first pod name # noqa.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_search_dirsrv_target_namespace` | OpenShift namespace value used by this role. |
| `ocp_search_dirsrv_app_label` | Role input variable used to configure automation behavior. |
| `ocp_search_dirsrv_container_name` | Resource name used by this role. |
| `ocp_search_dirsrv_ldap_port` | Role input variable used to configure automation behavior. |
| `ocp_search_dirsrv_bind_dn` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: ADO | List LDAP users/groups from 389-DS
  hosts: localhost
  gather_facts: false
  vars:
    component: 389ds
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks: null
  roles:
    - role: infra.automation_development_office.ocp_search_dirsrv
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Find a running dirsrv pod # noqa
- Fail if no dirsrv pods found
- Pick first pod name # noqa
- Render search script # noqa

```bash
cd roles/ocp_search_dirsrv
molecule test
```

## 📁 Role Structure

```text
roles/ocp_search_dirsrv/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
