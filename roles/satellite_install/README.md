# Role: `satellite_install`

This Ansible role prepares and installs a Red Hat Satellite host on supported RHEL systems.

It validates OS, CPU, memory, location, and Satellite version before install, supports a safe `pre_check` mode for validation-only runs, and can register the host to RHSM, patch it, prepare storage, install packages, and update DNS/firewall settings.

> **⚠️ Note:**
> This role requires root privileges for system modifications, package installation, and configuration changes. Ensure your target hosts are accessible with privileged access (`become: true`).

## Role Author

- Automation Development Office (automation-development-office@redhat.com)

## ✅ Role Requirements

- Ansible >= 2.9
- Target hosts: Supported Red Hat Enterprise Linux (RHEL 9 or later)
- Privileged access on the target host (`become: true`)
- Required collections:
  - `community.general`
  - `community.crypto`
  - `ansible.posix`
- RHSM activation key and organization ID (when `satellite_install_rhn_connected: true`)
- Suitable additional disk for Satellite storage (optional, for automatic storage management)

## 📦 Role Variables

Variables below are referenced by the role task files under `tasks/`. Defaults are defined in `defaults/main.yml`.

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `satellite_install_pre_check` | When `true`, only run the preliminary validation tasks and skip the remaining install/import tasks | ❌ | `false` |
| `satellite_install_force_reinstall` | When `true`, rerun the Satellite installer even if Satellite services already appear to be installed | ❌ | `false` |
| `satellite_install_deployment_version` | Target Satellite version validated during checks and used in RHSM repo names | ❌ | `"6.19"` |
| `satellite_install_location` | Logical location/name for the Satellite deployment | ✅ | `""` |
| `satellite_install_size_profile` | Selected tuning profile name. When set, `templates/tuning_profile.j2` uses this directly. | ❌ | `"default"` |
| `satellite_install_min_memory_size` | Minimum required memory in MB (`ansible_facts["memtotal_mb"]`) | ❌ | `20480` |
| `satellite_install_min_cpu_count` | Minimum required vCPU count and input to the Satellite tuning profile template | ❌ | `4` |
| `satellite_install_rhn_connected` | When `true`, validate RHSM credentials during preliminary checks | ❌ | `false` |
| `satellite_install_rhn_org_id` | RHSM organization ID used for host registration | ✅* | `""` |
| `satellite_install_admin_username` | Satellite admin username used when importing a subscription manifest | ❌ | `"admin"` |
| `satellite_install_admin_password` | Password to set for the Satellite admin user after installation | ✅ | `""` |
| `satellite_install_rhn_activation_key` | RHSM activation key used for host registration | ✅* | `""` |
| `satellite_install_manifest_file` | Manifest filename written by bootstrap when a manifest is uploaded through preflight | ❌ | `""` |
| `satellite_install_manifest_path` | Local path to a Red Hat Satellite subscription manifest zip to upload after installation | ❌ | `""` |
| `satellite_install_manifest_organization` | Satellite organization that receives the uploaded manifest. Falls back to Satellite config organization when unset. | ❌ | `""` |
| `satellite_install_rhn_repos` | RHSM repository IDs enabled after registration | ❌ | See `defaults/main.yml` |
| `satellite_install_timezone` | System timezone set before RHSM registration | ❌ | `"UTC"` |
| `satellite_install_proxy_server` | Optional RHSM proxy hostname passed to `redhat_subscription` | ❌ | `""` |
| `satellite_install_proxy_port` | Optional RHSM proxy port passed to `redhat_subscription` | ❌ | `""` |
| `satellite_install_proxy_scheme` | Optional RHSM proxy scheme (`http` or `https`) passed to `redhat_subscription` | ❌ | `""` |
| `satellite_install_selinux_state` | SELinux state applied after package updates | ❌ | `"enforcing"` |
| `satellite_install_vg_name` | LVM volume group name for Satellite storage | ❌ | `"satellite"` |
| `satellite_install_req_dirs` | List of logical volumes to create and mount; each item requires `lv_name`, `lv_size`, and `mount_point` | ❌† | `/var/lib/pulp` and `/var/lib/pgsql` defaults |
| `satellite_install_data_disk_min_size` | Minimum disk size used when auto-selecting an unpartitioned data disk | ❌ | `"10G"` |
| `satellite_install_data_device_name` | Disk device basename override when auto-discovery finds multiple suitable disks | ❌ | `""` |
| `satellite_install_data_device` | Base device path prefix joined with the selected disk (for example `/dev/sdb`) | ❌ | `"/dev"` |
| `satellite_install_packages` | Package list installed before Satellite configuration | ❌ | See `defaults/main.yml` |
| `satellite_install_dns_device` | NetworkManager connection name updated by the DNS configuration tasks | ✅‡ | `""` |
| `satellite_install_dns_servers` | DNS servers applied via NetworkManager and `/etc/resolv.conf` | ❌ | `[]` |
| `satellite_install_dns_search` | DNS search domains applied via NetworkManager | ❌ | `[]` |
| `satellite_install_size` | List of tuning tiers (`name`, `min_hosts`, `max_hosts`, `min_ram`, `min_cpu`) used by `templates/tuning_profile.j2` to select the `satellite-installer --tuning` profile. Must include tier names `default`, `medium`, `large`, `extra-large`, and `extra-extra-large`. | ❌§ | See `defaults/main.yml` |

