# Role: infra.ado.ocp_acm_policy

Generate a namespace-label ACM policy and explicit cluster placement locally.

## Role Author

Automation Development Office.

## ✅ Role Requirements

Ansible on the generation host and a writable output directory. Generation makes
no Kubernetes calls and needs no Internet access. Applying output later requires
the corresponding Argo CD or ACM APIs, permissions, and internal Git access.
No credentials are generated or copied into manifests.

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `ocp_acm_policy_target_namespace` | Namespace to check on selected managed clusters. |
| `ocp_acm_policy_label_key / ocp_acm_policy_label_value` | Required namespace label. |
| `ocp_acm_policy_cluster_set` | Existing managed cluster set to bind and select. |
| `ocp_acm_policy_selector_key / ocp_acm_policy_selector_value` | Explicit label selector for managed clusters. |
| `ocp_acm_policy_remediation` | inform by default; enforce acts only after applying output. |
| `ocp_acm_policy_output_dir` | Local directory for the policy bundle. |

The following defaults define the role contract. Supply nonempty target inputs.

```yaml
---
ocp_acm_policy_output_dir: '{{ playbook_dir }}/policies'
ocp_acm_policy_name: namespace-label
ocp_acm_policy_namespace: policies
ocp_acm_policy_target_namespace: ''
ocp_acm_policy_label_key: ''
ocp_acm_policy_label_value: ''
ocp_acm_policy_cluster_set: ''
ocp_acm_policy_selector_key: ''
ocp_acm_policy_selector_value: ''
ocp_acm_policy_remediation: inform
```

The GitOps role requires a safe relative repository path. It writes resources
under that path and an Application under `gitops-applications/`. It does not enable
automatic sync, pruning, or deletion finalizers. The ACM role requires an explicit
cluster set and selector. It writes a hub Namespace, ManagedClusterSetBinding,
Placement, Policy/ConfigurationPolicy, and PlacementBinding. Remediation defaults
to `inform`; `enforce` can create the target namespace and add/update its label
when the policy is later applied. Other labels are preserved with `musthave`.
Generation neither installs prerequisites nor registers/applies the output.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_acm_policy
      ocp_acm_policy_target_namespace: team-a
      ocp_acm_policy_label_key: owner
      ocp_acm_policy_label_value: platform
      ocp_acm_policy_cluster_set: production
      ocp_acm_policy_selector_key: environment
      ocp_acm_policy_selector_value: production
      ocp_acm_policy_output_dir: /tmp/platform-repo/policies
```

Use local/internal repository URLs for disconnected sites. Configure Git
credentials and trust independently in Argo CD. Do not embed passwords in URLs.
Repeated generation with identical inputs leaves the files unchanged. Renamed,
disabled, or moved outputs are not automatically deleted: review existing files
and ownership before committing a migration to a repository watched by Argo CD.

## 🧪 Role Molecule Testing

`extensions/molecule/integration_delivery_generation` tests offline rendering,
idempotence, generated YAML semantics, and rejection of missing cluster selection.
Run `molecule test -s integration_delivery_generation` from `extensions/molecule`
with the source collection installed. No live Argo CD or ACM test is implied.

## 📁 Role Structure

```text
ocp_acm_policy/
  defaults/main.yml
  tasks/main.yml
  meta/main.yml
  README.md
```
