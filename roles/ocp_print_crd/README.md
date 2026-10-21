# Role: infra.automation_development_office.ocp_print_crd

Ocp Print Crd automation role. Primary tasks include: Print CRD; Assert required input; Discover Subscriptions in {{ name_space }}.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_print_crd_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_print_crd
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_print_crd
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Print CRD
- Assert required input
- Discover Subscriptions in {{ name_space }}
- Fail if no Subscription found

```bash
cd roles/ocp_print_crd
molecule test
```

## 📁 Role Structure

```text
roles/ocp_print_crd/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
