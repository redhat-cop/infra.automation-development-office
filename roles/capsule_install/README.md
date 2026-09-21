# Role: `capsule_install`

This Ansible role prepares and installs a Red Hat Satellite Capsule host on supported RHEL systems.

It validates OS, CPU, memory, location, and Capsule version before install, supports a safe `pre_check` mode for validation-only runs, and can register the Capsule host to Satellite using a generated registration command.

> **⚠️ Note:**
> This role requires root privileges for system modifications, package installation, and configuration changes. Ensure your target hosts are accessible with privileged access (`become: true`).

## Role Author

- Automation Development Office (automation-development-office@redhat.com)

## ✅ Role Requirements

- Ansible >= 2.9
- Target hosts: Supported Red Hat Enterprise Linux (RHEL 9 or later)
- Privileged access on the target host (`become: true`)
- Required collections:
  - `ansible.posix`
  - `community.general`
  - `redhat.satellite`
- Upstream Satellite server FQDN, organization ID, activation key, and admin credentials for Capsule registration

## 📦 Role Variables

Variables below are referenced by the role task files under `tasks/`. Defaults are defined in `defaults/main.yml`.

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `capsule_install_pre_check` | When `true`, only run the preliminary validation tasks and skip the remaining install tasks | ❌ | `false` |
| `capsule_install_os_version` | RHEL major version referenced in OS validation messages | ❌ | `"9"` |
| `capsule_install_deployment_version` | Target Capsule version used in RHSM repo names | ❌ | `"6.19"` |
| `capsule_install_location` | Logical location/name for the Capsule deployment | ✅ | `""` |
| `capsule_install_min_memory_size` | Minimum required memory in MB (`ansible_facts["memtotal_mb"]`) | ❌ | `12288` |
| `capsule_install_min_cpu_count` | Minimum required vCPU count (`ansible_facts["processor_vcpus"]`) | ❌ | `4` |
| `capsule_install_org_id` | Organization ID used for Capsule registration | ✅ | unset |
| `capsule_install_activation_key` | Activation key used for Capsule registration | ✅ | unset |
| `capsule_install_satellite_fqdn` | FQDN of the upstream Satellite server | ✅* | unset |
| `capsule_install_admin_username` | Satellite admin username used to generate the registration command | ❌ | `"admin"` |
| `capsule_install_admin_password` | Satellite admin password used to generate the registration command | ✅* | unset |
| `capsule_install_timezone` | System timezone set before registration | ❌ | `"UTC"` |
| `capsule_install_setup_insights` | Whether to configure Red Hat Insights during Capsule registration | ❌ | `false` |
| `capsule_install_rhn_repos` | RHSM repository IDs enabled after registration | ❌ | See `defaults/main.yml` |
| `capsule_install_scenario` | Satellite installer scenario for Capsule deployment | ❌ | `"capsule"` |
| `capsule_install_selinux_state` | SELinux state applied after package updates | ❌ | `"enforcing"` |
| `capsule_install_vg_name` | LVM volume group name for Capsule storage | ❌ | `"capsule"` |
| `capsule_install_req_dirs` | List of logical volumes to create and mount; each item requires `lv_name`, `lv_size`, and `mount_point` | ❌ | `/var/lib/pulp` and `/var/lib/pgsql` defaults |
| `capsule_install_data_disk_min_size` | Minimum disk size in GB used when validating storage requirements | ❌ | `500` |
| `capsule_install_data_device` | Base device path prefix joined with the selected disk | ❌ | `"/dev"` |
| `capsule_install_packages` | Package list installed for Capsule deployment | ❌ | See `defaults/main.yml` |
| `capsule_install_dns_device` | NetworkManager connection name updated by the DNS configuration tasks | ✅‡ | unset |
| `capsule_install_dns_servers` | DNS servers applied via NetworkManager and `/etc/resolv.conf` | ❌ | unset |
| `capsule_install_dns_search` | DNS search domains applied via NetworkManager | ❌ | unset |
| `capsule_install_certs` | Certificate filenames fetched from `/root/certs/` on the Capsule host and copied to Satellite before `capsule-certs-generate` | ✅* | unset |
| `capsule_install_satellite_haproxy` | Enable load-balanced Capsule registration settings | ❌ | `false` |
| `capsule_install_satellite_loadbalancer_ports` | Firewall/service ports used by load-balanced deployments | ❌ | See `defaults/main.yml` |
| `capsule_install_installer_options` | Installer flags for standard Capsule deployment | ❌ | See `defaults/main.yml` |
| `capsule_install_loadbalanced_options` | Installer flags for load-balanced Capsule deployment | ❌ | See `defaults/main.yml` |
| `capsule_install_sync_wait_time` | Maximum wait time for synchronization operations | ❌ | `86400` |
| `capsule_install_lifecycle_environments` | Lifecycle environments assigned to the Capsule smart proxy | ❌ | `[]` |
| `capsule_install_loadbalancer_fqdn` | FQDN of the Capsule load balancer host | ❌* | `""` |
| `capsule_install_loadbalancer_activation_key` | Activation key used to register the load balancer host | ❌* | `""` |

