# Role: infra.automation_development_office.ocp_virtualization

Provision an OpenShift Virtualization VM from a cluster **DataSource** / DV
(for example the built-in `rhel9` image in `openshift-virtualization-os-images`),
with optional Multus bridge networking and cloud-init.

This role builds the VirtualMachine spec (DataSource `dataVolumeTemplates`,
Multus NAD, cloud-init, instance type / preference) and applies it with
`kubernetes.core.k8s` when that VirtualMachine is not already in the namespace.

For bridge/Multus mode the role looks up the NetworkAttachmentDefinition first
and creates it only when missing. An existing NAD (for example
`ado-built-vm/br-ex-network`) is reused without PATCH/delete so a working
`spec.config` JSON string is never rewritten as an object.

When `instance_type` is `custom` (or empty), the role sets explicit CPU topology
(`sockets` / `cores` / `threads`) instead of cores-only. Preferences such as
`rhel.9` require sockets; a cores-only spec is rejected by the KubeVirt
admission webhook.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift Virtualization (KubeVirt) installed
- Collection: `kubernetes.core`
- OpenShift credentials via `K8S_AUTH_*` or `provision_openshift_virt_api_*` /
  `host` + `token`
- A usable DataSource (prefer provided golden images: `rhel9`, `rhel8`, …)

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `source_name` | Cluster DataSource name (default `rhel9`) |
| `source_namespace` | DataSource namespace (default `openshift-virtualization-os-images`) |
| `instance_type` | KubeVirt instance type (default `u1.large`, 2 CPU / 8Gi). Use `custom` for explicit `domain.cpu` topology |
| `preference` | Guest preference (default `rhel.9`) |
| `cpu_cores` | For `instance_type=custom`, total guest vCPUs mapped to `domain.cpu.sockets` (default `2`) |
| `cpu_sockets` / `cpu_cores_per_socket` / `cpu_threads` | Optional custom topology overrides (default sockets=`cpu_cores`, cores=`1`, threads=`1`) |
| `vm_namespace` | Target namespace (default `ado-built-vm`) |
| `vm_name` | VirtualMachine metadata.name (required) |
| `network_mode` | `pod` or `bridge` (use with `multus_network_name` for br-ex) |
| `vm_state` | `present` or `absent` (absent deletes VM locally) |

Create runs only when the VM is missing. An existing VirtualMachine is left
unchanged.

## 🚀 Role Usage

```yaml
- name: Provision Virt VM
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_virtualization
      vars:
        vm_name: keycloak-ado
        vm_namespace: ado-built-vm
        source_name: rhel9
        instance_type: u1.large
        preference: rhel.9
        network_mode: bridge
        multus_network_name: ado-built-vm/br-ex-network
```

Contoller playbook: `playbooks/provision/ado-provision-openshift-virt-vm-bootstrap.yml`
JT: **ADO | Provision OpenShift Virt VM**. Survey / extra_vars should win over
stale `component_config` defaults.

If the VMI shows `ErrorUnschedulable` with `Insufficient memory`, shrink the
instance type rather than changing the guest image.

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via Contoller JT
`ado-ocp-virtualization-deploy-bootstrap` or lab virt provision workflow.

## 📁 Role Structure

```text
roles/ocp_virtualization/
  README.md
  defaults/main.yml
  meta/main.yml
  tasks/
    main.yml
    create_vm.yml
    delete_vm.yml
```
