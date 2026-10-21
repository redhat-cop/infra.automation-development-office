# Role: `satellite_config`

This Ansible role configures a Red Hat Satellite server after installation.

It applies Satellite settings, manages subscription manifests, enables Red Hat repository sets, syncs content, creates lifecycle environments and content views, and supports third-party product and repository uploads.

> **⚠️ Note:**
> This role requires privileged access on the Satellite host for manifest copy, certificate, and Hammer operations. Satellite API credentials with sufficient permissions are required for all configuration tasks.

## Role Author

- Automation Development Office (automation-development-office@redhat.com)

## ✅ Role Requirements

- Ansible >= 2.14
- Target hosts: Red Hat Satellite server with a completed installation
- Privileged access on the target host (`become: true`) where noted in tasks
- Required collections:
  - `redhat.satellite`
  - `community.general`
- Valid Satellite administrator credentials
- Subscription manifest source file (for connected deployments using `manifest.yml`)
- Upstream Satellite credentials and FQDN (when `satellite_config_rhn_connected: false`)

## 📦 Role Variables

Variables below are referenced by the role task files under `tasks/`. Defaults are defined in `defaults/main.yml` where noted.

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `satellite_config_username` | Satellite administrator username for API and Hammer calls | ✅ | Not defined in role defaults |
| `satellite_config_password` | Satellite administrator password for API and Hammer calls | ✅ | Not defined in role defaults |
| `satellite_config_admin_password` | Satellite admin account password. Can be used to update admin's password | ✅ | Not defined in role defaults |
| `satellite_config_server_url` | Satellite server URL | ❌ | `"https://{{ ansible_fqdn }}"` |
| `satellite_config_organization` | Satellite organization name or label | ✅ | Not defined in role defaults |
| `satellite_config_validate_certs` | Whether to validate Satellite TLS certificates | ❌ | Not defined in role defaults |
| `satellite_config_upload_manifest` | When `true`, include the manifest tasks in the role flow to copy, upload, and refresh the subscription manifest | ❌ | `false` |
| `satellite_config_rhn_connected` | When `true`, configure connected Satellite proxy settings; when `false`, configure disconnected CDN sync | ❌ | `true` |
| `satellite_config_settings` | List of Satellite settings to apply; each item requires `name` and `value`. On Satellite 6.19+, `host_tasks_workers_pool_size` is omitted automatically (removed upstream). | ❌ | See `defaults/main.yml` |
| `satellite_config_proxy_server` | HTTP proxy hostname for connected Satellite content sync | ❌* | Not defined in role defaults |
| `satellite_config_proxy_port` | HTTP proxy port for connected Satellite content sync | ❌* | Not defined in role defaults |
| `satellite_config_proxy_scheme` | HTTP proxy scheme (`http` or `https`) for connected Satellite content sync | ❌* | Not defined in role defaults |
| `satellite_config_connected_fqdn` | FQDN of the upstream connected Satellite used for disconnected CDN configuration | ✅† | Not defined in role defaults |
| `satellite_config_upstream_admin_username` | Administrator username for the upstream connected Satellite | ✅† | Not defined in role defaults |
| `satellite_config_upstream_admin_password` | Administrator password for the upstream connected Satellite | ✅† | Not defined in role defaults |
| `satellite_config_manifest_file` | Manifest filename used by bootstrap/configure; role derives source/destination paths when unset | ❌ | `""` |
| `satellite_config_manifest_src` | Controller-side path to the subscription manifest file copied to Satellite | ✅‡ | `""` |
| `satellite_config_manifest_path` | Destination path on the Satellite host for the manifest file | ✅‡ | `""` |
| `satellite_config_satellite_deployment_version` | Satellite version interpolated into default Red Hat repository set labels | ❌ | `"6.19"` |
| `satellite_config_satellite_redhat_repos` | Red Hat repository sets to enable; each item supports `label`, optional `repos`, and optional `all` | ❌ | See `defaults/main.yml` |
| `satellite_config_gpg_key_files` | Role-relative GPG key files copied to the Satellite host | ❌ | See `defaults/main.yml` |
| `satellite_config_custom_repo_dest` | Destination directory for extracted custom repository content | ✅§ | Not defined in role defaults |
| `satellite_config_custom_repo_src` | Source directory containing custom repository archives | ✅§ | Not defined in role defaults |
| `satellite_config_custom_repo_files` | Archive filenames extracted from `satellite_config_custom_repo_src` | ✅§ | Not defined in role defaults |
| `satellite_config_custom_repos` | Custom repository upload definitions passed to `subelements('files')`; each item requires `product`, `repository`, and `files` | ✅§ | Not defined in role defaults |
| `satellite_config_repo_sync_wait_time` | Async timeout in seconds while waiting for repository sync jobs to finish | ❌ | See `defaults/main.yml` |
| `satellite_config_lifecycle_envs` | Lifecycle environments to create; each item requires `env_name` and `prior` | ✅¶ | Not defined in role defaults |
| `satellite_config_content_views` | Content views to publish and promote; each item requires `name` and `lifecycle_environments` | ✅¶ | Not defined in role defaults |