> **Notes:**
> \* Required when `capsule_install_pre_check: false` so `rhsm_subscribe.yml` can register the Capsule host and `generate_cap_custom_cert.yml` can build the Capsule cert tarball.
> \* Required when `capsule_install_satellite_haproxy: true` for `configure_firewall.yml` load-balancer ports and `haproxy.yml` setup.
> ‡ Required when `capsule_install_dns_servers` or `capsule_install_dns_search` is set.

See `defaults/main.yml` for default values and structure.

## 🚀 Role Usage

Define the Capsule installation configuration in your playbook or inventory using the variables above.

### Example 1: Run validation checks only

```yaml
- name: ADO | Validate Capsule host
  hosts: capsule_hosts
  become: true
  gather_facts: true
  vars:
    capsule_install_pre_check: true
    capsule_install_os_version: "9"
    capsule_install_org_id: "12345678"
    capsule_install_activation_key: "capsule-rhel9"
    capsule_install_location: AWS
  roles:
    - role: infra.ado.capsule_install
```

### Example 2: Run preliminary check and Capsule registration

```yaml
- name: ADO | Install Capsule
  hosts: capsule_hosts
  become: true
  gather_facts: true
  vars:
    capsule_install_pre_check: false
    capsule_install_os_version: "9"
    capsule_install_deployment_version: "6.19"
    capsule_install_org_id: "12345678"
    capsule_install_activation_key: "capsule-rhel9"
    capsule_install_location: AWS
    capsule_install_satellite_fqdn: satellite.example.com
    capsule_install_admin_password: "StrongAdminPassword123!"
    capsule_install_dns_device: ens192
    capsule_install_dns_servers:
      - 10.0.0.10
      - 10.0.0.11
    capsule_install_dns_search:
      - example.com
    capsule_install_certs:
      - "{{ ansible_fqdn }}_cert.pem"
      - "{{ ansible_fqdn }}_cert_key.pem"
      - ca_cert_bundle.pem
  roles:
    - role: infra.ado.capsule_install
```

## 🧪 Role Molecule Testing

Use the extension integration scenario at
`extensions/molecule/integration_capsule_install`.

Install the collection and dependencies before running locally:

```bash
cd /path/to/your/git/checkout/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"
```

Run the integration scenario:

```bash
cd extensions/molecule
molecule test -s integration_capsule_install
```

By default, `converge` is offline-only because live Capsule installation requires
Satellite credentials. `verify` checks task file layout, `main.yml` wiring, HAProxy
template presence, and README format via `scripts/verify_readme.py`.

## 🔧 Tasks Overview

