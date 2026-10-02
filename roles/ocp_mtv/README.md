# Role: infra.ado.ocp_mtv

Install the Migration Toolkit for Virtualization operand
(``ForkliftController``) after the ``mtv-operator`` Subscription is ready.
Requires OpenShift Virtualization on the target cluster for migrations.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- ``kubernetes.core``
- ``mtv-operator`` CSV Succeeded in ``openshift-mtv`` (playbook installs it)
- OpenShift Virtualization recommended on the destination cluster

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | ``present`` (default) creates ``ForkliftController``; ``absent`` deletes it. |
| `name_space` / `operator_namespace` | MTV namespace. Default from components: ``openshift-mtv``. |
| `ocp_mtv_controller_name` | ForkliftController name. Default: ``forklift-controller``. |
| `ocp_mtv_olm_managed` | Set ``spec.olm_managed``. Default: ``true``. |

## 🚀 Role Usage

```yaml
- name: Configure MTV ForkliftController
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_mtv
      vars:
        state: present
        name_space: openshift-mtv
```

Preflight: select OpenShift app **mtv** (Migration Toolkit for Virtualization).
Also select **ocp_virtualization** when this cluster is a migration target.

Set ``component_config.mtv.channel`` to a channel that exists in the cluster
Software Catalog (default ``release-v2.12``). MTV versions are tied to OCP
versions — pick the channel the catalog offers for your cluster.

## 🧪 Role Molecule Testing

No dedicated Molecule scenario yet; covered via bootstrap playbook + Contoller JT.

```bash
cd extensions/molecule
# use closest OpenShift operator scenario patterns when adding coverage
```

## 📁 Role Structure

```text
roles/ocp_mtv/
  README.md
  defaults/
  meta/
  tasks/
```
