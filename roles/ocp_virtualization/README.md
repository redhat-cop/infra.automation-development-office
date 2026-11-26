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

### Two job templates, one playbook and role

| Job template | For | Survey |
|---|---|---|
| **ADO \| Provision OpenShift Virt VM** (Advanced) | Platform engineers | Everything the role supports: custom CPU and memory, boot image, storage, network, cloud-init login, static IP, remove |
| **ADO \| Create VM — Self Service** | Application teams | Project, VM name, approved image, approved size (Small, Medium, Large), start |

Both run `ado-provision-openshift-virt-vm-bootstrap.yml` and this role. Use AAP
permissions to decide who can launch each template.

Self Service reads its approved values from `openshift_virt_self_service_policy`
(generated from the Preflight OpenShift Virt VM form into `vars_openshift_virt.yml`).
The playbook refuses a launch that is outside the policy, even if the value arrives as
an extra variable: project, image and preference, size, storage class, network mode and
attachment, root disk size, login user and SSH key, passwords, root SSH, hostname and
removal. It also reads the project `ResourceQuota` (read-only) and refuses a size the
quota clearly cannot hold: memory, storage, PVC count and VM count. CPU is not checked
because the request depends on the cluster overcommit setting. If the quota cannot be
read, the check is skipped with a message and OpenShift still enforces it at creation.

#### How Self Service is enforced, and where it stops

An extra variable has higher precedence than every variable a playbook sets, so no
playbook can stop a value that reaches it as an extra variable from changing the
variables it computes. The guard is therefore built so that replacing an internal
variable does not help:

- It checks the **final values the roles read** (`instance_type`, `storage_class`,
  `source_namespace`, `name_space`, `ocp_namespace_name`, `state`, `cloud_init_*`, ...)
  against the policy, not a copy the playbook computed.
- It reads the policy from `group_vars/all/<env>/vars_openshift_virt.yml` in the project,
  not from the `openshift_virt_self_service_policy` variable, so a policy passed as an
  extra variable has no effect on the check. A policy that holds template expressions, a
  missing file or an invalid environment name is refused.
- It parses the final `cloud_init_user_data` and compares it with the one approved
  structure (approved login and SSH key, no passwords, no root SSH, nothing else). Extra
  keys such as `runcmd` or `write_files`, a changed value or a duplicate key is refused.
  `cloud_init_network_data` must be empty (DHCP).
- It turns on when `ado_vm_template_mode` is `self_service` **or** AAP names a Self
  Service job template (`awx_job_template_name`), and a mode other than `advanced` or
  `self_service` is refused.

What it cannot do: if an extra variable named `ado_vm_template_mode=advanced` reaches the
play and AAP does not also name a Self Service job template, the run is treated as
Advanced and is not guarded. Keep that from happening in AAP: leave **Prompt on launch**
off for variables, job tags, limit and inventory on the Self Service template, give users
**Execute** on that template only (not on the Advanced one or on the project), and do not
add it to a workflow whose nodes pass variables. The survey answers are the only variables
the template accepts. Whether your AAP discards undeclared extra variables, and whether it
sets `awx_job_template_name` after user variables, is AAP behavior this repository cannot
verify; check it on your instance.

Not covered by the guard (not part of the approved image, size, project or cloud-init):
the OpenShift API address and token (`provision_openshift_virt_api_host`, `..._api_token`,
`host`, `token`), `multus_nad_name` / `multus_nad_config`, `app_label`, wait timeouts and
the interface name. They are not survey variables, so AAP rejects them the same way.

The role looks the VM up first and creates it only when it is missing. An existing VM is
never replaced or changed by either template.

Not supported by the role, so not offered by either template: PVC, DataVolume or ISO
boot sources, additional disks, node placement or scheduling, start or stop of an
existing VM, and Windows. Self Service uses DHCP in the guest (no address pool in the
policy).

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
