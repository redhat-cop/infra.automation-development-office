# Role: infra.ado.ocp_acm

Deploy the ACM MultiClusterHub CR, wait until it is **Running**, keep the ACM
console component enabled, and enable OpenShift Console plug-ins (`acm`,
`mce`) so **Fleet Management** (or **All Clusters**) appears in the web
console.

On **`state=absent`**, remove MultiClusterHub and related hub objects
(MultiClusterEngine, ClusterManager, `local-cluster` ManagedCluster) and clear
known stuck finalizers / stale validating webhooks so a later install is not
poisoned by a half-finished uninstall. Safeguards include recreating the hub
Namespace if MultiClusterHub is orphaned, force-removing the MCH validating
webhook before delete, and clearing finalizers when deletion sticks.

On **`state=present`**, if MultiClusterHub or MultiClusterEngine is already
**Uninstalling**, finish that uninstall first (default
`ocp_acm_heal_stuck_uninstall=true`), then install. Also creates a missing
`local-cluster` Namespace when the ManagedCluster exists without one.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift API access (`kubernetes.core`)
- ACM operator Subscription / CSV already installed (typically via
  `infra.ado.ocp_operator_subscription` + `infra.ado.ocp_wait_operator`)

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `name_space` / `operator_namespace` | ACM hub namespace (default `open-cluster-management`) |
| `ocp_acm_mch_name` | MultiClusterHub name (default `multiclusterhub`) |
| `ocp_acm_mce_name` | MultiClusterEngine name (default `multiclusterengine`) |
| `ocp_acm_clustermanager_name` | ClusterManager name (default `cluster-manager`) |
| `ocp_acm_local_cluster_name` | Local ManagedCluster name (default `local-cluster`) |
| `ocp_acm_availability_config` | MCH `availabilityConfig` (default `High`) |
| `ocp_acm_mch_retries` / `ocp_acm_mch_delay` | Wait loop for MCH `status.phase=Running` |
| `ocp_acm_uninstall_retries` / `ocp_acm_uninstall_delay` | Wait before clearing stuck uninstall finalizers |
| `ocp_acm_heal_stuck_uninstall` | On present, finish Uninstalling MCH/MCE first (default `true`) |
| `ocp_acm_absent_cleanup_mce` | On absent, also remove MultiClusterEngine (default `true`) |
| `ocp_acm_absent_cleanup_clustermanager` | On absent, remove ClusterManager (default `true`) |
| `ocp_acm_absent_cleanup_local_cluster` | On absent, remove `local-cluster` ManagedCluster (default `true`) |
| `ocp_acm_cleanup_stale_webhooks` | Remove known ACM validating webhooks whose Service is gone (default `true`) |
| `ocp_acm_stale_validating_webhooks` | Allowlisted webhook names to consider for stale cleanup |
| `ocp_acm_force_remove_mch_webhook` | On hub cleanup, always delete the MCH validating webhook (default `true`) |
| `ocp_acm_mch_validating_webhook` | MCH ValidatingWebhookConfiguration name |
| `ocp_acm_enable_console_component` | Keep MCH `console` component enabled (default `true`) |
| `ocp_acm_enable_console_plugins` | Patch Console operator `spec.plugins` (default `true`) |
| `ocp_acm_console_plugins` | Plug-in names to enable (default `acm`, `mce`) |
| `ocp_acm_observability_enabled` | When ``true``, deploy Multicluster Observability (default ``false``). |
| `ocp_acm_observability_s3_bucket` / `_endpoint` / `_access_key` / `_secret_key` | Required S3-compatible object storage for Thanos when observability is enabled (lab MinIO works). |
| `ocp_acm_observability_s3_insecure` | Thanos ``insecure`` flag (default ``true`` for lab HTTP MinIO). |
| `ocp_acm_observability_storage_class` | Optional StorageClass for MCO PVCs. |
| `state` | `present` (default) or `absent` |

## 🚀 Role Usage

```yaml
- hosts: localhost
  roles:
    - role: infra.ado.ocp_acm
```

Uninstall (thorough hub cleanup):

```yaml
- hosts: localhost
  roles:
    - role: infra.ado.ocp_acm
      vars:
        state: absent
```

After a successful present run, refresh the OpenShift console and open
**Fleet Management** (older OCP: cluster switcher → **All Clusters**).
First-time ACM install commonly takes 15–30 minutes before MCH reports
Running. Re-running `state=present` (including via the OpenShift workflow)
converges only — it does not delete/recreate MultiClusterHub. The console
component patch is skipped when `console` is already enabled so reruns stay
idempotent.

## 🧪 Role Molecule Testing

```bash
cd extensions/molecule
molecule test -s ocp_acm
```

## 📁 Role Structure

```text
roles/ocp_acm/
  README.md
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
  tasks/present.yml
  tasks/absent.yml
  tasks/finish_stuck_uninstall.yml
  tasks/cleanup_hub.yml
  tasks/cleanup_stale_webhooks.yml
```
