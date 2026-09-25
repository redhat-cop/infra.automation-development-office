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
| `ocp_namespace_terminating_retries` | Retries while waiting for a Terminating namespace to disappear (default ``24``). |
| `ocp_namespace_terminating_delay` | Seconds between Terminating waits (default ``5``). |
| `ocp_namespace_delete_wait_timeout` | Seconds for ``kubernetes.core.k8s`` wait on delete (default ``45``). |
| `ocp_namespace_delete_settle_seconds` | Pause after delete before finalize check (default ``3``). |
| `ocp_namespace_absent_sweep_olm` | On ``absent``, run ``ocp_absent_cleanup`` OLM sweep (default ``true``). |
| `ocp_namespace_absent_sweep_workloads` | On ``absent``, sweep Deployments/Pods via ``ocp_absent_cleanup`` (default ``true``). |
| `ocp_namespace_absent_fail_if_present` | After ``absent``, fail if the namespace still exists (default ``true``). |

On ``state=absent``, this role invokes ``infra.ado.ocp_absent_cleanup`` before and after delete so stuck Terminating namespaces, Failed CSVs, and leftover Deployments are cleared consistently across OpenShift components.

On ``state=present``, if the namespace already exists in ``Terminating`` phase (common after a prior absent), the role runs the same cleanup gate, waits/finalizes, then creates — and fails if the namespace is still Terminating (``kubernetes.core.k8s`` alone can return ok while the NS is unusable).

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