> **Notes:**
> \* Required when `satellite_config_rhn_connected: true` and configuring Satellite content proxy settings.
>
> † Required when `satellite_config_rhn_connected: false` for disconnected CDN configuration.
>
> ‡ Required when running `manifest.yml` to upload or refresh the subscription manifest.
>
> § Required when uploading custom third-party repository content.
>
> ¶ Required when running the corresponding lifecycle environment or content view tasks.

The bootstrap generator can populate `satellite_config_username`,
`satellite_config_password`, and `satellite_config_admin_password` from the
Satellite service account fields in the UI or from
`bootstrap_generate_env_vars_satellite_service_account_*` CLI variables.

See `defaults/main.yml` for default values and structure.

## 🚀 Role Usage

Define the Satellite configuration in your playbook or inventory using the variables above. Run this role after `satellite_install` on a host where Satellite is installed and reachable.

### Example 1: Configure a connected Satellite server
```yaml
- name: ADO | Configure Satellite
  hosts: all
  gather_facts: true
  roles:
    - role: infra.automation_development_office.satellite_config
```

### Example 2: Configure a disconnected Satellite with upstream CDN sync
```yaml
- hosts: satellite_hosts
  become: true
  vars:
    satellite_config_username: admin
    satellite_config_password: "{{ vault_satellite_admin_password }}"
    satellite_config_admin_password: "{{ vault_satellite_admin_password }}"
    satellite_config_organization: Example_Org
    satellite_config_validate_certs: false
    satellite_config_rhn_connected: false
    satellite_config_connected_fqdn: satellite-upstream.example.com
    satellite_config_upstream_admin_username: admin
    satellite_config_upstream_admin_password: "{{ vault_upstream_satellite_password }}"
    satellite_config_satellite_deployment_version: "6.16"
    satellite_config_manifest_src: files/manifest.zip
    satellite_config_manifest_path: /root/manifest.zip
  roles:
    - role: infra.automation_development_office.satellite_config
```

## 🔧 Tasks Overview

- **Main Task File** (`main.yml`):
  - Runs configuration tasks in order: settings, manifest, repository enablement, third-party products, repository sync, lifecycle environments, and content views.
- **Settings Config** (`settings.yml`):
  - Applies Satellite settings, configures proxy objects for connected deployments, and configures disconnected CDN sync from an upstream Satellite.
- **Manifest Config** (`manifest.yml`):
  - Copies, removes, uploads, and refreshes the subscription manifest.
- **Enable Repos** (`enable_repos.yml`):
  - Ensures `/var/lib/pulp` ownership and enables configured Red Hat repository sets.
- **Third Party Products** (`third_party_products.yml`):
  - Copies GPG keys, includes content credential and repository roles, and uploads custom repository content.
- **Repo Sync** (`repo_sync.yml`):
  - Discovers enabled products and synchronizes all repositories asynchronously.

## 🧪 Role Molecule Testing

This role does not include a dedicated Molecule scenario or platform-specific Molecule playbooks.

> Molecule tests for `satellite_config` have not been added to the repository.

## 📁 Role Structure

```text
roles/
└─ satellite_config/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ files/
   │  ├─ .keep
   │  └─ RPM-GPG-KEY-EPEL-9
   ├─ meta/
   │  ├─ argument_specs.yml
   │  └─ main.yml
   └─ tasks/
      ├─ content_views.yml
      ├─ enable_repos.yml
      ├─ lifecycle_envs.yml
      ├─ main.yml
      ├─ manifest.yml
      ├─ repo_sync.yml
      ├─ settings.yml
      └─ third_party_products.yml
```