> **Notes:**
> \* Required when `satellite_install_rhn_connected: true`
>
> † Required when configuring Satellite storage; each entry in `satellite_install_req_dirs` must define `lv_name`, `lv_size`, and `mount_point`.
>
> ‡ Required when `satellite_install_dns_servers` or `satellite_install_dns_search` is set.
>
> § Required for a full install run (`satellite_install_pre_check: false`) so `install_satellite.yml` can render the tuning profile.

See `defaults/main.yml` for default values and structure.

## 🚀 Role Usage

Define the Satellite installation configuration in your playbook or inventory using the variables above.

### Example 1: Run validation checks only
```yaml
- name: ADO | Install Satellite
  hosts: all
  gather_facts: true
  roles:
    - role: infra.automation_development_office.satellite_install
```

### Example 2: Run a connected Satellite install
```yaml
- hosts: satellite_hosts
  become: true
  vars:
    satellite_install_pre_check: false
    satellite_install_deployment_version: "6.19"
    satellite_install_location: AWS
    satellite_install_rhn_connected: true
    satellite_install_rhn_org_id: "12345678"
    satellite_install_rhn_activation_key: "satellite-rhel9"
    satellite_install_admin_password: "StrongAdminPassword123!"
    satellite_install_manifest_path: "{{ playbook_dir }}/../../files/satellite-manifest.zip"
    satellite_install_manifest_organization: "Default Organization"
    satellite_install_timezone: America/New_York
    satellite_install_size_profile: default
    satellite_install_vg_name: satellite
    satellite_install_data_device: /dev
    satellite_install_data_disk_min_size: "500G"
    satellite_install_req_dirs:
      - mount_point: /var/lib/pulp
        lv_name: lv_rhspulp
        lv_size: 300g
      - mount_point: /var/lib/pgsql
        lv_name: lv_pgsql
        lv_size: 20g
    satellite_install_dns_device: ens192
    satellite_install_dns_servers:
      - 10.0.0.10
      - 10.0.0.11
    satellite_install_dns_search:
      - example.com
  roles:
    - role: infra.automation_development_office.satellite_install
```

## 🔧 Tasks Overview

- **Main Task File** (`main.yml`):
  - Always runs `preliminary_check.yml` first for validation.
  - When `pre_check: false`, continues with conditional task imports for RHSM subscription, patching, storage configuration, package installation, firewall configuration, certificate preparation, DNS configuration, Satellite installation, and optional manifest import.
- **Preliminary Check** (`preliminary_check.yml`):
  - Validates RHEL version (9+), required inputs, and system resources.
  - Ensures `grubby` is installed, removes `ipv6.disable=1` kernel arguments, adds `ipv6.disable=0` if missing.
  - Sets SELinux to permissive and may trigger reboots via handlers.
- **RHSM Subscribe** (`rhsm_subscribe.yml`):
  - Registers the host with RHSM using provided organization ID and activation key.
  - Enables specified repositories for Satellite installation.
- **Patch** (`patch.yml`):
  - Applies system patches and updates SELinux state.
- **Storage Config** (`storage_config.yml`):
  - Configures logical volumes and mount points for Satellite data directories.
  - Auto-detects suitable disks or uses explicit device specifications.
- **Install Packages** (`install_packages.yml`):
  - Installs Satellite and related packages from configured repositories.
- **Configure Firewall** (`configure_firewall.yml`):
  - Updates firewall rules for Satellite services.
- **Prep Custom Certificates** (`prep-custom-certs.yml`):
  - Prepares custom certificates using the `openssl.cnf.j2` template.
- **DNS Config** (`dns_config.yml`):
  - Updates DNS settings via NetworkManager and resolv.conf.
- **Satellite Install** (`install_satellite.yml`):
  - Runs `satellite-installer --scenario satellite` and applies tuning/profile settings.
- **Manifest Import** (`import_manifest.yml`):
  - Optionally uploads a Red Hat Satellite subscription manifest zip with `hammer subscription upload` when `satellite_install_manifest_path` is defined.

## 🧪 Role Molecule Testing

This role no longer includes a dedicated Molecule scenario or platform-specific Molecule playbooks.

> Molecule tests for `satellite_install` have been removed from the repository.

## 📁 Role Structure

```text
roles/
└─ satellite_install/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ handlers/
   │  └─ main.yml
   ├─ meta/
   │  ├─ argument_specs.yml
   │  └─ main.yml
   ├─ tasks/
   │  ├─ configure_firewall.yml
   │  ├─ dns_config.yml
   │  ├─ install_packages.yml
   │  ├─ install_satellite.yml
   │  ├─ import_manifest.yml
   │  ├─ main.yml
   │  ├─ patch.yml
   │  ├─ prep-custom-certs.yml
   │  ├─ preliminary_check.yml
   │  ├─ rhsm_subscribe.yml
   │  └─ storage_config.yml
   ├─ templates/
   │  ├─ openssl.cnf.j2
   │  ├─ resolv.conf.j2
   │  └─ tuning_profile.j2
   ├─ tests/
   │  └─ inventory
   └─ vars/
      └─ main.yml
```
