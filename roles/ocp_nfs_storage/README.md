# Role: infra.ado.ocp_nfs_storage

Install the NFS CSI driver (Helm chart ``csi-driver-nfs``) on OpenShift and
create an NFS-backed StorageClass. Used by bootstrap when preflight selects
the ``nfs_csi`` OpenShift option, and by Contoller / local playbook
``playbooks/openshift/ado-install-nfs-csi-bootstrap.yml``.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- ``kubernetes.core`` and Helm available in the EE / preflight pod
- Cluster-admin OpenShift credentials (kubeconfig or host + token)
- Reachable NFS server and export path (for the StorageClass)
- Default install uses the **bundled** Helm chart under
  ``files/charts/csi-driver-nfs-<version>.tgz`` (~12 KiB) — no GitHub helm
  repo fetch. Cluster still pulls CSI container images from the registries
  referenced by the chart unless you mirror those separately.

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_nfs_storage_server` | NFS server hostname or IP (required). |
| `ocp_nfs_storage_share` | NFS export path (required). Example: `/volume1/openshift`. |
| `ocp_nfs_storage_class_name` | StorageClass name. Default: `synology-nfs-csi`. |
| `ocp_nfs_storage_driver_version` | Helm chart version (no leading ``v``). Default: `4.11.0`. Must match a bundled ``files/charts/csi-driver-nfs-<version>.tgz`` when using the default local chart. |
| `ocp_nfs_storage_use_bundled_chart` | Use the chart shipped in the role (default ``true``). Set ``false`` to ``helm repo add`` the upstream GitHub charts URL. |
| `ocp_nfs_storage_chart_path` | Optional absolute path to a chart ``.tgz`` or directory. Overrides the bundled archive when set. |
| `ocp_nfs_storage_nfs_version` | NFS protocol version. Default: `4.1`. |
| `ocp_nfs_storage_namespace` | Driver namespace. Default: `csi-driver-nfs`. |
| `ocp_nfs_storage_reclaim_policy` | StorageClass reclaimPolicy. Default: `Delete`. |
| `ocp_nfs_storage_binding_mode` | volumeBindingMode. Default: `Immediate`. |
| `ocp_nfs_storage_allow_volume_expansion` | AllowVolumeExpansion. Default: `true`. |
| `ocp_nfs_storage_create_test_namespace` | Create a sample namespace. Default: `true`. |
| `ocp_nfs_storage_create_test_pvc` | Create a sample PVC. Default: `false`. |
| `ocp_nfs_storage_connection` | Optional ``host`` / ``api_key`` / ``kubeconfig`` / ``validate_certs``. |

Aliases accepted by env generation: ``nfs_server``, ``nfs_share``,
``nfs_storage_class_name``.

## 🚀 Role Usage

```yaml
- name: Install NFS CSI and StorageClass
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_nfs_storage
      vars:
        ocp_nfs_storage_server: 192.168.0.6
        ocp_nfs_storage_share: /volume1/openshift
        ocp_nfs_storage_class_name: synology-nfs-csi
        ocp_nfs_storage_connection:
          kubeconfig: "{{ kubeconfig_path }}"
          validate_certs: false
```

### Preflight / bootstrap

Put ``nfs_csi`` in ``component_options.openshift`` and set OpenShift NFS fields
in preflight JSON (or ``component_config.openshift``):

```json
{
  "component_options": { "openshift": ["nfs_csi"] },
  "openshift": {
    "nfs_server": "192.168.0.6",
    "nfs_share": "/volume1/openshift",
    "nfs_storage_class_name": "synology-nfs-csi"
  }
}
```

``bootstrap_controller`` then runs ``install_nfs_csi.yml`` during scaffolding.
Apps (RHBK, Grafana, GitLab, …) still pick a StorageClass name separately via
each component's storage / Look up field — this role installs the driver and
creates the class.

## 🧪 Role Molecule Testing

```bash
cd extensions/molecule
molecule test -s ocp_nfs_storage
```

## 📁 Role Structure

```text
roles/ocp_nfs_storage/
  README.md
  defaults/
  files/
    charts/
      csi-driver-nfs-4.11.0.tgz
  handlers/
  meta/
  tasks/
  templates/
  tests/
  vars/
```
