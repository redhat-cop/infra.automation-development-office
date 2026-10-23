# Role: infra.automation_development_office.rhel_sat_reg

Rhel Sat Reg automation role. Primary tasks include: Gathering facts; Fail if OS version earlier than 8 is detected (Out of Support); Unregister from Satellite via subscription-manager.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `rhel_sat_reg_org_admin_account` | Satellite API username. Defaults to `satellite_config_username` / vault service account. |
| `rhel_sat_reg_org_admin_account_password` | Satellite API password. Defaults to `satellite_config_password` / vault service account password. |
| `rhel_sat_reg_activation_key_name` | Client activation key used to register the host. Defaults to `satellite_activation_key`. |
| `rhel_sat_reg_satellite_org_name` | Satellite organization name. Defaults to `satellite_config_organization`. |
| `rhel_sat_reg_satellite_host` | Satellite server URL. Defaults to `satellite_config_server_url`. |
| `rhel_sat_reg_validate_certs` | Validation or TLS verification setting used by this role. |
| `rhel_sat_reg_insights_enabled` | Role input variable used to configure automation behavior. |
| `rhel_sat_reg_update_packages` | Role input variable used to configure automation behavior. |
| `rhel_sat_reg_insecure` | Role input variable used to configure automation behavior. |
| `rhel_sat_reg_action` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: ADO | Register host to Satellite
  hosts: all
  gather_facts: true
  roles:
    - role: infra.automation_development_office.rhel_sat_reg
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Gathering facts
- Fail if OS version earlier than 8 is detected (Out of Support)
- Unregister from Satellite via subscription-manager
- Clean local subscription-manager configs

```bash
cd roles/rhel_sat_reg
molecule test
```

## 📁 Role Structure

```text
roles/rhel_sat_reg/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
