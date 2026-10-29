# Role: `infra.automation_development_office.rhel_patching`

Comprehensive patching for Red Hat Enterprise Linux (RHEL) servers.

Handles package updates, kernel management, system reboots, and patching statistics.
Includes safety checks for supported RHEL versions.

## Role Author

- Jeff Radabaugh
- Automation Development Office

## ✅ Role Requirements

- Red Hat Enterprise Linux 8 or 9 (RHEL 6 and earlier are not supported)
- SSH access with sudo privileges. The generated patch job enables privilege escalation (`become`).
- Package management utilities (`dnf`) available on target systems

> **RHEL 7 is not supported.** The role fails on RHEL 7 and earlier hosts. Running
> it on unsupported versions is at your own risk and is not validated by automated
> testing.

## 📦 Role Variables

| Variable | Description |
|---------|-------------|
| `rhel_patching_package_cleanup` | Whether to clean up old kernels from `/boot`. Default: `false`. |
| `rhel_patching_versions` | Version specification for package updates. Default: `latest`. |
| `rhel_patching_update_cache` | Whether to update the package cache before patching. Default: `false`. |
| `rhel_patching_exclude_list` | Packages to exclude from updates. Default: `[]`. |
| `rhel_patching_disable_repos` | Repositories to disable during patching. Default: `[]`. |
| `rhel_patching_skip_broken` | Whether to skip broken dependencies. Default: `false`. |
| `rhel_patching_package_list` | Specific packages to update. Default: `["*"]`. |
| `rhel_patching_check_mountpoints` | Whether to check server mountpoints before patching. Default: not set in role defaults. |
| `rhel_patching_reboot` | Whether to reboot servers after patching. Default: `false`. |

## 🚀 Role Usage

### Basic patching (no reboot)

```yaml
- name: Patch RHEL servers
  hosts: rhel_servers
  gather_facts: true
  become: true
  vars:
    rhel_patching_update_cache: true
    rhel_patching_package_cleanup: true
  roles:
    - role: infra.automation_development_office.rhel_patching
```

### Patching with forced restart

```yaml
- name: Patch and restart RHEL servers
  hosts: rhel_servers
  gather_facts: true
  become: true
  vars:
    rhel_patching_reboot: true
    rhel_patching_update_cache: true
    rhel_patching_package_cleanup: true
  roles:
    - role: infra.automation_development_office.rhel_patching
```

### Selective package patching

```yaml
- name: Update specific packages
  hosts: rhel_servers
  gather_facts: true
  become: true
  vars:
    rhel_patching_package_list:
      - httpd
      - nginx
      - openssh
    rhel_patching_versions: latest
    rhel_patching_exclude_list: []
  roles:
    - role: infra.automation_development_office.rhel_patching
```

### Advanced patching configuration

```yaml
- name: Advanced patching with custom settings
  hosts: rhel_servers
  gather_facts: true
  become: true
  vars:
    rhel_patching_reboot: true
    rhel_patching_update_cache: true
    rhel_patching_package_cleanup: true
    rhel_patching_exclude_list:
      - kernel-debug
      - custom-app
    rhel_patching_disable_repos:
      - epel-testing
    rhel_patching_skip_broken: true
  roles:
    - role: infra.automation_development_office.rhel_patching
```

### Behavior notes

- Validates supported RHEL versions (8 and 9 only)
- Gathers repository and package update information before patching
- Optionally updates the package cache, removes old kernels, and applies updates
- Reboots when `rhel_patching_reboot` is enabled and updates changed the system
- Reports pre- and post-patch kernel versions, uptime, and update counts

## 🧪 Role Molecule Testing

Automated Molecule testing covers RHEL 8 and 9 using UBI 8 and UBI 9 Podman
containers only.

Use the extension integration scenario at
`extensions/molecule/integration_rhel_patching`.

Install the collection and ensure Podman is available, then run locally:

```bash
cd /path/to/your/git/checkout/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix containers.podman community.general \
  --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

pip install 'molecule-plugins[podman]'

cd extensions/molecule
molecule test -s integration_rhel_patching
```

The scenario starts UBI 8 and UBI 9 Podman containers. UBI 9 runs the role
directly; UBI 8 uses `command`-based `dnf` CLI tasks in the Molecule playbooks
because Python 3.11 on UBI 8 lacks `python3-dnf` bindings. Converge first runs
discovery-only mode (`rhel_patching_package_list: []`), then applies a targeted
update to the `tar` package on each host.

## 📁 Role Structure

```text
roles/
└─ rhel_patching/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ handlers/
   │  └─ main.yml
   ├─ meta/
   │  └─ main.yml
   ├─ tasks/
   │  ├─ main.yml
   │  ├─ package_facts.yml
   │  ├─ patch.yml
   │  ├─ reboot.yml
   │  ├─ recon.yml
   │  └─ repo_facts.yml
   ├─ templates/
   │  └─ report.txt.j2
   └─ vars/
      └─ main.yml
```
