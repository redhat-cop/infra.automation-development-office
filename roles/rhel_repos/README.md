# Role: infra.automation_development_office.rhel_repos

Manages repository enable and disable operations on Red Hat Enterprise Linux systems.

## Role Author

- Jeff Radabaugh
- Automation Development Office

## ✅ Role Requirements

- Target host OS family: `RedHat`
- Ansible with facts enabled (uses `ansible_os_family` and `ansible_pkg_mgr`)
- `community.general` collection for `rhsm_repository`
- Privileged access to manage repositories

Repository inputs are comma-separated strings today (for example,
`repos_to_enable: "repo1,repo2"`). YAML list input is planned but not
implemented yet.

> **Migration:** This role was renamed from `platform_repos`. Use
> `infra.automation_development_office.rhel_repos` and `rhel_repos_*` variables instead of
> `ado.platform.repos` / `platform_repos_*`.

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `repos_action` | Action to perform: `enable` or `disable`. Required. |
| `repos_to_enable` | Comma-separated repository IDs to enable. Required when `repos_action` is `enable`. |
| `repos_to_disable` | Comma-separated repository IDs to disable. Required when `repos_action` is `disable`. |
| `repos_enable_method` | Enable method: `rhsm_repository`, `yum_repository`, or `file-edit`. Default: auto-detect. |
| `repos_disable_method` | Disable method: `rhsm_repository`, `yum_repository`, or `file-edit`. Default: auto-detect. |
| `rhel_repos_backup_files` | Backup repo files when using the `file-edit` method. Default: `true`. |
| `rhel_repos_clean_cache` | Run package manager cache cleanup after the action. Default: `false`. |

Legacy vars `repos_backup_files` and `repos_clean_cache` are still honored in
task logic.

## 🚀 Role Usage

`tasks/main.yml` dispatches based on `repos_action`:

- `repos_action: "enable"` runs `tasks/enable_repo.yml` (requires `repos_to_enable`)
- `repos_action: "disable"` runs `tasks/disable_repo.yml` (requires `repos_to_disable`)

When no method is set, the role uses `rhsm_repository` if `subscription-manager`
is available; otherwise it uses `yum_repository`. Use `file-edit` only when
explicitly requested.

### Enable repositories (auto method)

```yaml
- name: Enable repositories
  hosts: rhel_servers
  gather_facts: true
  vars:
    repos_action: "enable"
    repos_to_enable: "rhel-8-for-x86_64-appstream-rpms,rhel-8-for-x86_64-baseos-rpms"
  roles:
    - role: infra.automation_development_office.rhel_repos
```

### Disable repositories (auto method)

```yaml
- name: Disable repositories
  hosts: rhel_servers
  gather_facts: true
  vars:
    repos_action: "disable"
    repos_to_disable: "rhel-8-for-x86_64-appstream-rpms,rhel-8-for-x86_64-baseos-rpms"
  roles:
    - role: infra.automation_development_office.rhel_repos
```

### Enable with explicit method and cleanup

```yaml
- name: Enable repositories with RHSM
  hosts: rhel_servers
  gather_facts: true
  vars:
    repos_action: "enable"
    repos_to_enable: "rhel-8-for-x86_64-supplementary-rpms"
    repos_enable_method: "rhsm_repository"
    rhel_repos_clean_cache: true
  roles:
    - role: infra.automation_development_office.rhel_repos
```

### Disable with file-edit fallback

```yaml
- name: Disable repositories with file editing
  hosts: rhel_servers
  gather_facts: true
  vars:
    repos_action: "disable"
    repos_to_disable: "epel,epel-modular"
    repos_disable_method: "file-edit"
    rhel_repos_backup_files: true
  roles:
    - role: infra.automation_development_office.rhel_repos
```

## 🧪 Role Molecule Testing

Automated Molecule testing uses UBI 8 and UBI 9 Podman containers in
`extensions/molecule/integration_rhel_repos_default`.

| Instance | Image | Coverage |
|----------|-------|----------|
| `rhel-repos-el8` | UBI 8 | `file-edit` enable/disable |
| `rhel-repos-el9` | UBI 9 | `file-edit` enable/disable and `yum_repository` enable |

UBI 8 uses Python 3.11 for Ansible connectivity. The `yum_repository` method is
exercised on UBI 9 only because Python 3.11 on UBI 8 lacks `python3-dnf`
bindings.

The `integration_rhel_repos_rhsm` scenario is manual-only (excluded from PR CI)
and requires a registered RHEL host for `rhsm_repository` testing.

Install the collection and ensure Podman is available, then run locally:

```bash
cd /path/to/your/git/checkout/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix containers.podman community.general \
  --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

pip install 'molecule-plugins[podman]'

cd extensions/molecule
molecule test -s integration_rhel_repos_default
```

Shared stage playbooks live under `extensions/molecule/utils/playbooks/`:

- `rhel_repos_prepare_default.yml`
- `rhel_repos_converge_default.yml`
- `rhel_repos_verify_default.yml`
- `rhel_repos_destroy_default.yml`

The role-level `tests/` directory is legacy skeleton content and is not used by
the extension Molecule CI flow.

## 📁 Role Structure

```text
roles/
└─ rhel_repos/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ handlers/
   │  └─ main.yml
   ├─ meta/
   │  └─ main.yml
   ├─ tasks/
   │  ├─ main.yml
   │  ├─ enable_repo.yml
   │  └─ disable_repo.yml
   ├─ tests/
   │  ├─ inventory
   │  └─ test.yml
   └─ vars/
      └─ main.yml
```