- **Main Task File** (`main.yml`):
  - Always runs `preliminary_check.yml` first for validation.
  - When `capsule_install_pre_check: false`, continues with `rhsm_subscribe.yml`, package updates via `satellite_install` `patch.yml` using `capsule_install_selinux_state`, storage configuration via `satellite_install` `storage_config`, then `install_packages.yml`, `configure_firewall.yml`, `dns_config.yml`, `generate_cap_custom_cert.yml`, `install_capsule.yml`, `post_config.yml`, `sync_capsule.yml`, and conditional `haproxy.yml`.
- **Install Packages** (`install_packages.yml`):
  - Installs Capsule packages when `satellite-capsule` is not already present.
- **Configure Firewall** (`configure_firewall.yml`):
  - Starts and enables `firewalld`, and allows the `RH-Satellite-6-capsule` service.
  - When `capsule_install_satellite_haproxy` is enabled, opens `capsule_install_satellite_loadbalancer_ports` on `capsule_install_loadbalancer_fqdn`.
- **DNS Config** (`dns_config.yml`):
  - Ensures `/etc/hosts` has the Capsule short name and FQDN.
  - When DNS variables are set, updates NetworkManager and renders `templates/resolv.conf.j2`.
- **Generate Custom Capsule Certificate** (`generate_cap_custom_cert.yml`):
  - Copies `capsule_install_certs` from the Capsule host to Satellite, runs `capsule-certs-generate`, and returns the cert tarball to the Capsule.
  - Sets `capsule_install_foreman_proxy_oauth_consumer_key` and `capsule_install_foreman_proxy_oauth_consumer_secret` from the generator output for later installer options.
- **Install Capsule** (`install_capsule.yml`):
  - Checks whether Capsule services are already running.
  - Runs `satellite-installer` with `capsule_install_scenario` and `capsule_install_installer_options`, or load-balanced options when `capsule_install_satellite_haproxy` is enabled.
- **Post Config** (`post_config.yml`):
  - Updates the Capsule smart proxy organization, location, and lifecycle environments on Satellite using `redhat.satellite.smart_proxy`.
- **Sync Capsule** (`sync_capsule.yml`):
  - Triggers Capsule content synchronization through the Satellite API and waits for completion.
- **HAProxy** (`haproxy.yml`):
  - Configures a load balancer host when `capsule_install_satellite_haproxy` is enabled, including registration, package install, `templates/haproxy.cfg.j2` deployment, and service enablement.
- **Preliminary Check** (`preliminary_check.yml`):
  - Validates RHEL version (9+), required inputs, and system resources.
  - Ensures `grubby` is installed, removes `ipv6.disable=1` kernel arguments, adds `ipv6.disable=0` if missing.
  - Sets SELinux to permissive and may trigger reboots via handlers.
- **RHSM Subscribe** (`rhsm_subscribe.yml`):
  - Sets the system timezone and restarts `crond`.
  - Removes non-Red Hat repository files when the Capsule is not already registered.
  - Generates a Satellite registration command with `redhat.satellite.registration_command`.
  - Registers the host and enables repositories from `capsule_install_rhn_repos`.

## 🔄 Handlers

- **Reboot node** (`reboot system`):
  - Reboots the host after kernel argument or SELinux changes, with a 600-second timeout.

## 📁 Role Structure

```text
roles/
└── capsule_install/
    ├── README.md
    ├── defaults/
    │   └── main.yml
    ├── handlers/
    │   └── main.yml
    ├── meta/
    │   ├── argument_specs.yml
    │   └── main.yml
    ├── tasks/
    │   ├── main.yml
    │   ├── preliminary_check.yml
    │   ├── rhsm_subscribe.yml
    │   ├── install_packages.yml
    │   ├── configure_firewall.yml
    │   ├── dns_config.yml
    │   ├── generate_cap_custom_cert.yml
    │   ├── install_capsule.yml
    │   ├── post_config.yml
    │   ├── sync_capsule.yml
    │   └── haproxy.yml
    ├── templates/
    │   ├── haproxy.cfg.j2
    │   └── resolv.conf.j2
    ├── tests/
    │   └── inventory
    └── vars/
        └── main.yml
```
