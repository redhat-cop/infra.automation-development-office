# Role: infra.automation_development_office.ocp_absent_cleanup

Explicit OpenShift cleanup for one or more named namespaces. CSV deletion,
workload deletion, CSV finalizer stripping, and namespace ``/finalize`` each
require their own authorize flag. Ordinary namespace deletion belongs to
``ocp_namespace`` and does not call this role.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core 2.16+
- Collections: `kubernetes.core` (see `collections/requirements.yml`)
- Cluster API access via `K8S_AUTH_HOST` / `K8S_AUTH_API_KEY` (or `host` /
  `token` as used by other `ocp_*` roles)
- Caller must pass an explicit non-empty `ocp_absent_cleanup_namespaces` list
- Selection rules live in `plugins/filter/ocp_absent_cleanup.py`

## 📦 Role Variables

| Variable | Default | Description |
| --- | --- | --- |
| `ocp_absent_cleanup_namespaces` | `[]` | **Required.** Namespaces this run may touch. |
| `ocp_absent_cleanup_mode` | `cleanup` | `cleanup` or `check` (inventory/report only). |
| `ocp_absent_cleanup_sweep_olm` | `false` | Consider CSVs and InstallPlans. Still requires authorize flags. |
| `ocp_absent_cleanup_authorize_csv_delete` | `false` | Required before any CSV or InstallPlan delete. |
| `ocp_absent_cleanup_authorize_unfiltered_csv_delete` | `false` | Required when `csv_name_match` is empty. Empty does not mean every CSV. |
| `ocp_absent_cleanup_csv_name_match` | `""` | Exact CSV name, or OLM package prefix matching ``<prefix>.<version>`` only. Not a substring. |
| `ocp_absent_cleanup_delete_copied_csvs` | `false` | Also delete OLM copies (`olm.copiedFrom`, or `olm.operatorNamespace` for another namespace). |
| `ocp_absent_cleanup_strip_csv_finalizers` | `false` | Strip finalizers only on CSVs already selected for deletion. |
| `ocp_absent_cleanup_sweep_workloads` | `false` | Consider Deployments and Pods. |
| `ocp_absent_cleanup_deployment_names` | `[]` | Deployment allowlist. Empty does not mean every Deployment. |
| `ocp_absent_cleanup_authorize_unfiltered_workloads` | `false` | Delete every Deployment and force-delete Pods in the namespace. |
| `ocp_absent_cleanup_fail_if_present` | `true` | Fail if a targeted namespace still exists after finalize. |
| `ocp_absent_cleanup_finalize` | `false` | Call namespace `/finalize` and wait until gone. |
| `ocp_absent_cleanup_finalize_only_terminating` | `true` | Only finalize when `status.phase=Terminating`. |
| `ocp_absent_cleanup_blocked_namespaces` | `[]` | Extra deny names. The built-in platform denylist always applies. |
| `ocp_absent_cleanup_blocked_namespace_prefixes` | `[]` | Extra deny prefixes. `kube-` is always denied. |
| `ocp_absent_cleanup_terminating_retries` | `12` | Retries waiting for namespace to disappear after finalize. |
| `ocp_absent_cleanup_terminating_delay` | `5` | Seconds between finalize waits. |
| `ocp_absent_cleanup_delete_settle_seconds` | `3` | Pause after sweeps before finalize. |

Safety gates:

- Refuses an empty namespace list and any name that is not one DNS-1123 label
- Refuses platform namespaces (`default`, `kube-*`, `openshift`, `openshift-etcd`, `openshift-monitoring`, and the other control-plane namespaces)
- `openshift-operators` accepts only a name-matched CSV cleanup. Workload sweep, unfiltered CSV deletion, and copied-CSV deletion are refused there
- Deletes only objects whose namespace is the requested namespace
- Skips OLM copied CSVs unless `ocp_absent_cleanup_delete_copied_csvs` is true
- `check` mode lists objects and does not delete them

## 🚀 Role Usage

### Callers

| Caller | When | Behavior |
| --- | --- | --- |
| `infra.automation_development_office.ocp_namespace` | `state=absent` | Does not call this role unless `ocp_namespace_advanced_cleanup` is true |
| `infra.automation_development_office.ocp_operator_subscription` | `state=absent` | Matched CSV cleanup only. Does not delete copies or finalize the namespace |
| Cert-manager uninstall playbook | explicit cleanup task | Name-matched cert-manager CSVs in the cert-manager namespaces, plus workloads and finalize |

### Standalone check

```yaml
- name: Report stuck cert-manager namespaces
  ansible.builtin.include_role:
    name: infra.automation_development_office.ocp_absent_cleanup
  vars:
    ocp_absent_cleanup_namespaces:
      - cert-manager
      - cert-manager-operator
    ocp_absent_cleanup_mode: check
    ocp_absent_cleanup_fail_if_present: false
  tags:
    - ocp_absent_cleanup
    - check
```

### Matched CSV cleanup

```yaml
- name: Remove one operator CSV in its own namespace
  ansible.builtin.include_role:
    name: infra.automation_development_office.ocp_absent_cleanup
  vars:
    ocp_absent_cleanup_namespaces:
      - openshift-operators
    ocp_absent_cleanup_mode: cleanup
    ocp_absent_cleanup_sweep_olm: true
    ocp_absent_cleanup_authorize_csv_delete: true
    ocp_absent_cleanup_csv_name_match: cert-manager-operator
    ocp_absent_cleanup_delete_copied_csvs: false
    ocp_absent_cleanup_strip_csv_finalizers: true
    ocp_absent_cleanup_sweep_workloads: false
    ocp_absent_cleanup_finalize: false
    ocp_absent_cleanup_fail_if_present: false
```

## 🧪 Role Molecule Testing

Unit tests cover namespace denylist, CSV copy detection, and the task defaults. They do not need a cluster:

```bash
python3 tests/unit/roles/test_ocp_absent_cleanup.py
```

There is no Molecule scenario that deletes namespaces. Do not add a live-cluster deletion test against a shared cluster.

## Tags

| Tag | Effect |
| --- | --- |
| `ocp_absent_cleanup` | Entire gate block (normalize, allowlist asserts, per-NS cleanup) |

## 📁 Role Structure

```text
roles/ocp_absent_cleanup/
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
  tasks/cleanup_one_namespace.yml
  tasks/finalize_namespace.yml
  README.md
```
