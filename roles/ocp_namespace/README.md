# Role: infra.automation_development_office.ocp_namespace

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
| `ocp_namespace_delete_settle_seconds` | Pause after delete before the presence check (default ``3``). |
| `ocp_namespace_absent_fail_if_present` | After ``absent``, fail if the namespace still exists (default ``true``). The failure reports finalizers and does not delete CSVs. |
| `ocp_namespace_advanced_cleanup` | Opt-in gate for ``ocp_absent_cleanup`` (default ``false``). |
| `ocp_namespace_absent_sweep_olm` | With advanced cleanup, list/delete OLM objects (default ``false``). |
| `ocp_namespace_absent_sweep_workloads` | With advanced cleanup, delete Deployments/Pods (default ``false``). |
| `ocp_namespace_absent_finalize` | With advanced cleanup, call namespace ``/finalize`` on a Terminating namespace (default ``false``). |
| `ocp_namespace_absent_csv_name_match` | CSV name substring for advanced OLM cleanup. Empty does not mean every CSV. |
| `ocp_namespace_absent_authorize_csv_delete` | Required before any CSV or InstallPlan delete (default ``false``). |
| `ocp_namespace_absent_authorize_unfiltered_csv_delete` | Required to delete CSVs when the name filter is empty (default ``false``). |
| `ocp_namespace_absent_delete_copied_csvs` | Delete OLM copied CSVs (``olm.copiedFrom`` or a different ``olm.operatorNamespace``). Default ``false``. |
| `ocp_namespace_absent_strip_csv_finalizers` | Strip finalizers on CSVs already selected for deletion (default ``false``). |
| `ocp_namespace_absent_authorize_unfiltered_workloads` | Delete every Deployment and force-delete Pods (default ``false``). |
| `ocp_namespace_absent_deployment_names` | Deployment allowlist. Empty does not mean every Deployment. |
| `ocp_namespace_blocked_namespaces` | Extra protected names. The built-in platform denylist always applies. |
| `ocp_namespace_blocked_namespace_prefixes` | Extra protected prefixes. ``kube-`` is always protected. |

``state=absent`` deletes only the requested Namespace resource. It refuses platform namespaces (``default``, ``kube-*``, ``openshift``, control-plane namespaces such as ``openshift-etcd`` and ``openshift-monitoring``, and ``openshift-operators``). It does not call ``ocp_absent_cleanup``, delete ClusterServiceVersions, strip CSV finalizers, or sweep workloads.

If the namespace is still present, the role reports the phase and finalizers and fails when ``ocp_namespace_absent_fail_if_present`` is true. Stuck-namespace cleanup is a separate opt-in: set ``ocp_namespace_advanced_cleanup=true`` and only the authorize flags for the actions you intend.

On ``state=present``, a Terminating namespace is waited on and then the role fails if it is still Terminating. ``state=present`` never sweeps CSVs, deletes workloads, or strips finalizers, including when advanced-cleanup flags are set.

```yaml
- name: Delete one namespace without touching Operators
  ansible.builtin.include_role:
    name: infra.automation_development_office.ocp_namespace
  vars:
    ocp_namespace_name: test-namespace
    state: absent

- name: Explicit stuck-namespace finalize, still without CSV deletion
  ansible.builtin.include_role:
    name: infra.automation_development_office.ocp_namespace
  vars:
    ocp_namespace_name: test-namespace
    state: absent
    ocp_namespace_advanced_cleanup: true
    ocp_namespace_absent_finalize: true
```

## 🚀 Role Usage

```yaml
- name: Run ocp_namespace
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_namespace
```

## 🧪 Role Molecule Testing

Safety coverage does not need a cluster:

```bash
python3 tests/unit/roles/test_ocp_absent_cleanup.py
```

``extensions/molecule/ocp_namespace`` creates a namespace on whatever cluster
``K8S_AUTH_HOST`` points at. Do not run it as a deletion test against a shared
cluster.

## 📁 Role Structure

```text
roles/ocp_namespace/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
    main.yml
    advanced_cleanup.yml
    finalize_namespace.yml
  tests/
  vars/
```
