# Role: infra.ado.ocp_namespace

Ocp Namespace automation role. Primary tasks include: Create namespace.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `name_space` | Namespace to create when ``ocp_namespace_name`` is unset. |
| `ocp_namespace_name` | Explicit namespace name (wins over host fact ``name_space``). Use when creating a different NS than the component operand. |
| `state` | ``present`` / ``absent``. Defaults to ``present``. |

## 🚀 Role Usage

```yaml
- name: Run ocp_namespace
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_namespace
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create namespace

```bash
cd roles/ocp_namespace
molecule test
```

## 📁 Role Structure

```text
roles/ocp_namespace/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
