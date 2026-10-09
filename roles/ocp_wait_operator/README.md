# Role: infra.ado.ocp_wait_operator

Ocp Wait Operator automation role. Primary tasks include: Wait for Operator CSV to appear; Set fact if Operator CSV is installed; Debug operator installation status.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | When not ``present`` (e.g. ``absent``), the role exits immediately and does not wait for CSV/Deployment. |
| `ocp_wait_operator_retries` | Role input variable used to configure automation behavior. |
| `ocp_wait_operator_delay` | Role input variable used to configure automation behavior. |
| `operator_namespace` | Namespace that holds the operator CSV. Empty values fall through to ``operator_subscription_namespace`` then ``name_space`` so a leaked ACS/GitOps namespace is not used. |
| `operator_name` / `operator_csv_contains` | Substring matched against CSV ``metadata.name`` (literal ``in``, not regex). Wait succeeds only when ``status.phase`` is ``Succeeded``. |

## 🚀 Role Usage

```yaml
- name: Run ocp_wait_operator
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_wait_operator
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Wait for Operator CSV to appear
- Set fact if Operator CSV is installed
- Debug operator installation status
- Get all Deployments in namespace

```bash
cd roles/ocp_wait_operator
molecule test
```

## 📁 Role Structure

```text
roles/ocp_wait_operator/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
