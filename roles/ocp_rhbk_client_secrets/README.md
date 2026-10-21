# Role: infra.automation_development_office.ocp_rhbk_client_secrets

Ocp Rhbk Client Secrets automation role. Primary tasks include: Rhbk_get_client_secrets Snapshot components_env (safe default); Rhbk_get_client_secrets Create temp file for rendered registry; Rhbk_get_client_secrets Render registry file (Jinja evaluated).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_rhbk_client_secrets_client_key` | Sensitive credential value used by this role. |
| `ocp_rhbk_client_secrets_client_id` | Sensitive credential value used by this role. |
| `ocp_rhbk_client_secrets_set_var_name` | Resource name used by this role. |
| `ocp_rhbk_client_secrets_do_not_override_existing` | Sensitive credential value used by this role. |
| `ocp_rhbk_client_secrets_validate_certs` | Sensitive credential value used by this role. |

## 🚀 Role Usage

```yaml
- name: Run ocp_rhbk_client_secrets
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_rhbk_client_secrets
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Rhbk_get_client_secrets Snapshot components_env (safe default)
- Rhbk_get_client_secrets Create temp file for rendered registry
- Rhbk_get_client_secrets Render registry file (Jinja evaluated)
- Rhbk_get_client_secrets Load rendered registry YAML

```bash
cd roles/ocp_rhbk_client_secrets
molecule test
```

## 📁 Role Structure

```text
roles/ocp_rhbk_client_secrets/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
