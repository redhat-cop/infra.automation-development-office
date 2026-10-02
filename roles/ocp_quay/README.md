# Role: infra.ado.ocp_quay

Ocp Quay automation role. Primary tasks include: Delete Quay namespace; Create Quay Namespace; Create PVC for Quay storage.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_quay_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_quay
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_quay
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Delete Quay namespace
- Create Quay Namespace
- Create PVC for Quay storage
- Set Quay config

```bash
cd roles/ocp_quay
molecule test
```

## 📁 Role Structure

```text
roles/ocp_quay/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```

OIDC issuer resolution accepts an omitted `ocp_quay_oidc_issuer_url` and derives the issuer from the configured RHBK host and realm.
