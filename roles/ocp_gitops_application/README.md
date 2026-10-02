# Role: infra.ado.ocp_gitops_application

Generate a manual-sync Argo CD Application and Kustomize resources locally.

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
| `ocp_gitops_application_repo_url` | Required Git repository URL; credentials are configured separately. |
| `ocp_gitops_application_resources` | Required list of Kubernetes resources to render. |
| `ocp_gitops_application_repo_path` | Relative source path within the Git repository. |
| `ocp_gitops_application_output_dir` | Local repository root for generated files. |
| `ocp_gitops_application_destination` | Target cluster API server known to Argo CD. |

The following defaults define the role contract. Supply nonempty target inputs.

```yaml
---
ocp_gitops_application_name: devspaces
ocp_gitops_application_namespace: openshift-gitops
ocp_gitops_application_project: default
ocp_gitops_application_repo_url: ''
ocp_gitops_application_revision: main
ocp_gitops_application_repo_path: gitops/devspaces/resources
ocp_gitops_application_destination: https://kubernetes.default.svc
ocp_gitops_application_target_namespace: openshift-devspaces
ocp_gitops_application_output_dir: '{{ playbook_dir }}'
ocp_gitops_application_resources: []
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
    - role: infra.ado.ocp_gitops_application
      ocp_gitops_application_repo_url: https://git.example.test/platform.git
      ocp_gitops_application_output_dir: /tmp/platform-repo
      ocp_gitops_application_resources:
        - apiVersion: v1
          kind: Namespace
          metadata:
            name: example
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
ocp_gitops_application/
  defaults/main.yml
  tasks/main.yml
  meta/main.yml
  README.md
```
