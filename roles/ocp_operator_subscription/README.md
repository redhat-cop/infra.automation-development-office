# Role: infra.ado.ocp_operator_subscription

Ocp Operator Subscription automation role. Primary tasks include: Subscription | Derive namespaces and names; Subscription | Assert required inputs; Namespace | Ensure subscription namespace exists.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | ``present`` to create/update the Subscription; ``absent`` to delete the Subscription and matching ClusterServiceVersions (so the operator leaves Installed Operators). |
| `operator_name` | OLM package name (Subscription ``spec.name``). |
| `operator_channel` | Channel (required for ``present``). |
| `operator_source` | Catalog source (required for ``present``). |
| `operator_source_namespace` | Catalog source namespace (required for ``present``). |
| `operator_subscription_namespace` / `name_space` | Namespace for the Subscription. |
| `operator_csv_contains` | Optional substring to match CSVs on uninstall (defaults to ``operator_name``). |
| `ocp_operator_subscription_absent_sweep_workloads` | When ``true``, ``ocp_absent_cleanup`` also deletes Deployments/Pods in the subscription namespace (default ``false`` — safe for shared NS like ``openshift-operators``). |

On ``state=absent``, after Subscription/CSV/InstallPlan removal this role runs ``infra.ado.ocp_absent_cleanup`` with ``ocp_absent_cleanup_csv_name_match`` set to the operator CSV match so Failed CSVs and Terminating leftovers are cleared without wiping unrelated operators in a shared namespace.

## 🚀 Role Usage

```yaml
- name: Run ocp_operator_subscription
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_operator_subscription
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Subscription | Derive namespaces and names
- Subscription | Assert required inputs
- Namespace | Ensure subscription namespace exists
- Openshift_tools_operator_groups | Create/Update (scoped vs all namespaces)

```bash
cd roles/ocp_operator_subscription
molecule test
```

## 📁 Role Structure

```text
roles/ocp_operator_subscription/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
