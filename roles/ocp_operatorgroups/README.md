# Role: infra.ado.ocp_operatorgroups

Ocp Operatorgroups automation role. Primary tasks include: Derive operator namespace and openshift_tools_operator_groups name; Guard — require name_space when not in AllNamespaces mode; Manage openshift_tools_operator_groups with module defaults.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | `present` (default) or `absent` |
| `name_space` | Namespace that owns the OperatorGroup |
| `operatorgroup` | OperatorGroup metadata.name (DNS-1123) |
| `ocp_operatorgroups_delete_wait` | Wait for OG delete API call (default `true`) |
| `ocp_operatorgroups_delete_wait_timeout` | Seconds for delete wait (default `60`) |
| `ocp_operatorgroups_delete_confirm_retries` | Retries confirming OG gone (default `12`) |
| `ocp_operatorgroups_delete_confirm_delay` | Delay between confirm retries (default `5`) |

## 🚀 Role Usage

```yaml
- name: Run ocp_operatorgroups
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_operatorgroups
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Derive operator namespace and openshift_tools_operator_groups name
- Guard — require name_space when not in AllNamespaces mode
- Manage openshift_tools_operator_groups with module defaults
- Delete OperatorGroup on ``state=absent`` (does not require namespace still present)
- Wait/confirm OperatorGroup is gone before asserting

```bash
cd roles/ocp_operatorgroups
molecule test
```

## 📁 Role Structure

```text
roles/ocp_operatorgroups/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
