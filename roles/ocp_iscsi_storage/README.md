# Role: infra.automation_development_office.ocp_iscsi_storage

Install Synology CSI (iSCSI) on OpenShift using `kubernetes.core.k8s`
(no `oc` CLI). Bundled vendor manifests plus a generated
`client-info-secret` and StorageClass.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- `kubernetes.core` collection
- Cluster-admin OpenShift credentials (kubeconfig or host + token)

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_iscsi_storage_dsm_host` | Synology DSM IP/hostname (required). |
| `ocp_iscsi_storage_dsm_port` | DSM API port. Default: `5000`. |
| `ocp_iscsi_storage_dsm_https` | Use HTTPS to DSM. Default: `false`. |
| `ocp_iscsi_storage_dsm_username` | DSM username (required, vault). |
| `ocp_iscsi_storage_dsm_password` | DSM password (required, vault). |
| `ocp_iscsi_storage_class_name` | StorageClass name. Default: `synology-iscsi-storage`. |
| `ocp_iscsi_storage_location` | DSM volume path. Default: `/volume1`. |
| `ocp_iscsi_storage_is_default` | Mark StorageClass as default. Default: `true`. |
| `ocp_iscsi_storage_install_snapshotter` | Install snapshotter manifests. Default: `true`. |
| `ocp_iscsi_storage_connection` | Optional `host` / `api_key` / `kubeconfig` / `validate_certs`. |

## 🚀 Role Usage

```yaml
- name: Install Synology iSCSI CSI
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_iscsi_storage
      vars:
        ocp_iscsi_storage_dsm_host: 192.168.0.6
        ocp_iscsi_storage_dsm_username: "{{ vault_dsm_user }}"
        ocp_iscsi_storage_dsm_password: "{{ vault_dsm_pass }}"
        ocp_iscsi_storage_connection:
          kubeconfig: "{{ kubeconfig_path }}"
          validate_certs: false
```

Applies namespace, client-info Secret, OpenShift SCC, controller, CSIDriver,
node DaemonSet, StorageClass, and optional snapshotter via idempotent k8s
module calls. Auth uses role connection kwargs or `KUBECONFIG` / in-cluster
defaults.

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

```bash
cd roles/ocp_iscsi_storage
molecule test
```

## 📁 Role Structure

```text
roles/ocp_iscsi_storage/
  README.md
  defaults/
  files/
  handlers/
  meta/
  tasks/
  templates/
  tests/
  vars/
```
