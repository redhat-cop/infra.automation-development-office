# Role: infra.automation_development_office.ocp_operator_subscription

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
| `operator_subscription_namespace` / `name_space` | Namespace for the Subscription. Empty string falls through to ``name_space``. |
| `operator_subscription_name` | Subscription ``metadata.name``. Empty or unset uses ``operator_name-sub``. |
| `operator_csv_contains` | Operator package prefix for uninstall. Matches that exact CSV name or ``<prefix>.<version>`` only (defaults to ``operator_name``). |
| `ocp_operator_subscription_absent_sweep_workloads` | When ``true``, ``ocp_absent_cleanup`` also deletes Deployments/Pods in the subscription namespace (default ``false``). ``openshift-operators`` refuses this workload sweep. |

On ``state=absent``, after Subscription removal this role deletes only CSVs in the subscription namespace whose name is exactly ``operator_csv_contains`` or ``<operator_csv_contains>.<version>``. A shorter token such as ``operator`` does not match ``openshift-gitops-operator.v1``. Each selected CSV is checked again before deletion. OLM copied CSVs are left alone. InstallPlans are deleted only when every CSV they reference matches that same rule. The follow-up ``ocp_absent_cleanup`` call uses that same prefix, may strip finalizers on those selected CSVs, and does not finalize the namespace.

## 🚀 Role Usage

```yaml
- name: Run ocp_operator_subscription
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_operator_subscription
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
