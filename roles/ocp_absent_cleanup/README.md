# Role: infra.ado.ocp_absent_cleanup

Safe OpenShift absent cleanup gate for stuck Terminating namespaces, finalizers,
leftover OLM CSVs/InstallPlans, and Deployments/pods.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core 2.16+
- Collections: `kubernetes.core` (see `collections/requirements.yml`)
- Cluster API access via `K8S_AUTH_HOST` / `K8S_AUTH_API_KEY` (or `host` /
  `token` as used by other `ocp_*` roles)
- Caller must pass an explicit non-empty `ocp_absent_cleanup_namespaces` list

## 📦 Role Variables

| Variable | Default | Description |
| --- | --- | --- |
| `ocp_absent_cleanup_namespaces` | `[]` | **Required.** Namespaces this run may touch. |
| `ocp_absent_cleanup_mode` | `cleanup` | `cleanup` or `check` (inventory/report only). |
| `ocp_absent_cleanup_sweep_olm` | `true` | Delete CSVs and InstallPlans in each namespace. |
| `ocp_absent_cleanup_csv_name_match` | `""` | Optional substring; when set only matching CSVs (and related InstallPlans) are removed — use for shared namespaces. |
| `ocp_absent_cleanup_sweep_workloads` | `true` | Delete Deployments and force-delete Pods. |
| `ocp_absent_cleanup_deployment_names` | `[]` | Optional Deployment name allowlist; empty = all Deployments in the namespace. |
| `ocp_absent_cleanup_fail_if_present` | `true` | Fail if a targeted namespace still exists after cleanup. |
| `ocp_absent_cleanup_finalize` | `true` | When true, may call namespace `/finalize` and wait until gone. Subscription absent sets this `false`. |
| `ocp_absent_cleanup_finalize_only_terminating` | `true` | Only finalize when `status.phase=Terminating` (never force-delete an Active NS). |
| `ocp_absent_cleanup_blocked_namespaces` | see defaults | Hard deny list (`default`, `kube-system`, `openshift`, …). |
| `ocp_absent_cleanup_blocked_namespace_prefixes` | `[kube-]` | Prefix deny list (`kube-*`). Does **not** block `openshift-*` (ADO operators often live there). |
| `ocp_absent_cleanup_terminating_retries` | `12` | Retries waiting for namespace to disappear after finalize. |
| `ocp_absent_cleanup_terminating_delay` | `5` | Seconds between finalize waits. |
| `ocp_absent_cleanup_delete_settle_seconds` | `3` | Pause after sweeps before finalize. |

Safety gates:

- Refuses an empty namespace list
- Refuses blocked platform namespaces and `kube-*`
- Never invents namespaces — callers must be explicit

## 🚀 Role Usage

### Automatic wiring (OpenShift absent)

| Caller | When | Behavior |
| --- | --- | --- |
| `infra.ado.ocp_namespace` | `state=absent` | Sweep before delete; gate after delete (`fail_if_present` default true) |
| `infra.ado.ocp_operator_subscription` | `state=absent` | Matched CSV cleanup only (no namespace finalize); workloads off by default |
| Cert-manager uninstall playbook | `state=absent` | Pre-delete sweep of operand + operator namespaces |

Any OpenShift component that deletes namespaces via `ocp_namespace` therefore gets
this gate without extra playbook wiring.

### Standalone check

```yaml
- name: Report stuck cert-manager namespaces
  ansible.builtin.include_role:
    name: infra.ado.ocp_absent_cleanup
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

### Standalone cleanup

```yaml
- name: Force-clean cert-manager leftovers
  ansible.builtin.include_role:
    name: infra.ado.ocp_absent_cleanup
  vars:
    ocp_absent_cleanup_namespaces:
      - cert-manager
      - cert-manager-operator
    ocp_absent_cleanup_mode: cleanup
  tags:
    - ocp_absent_cleanup
    - cleanup
```

### Shared namespace (matched CSV only)

```yaml
- name: Clean one operator CSV in a shared NS
  ansible.builtin.include_role:
    name: infra.ado.ocp_absent_cleanup
  vars:
    ocp_absent_cleanup_namespaces:
      - openshift-operators
    ocp_absent_cleanup_csv_name_match: cert-manager
    ocp_absent_cleanup_sweep_workloads: false
    ocp_absent_cleanup_fail_if_present: false
```

## 🧪 Role Molecule Testing

Allowlist / assert coverage (no cluster required; runs in PR CI):

```bash
cd extensions/molecule
ln -sfn . molecule
export ANSIBLE_COLLECTIONS_PATH="${HOME}/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH}"
molecule test -s integration_ocp_absent_cleanup
```

Unit tests:

```bash
python3 tests/unit/roles/test_ocp_absent_cleanup.py
# or: python3 -m pytest tests/unit/roles/test_ocp_absent_cleanup.py -q
```

Full cluster cleanup (lab only) is exercised by OpenShift component
`state=absent` jobs after installing the collection.

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
