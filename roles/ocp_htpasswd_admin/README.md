# Role: infra.ado.ocp_htpasswd_admin

Ocp Htpasswd Admin automation role. Primary tasks include: Build htpasswd content from user list; Create htpasswd Secret; Grant cluster-admin to selected htpasswd users.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `htpasswd_action` | `add` (merge users), `replace` (rewrite secret), or `remove`. |
| `htpasswd_users` | List of `{name, password, role}` entries for the HTPasswd secret. |
| `htpasswd_idp_name` | OAuth identity provider name shown as the OpenShift console login button. Default `htpasswd-admin`. Required for ``state=absent`` (must match the Login button to remove). |
| `htpasswd_secret` | Secret in `openshift-config` holding htpasswd data. Default `{htpasswd_idp_name}-secret`. |
| `htpasswd_mapping_method` | OAuth mapping method (`add` preferred to avoid stale Identity conflicts). |
| `htpasswd_remove_all` | When true with remove action, remove the provider when no users remain. |
| `state` | `present` (create/update) or `absent` (delete the IdP named by `htpasswd_idp_name` and its secret). |

## 🚀 Role Usage

```yaml
- name: ADO | Configure htpass-admin-user
  hosts: localhost
  gather_facts: false
  vars:
    component: htpasswd
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
        name: infra.ado.bootstrap_resolve_component
  roles:
    - infra.ado.ocp_htpasswd_admin
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Build htpasswd content from user list
- Create htpasswd Secret
- Grant cluster-admin to selected htpasswd users
- Get current OAuth config

```bash
cd roles/ocp_htpasswd_admin
molecule test
```

## 📁 Role Structure

```text
roles/ocp_htpasswd_admin/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
