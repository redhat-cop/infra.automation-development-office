# Role: infra.ado.bootstrap_generate_env_vars

Generate environment group variables and vault files used by the ADO bootstrap
playbook repository.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- `env` set to the target environment
- A vault password file when encrypted vault files are enabled
- Optional preflight JSON from the ADO preflight UI or CLI
- Write access to the bootstrap playbook repository working tree

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `env` | Target environment directory under `group_vars/all`. |
| `preflight_json` | Optional JSON file containing UI or CLI preflight answers. |
| `generate_env_vars_base_dir` | Base directory for generated environment variables. |
| `generate_env_vars_create_dirs` | Creates bootstrap repository directories when true. |
| `generate_env_vars_encrypt_vault_files` | Encrypts generated vault files when true. |
| `generate_env_vars_components` | Component list for generated `vars_*.yml` and `vault_*.yml` files. |
| `generate_env_vars_force` | Allows generated files to be overwritten. |
| `generate_env_vars_force_overwrite` | Compatibility overwrite flag mapped to `generate_env_vars_force`. |
| `bootstrap_generate_env_vars_machine_credential_enabled` | Creates an AAP Machine credential when using CLI vars without `preflight_json`. |
| `bootstrap_generate_env_vars_machine_credential_name` | AAP Machine credential name. Default `<org>-machine`. Custom names are normalized to the organization prefix. |
| `bootstrap_generate_env_vars_machine_credential_username` | SSH username for the Machine credential. Default `cloud-user`. |
| `bootstrap_generate_env_vars_machine_credential_ssh_key_data` | SSH private key data written to `vault_machine_cred.yml`. |
| `bootstrap_generate_env_vars_machine_credential_ssh_key_unlock` | Optional SSH private key passphrase written to `vault_machine_cred.yml`. |
| `bootstrap_generate_env_vars_machine_credential_become_method` | Become method for the Machine credential. Default `sudo`. |
| `bootstrap_generate_env_vars_machine_credential_become_username` | Become username for the Machine credential. Default `root`. |
| `bootstrap_generate_env_vars_aap_additional_credentials` | Additional AAP credentials to add to generated controller config. Secret-capable fields are written to `aap_vault.yml`. |
| `bootstrap_generate_env_vars_hub_publish_ado_collection` | Enables generated vars for adding the ADO collection to Automation Hub. Default `true`. |
| `bootstrap_generate_env_vars_hub_mark_ado_validated` | Targets the generated ADO collection hub entry at validated content when enabled. Default `true`. |
| `bootstrap_generate_env_vars_hub_force_ado_collection_update` | Forces the ADO collection publish task to overwrite an existing Hub version when Hub allows it. Default `true`. |
| `bootstrap_generate_env_vars_hub_update_collection_only` | Publishes or updates the ADO collection in AAP Hub without generating or applying normal component bootstrap content. Default `false`. |
| `bootstrap_generate_env_vars_hub_ado_collection_path` | Local ADO collection path used by generated hub collection vars. Default `.`. |
| `bootstrap_generate_env_vars_aap_ee_image` | Execution environment image used when creating or updating the default AAP execution environment. Default `registry.redhat.io/ansible-automation-platform-27/ee-supported-rhel9:latest`. |
| `bootstrap_generate_env_vars_aap_deployment_version` | AAP OpenShift operator/platform version. Supported values: `2.5`, `2.6`, `2.7`; default `2.7`. |
| `bootstrap_generate_env_vars_aap_namespace` | Namespace for the AAP operator and platform. Default `aap`. |
| `bootstrap_generate_env_vars_aap_instance_name` | AnsibleAutomationPlatform CR name. Default `aap`. |
| `bootstrap_generate_env_vars_aap_component_deployment` | AAP 2.5+ deployment model: `unified` or `individual`. Default `unified`. |
| `bootstrap_generate_env_vars_aap_install_controller` | Enable Automation Controller in the platform. Default `true`. |
| `bootstrap_generate_env_vars_aap_install_hub` | Enable Private Automation Hub in the platform. Default `true`. |
| `bootstrap_generate_env_vars_aap_install_eda` | Enable Event-Driven Ansible in the platform. Default `true`. |
| `bootstrap_generate_env_vars_aap_install_lightspeed` | Enable Ansible Lightspeed in the platform. Default `false`. |
| Preflight `component_config.aap.admin_password` | Platform admin password written to `vault_aap.yml` as `aap_admin_password`; bootstrap creates `{instance}-admin-password` and sets `spec.admin_password_secret`. |
| Preflight `component_config.aap.minimal_footprint` | When true, disables Hub/EDA/Lightspeed (Controller + Gateway only). |
| Preflight `component_config.aap.operator_scope` | AAP operator OperatorGroup scope: `all_namespaces` (default, uses `stable-X.Y-cluster-scoped`) or `namespaced` (uses `stable-X.Y`). Explicit `operator_channel` still wins when set. |
| `bootstrap_generate_env_vars_aap_hub_storage_class` | StorageClass for file-backed Hub storage. |
| `bootstrap_generate_env_vars_aap_hub_storage_size` | File-backed Hub PVC size. Default `20Gi`. |
| `bootstrap_generate_env_vars_aap_hub_s3_secret` | Existing S3 object storage secret when Hub storage type is `S3`. |
| `bootstrap_generate_env_vars_aap_hub_azure_secret` | Existing Azure object storage secret when Hub storage type is `azure`. |
| `bootstrap_generate_env_vars_satellite_server_url` | Satellite server URL written to `vars_satellite.yml`. |
| `bootstrap_generate_env_vars_satellite_organization` | Satellite organization written to `vars_satellite.yml`. |
| `bootstrap_generate_env_vars_satellite_activation_key` | Client activation key used by `rhel_sat_reg` when registering hosts. |
| `bootstrap_generate_env_vars_satellite_service_account_username` | Satellite service account username used by `satellite_config`. |
| `bootstrap_generate_env_vars_satellite_service_account_password` | Satellite service account password written to `vault_satellite.yml`. |
| `bootstrap_generate_env_vars_satellite_admin_password` | Satellite admin password written to `vault_satellite.yml`; defaults to the service account password when omitted. |
| `bootstrap_generate_env_vars_satellite_validate_certs` | Satellite TLS validation setting. Default `false`; also renders `validate_certs` into the Satellite dynamic inventory source vars. |
| `bootstrap_generate_env_vars_satellite_deployment_version` | Satellite version written to `satellite_config_satellite_deployment_version` and `satellite_install_deployment_version`. Default `6.19`. |
| `bootstrap_generate_env_vars_satellite_location` | Logical Satellite install location, such as `AWS` or `primary-dc`. |
| `bootstrap_generate_env_vars_satellite_rhn_org_id` | RHN organization ID used when registering the Satellite server host. |
| `bootstrap_generate_env_vars_satellite_rhn_activation_key` | RHN activation key used when registering the Satellite server host. |
| `bootstrap_generate_env_vars_satellite_rhn_connected` | When true, write `satellite_config_rhn_connected: true` for connected Satellite content sync. Default `true`. CLI/preflight can override. |
| `bootstrap_generate_env_vars_satellite_manifest_file` | Optional Satellite manifest filename written as `satellite_config_manifest_file` for the configure playbook. |
| `bootstrap_generate_env_vars_satellite_size_profile` | Selected Satellite sizing profile. Default `default`. |
| `bootstrap_generate_env_vars_satellite_vg_name` | Satellite install LVM volume group name written to `satellite_install_vg_name`. Default `satellite`. |
| `bootstrap_generate_env_vars_satellite_data_disk_min_size` | Minimum unpartitioned Satellite data disk size written to `satellite_install_data_disk_min_size`. Default `10G`. |
| `bootstrap_generate_env_vars_satellite_data_device_name` | Optional Satellite data disk basename written to `satellite_install_data_device_name`. |
| `bootstrap_generate_env_vars_satellite_data_device` | Satellite data disk path prefix written to `satellite_install_data_device`. Default `/dev`. |
| `bootstrap_generate_env_vars_satellite_size` | Satellite sizing tier list used to derive install RAM/CPU checks and the installer tuning profile. |
| `bootstrap_generate_env_vars_satellite_req_dirs` | Satellite storage mount definitions written to `satellite_install_req_dirs`. |
| `bootstrap_generate_env_vars_satellite_dynamic_inventory_enabled` | Creates a Satellite 6 dynamic inventory source in AAP when true. Default `false`; enable via preflight `component_options.satellite: [satellite_dynamic_inventory]` and/or `component_config.satellite.dynamic_inventory_enabled: true`. |
| `bootstrap_generate_env_vars_satellite_credential_name` | AAP credential name for the Satellite 6 inventory source. |
| `bootstrap_generate_env_vars_satellite_inventory_source_name` | AAP inventory source name for Satellite dynamic inventory. |
| `bootstrap_generate_env_vars_satellite_inventory_overwrite` | Overwrite hosts during Satellite inventory sync. Default `true`. |
| `bootstrap_generate_env_vars_satellite_inventory_overwrite_vars` | Overwrite host variables during Satellite inventory sync. Default `true`. |
| `bootstrap_generate_env_vars_satellite_inventory_update_on_launch` | Update the Satellite inventory source when launched. Default `true`. |
| `bootstrap_generate_env_vars_satellite_inventory_update_cache_timeout` | Cache timeout for the Satellite inventory source. Default `0`. |
| `bootstrap_generate_env_vars_satellite_inventory_host_filter` | Optional Satellite inventory source host filter. |
| `bootstrap_generate_env_vars_capsule_hostname` | Capsule host FQDN seeded into the dedicated Capsule AAP inventory. |
| `bootstrap_generate_env_vars_capsule_satellite_fqdn` | Upstream Satellite FQDN for Capsule install; defaults from `bootstrap_generate_env_vars_satellite_server_url` when unset. |
| `bootstrap_generate_env_vars_capsule_deployment_version` | Capsule version written to `capsule_install_deployment_version`. Default `6.19`. |
| `bootstrap_generate_env_vars_capsule_location` | Capsule location written to `capsule_install_location`; defaults to Satellite location when unset. |
| `bootstrap_generate_env_vars_capsule_org_id` | Organization for Capsule registration written to `capsule_install_org_id`. |
| `bootstrap_generate_env_vars_capsule_activation_key` | Capsule activation key written to `vault_capsule_activation_key` / `capsule_install_activation_key`. |
| `bootstrap_generate_env_vars_capsule_min_memory_size` | Minimum Capsule memory in MB (`capsule_install_min_memory_size`). Default `12288`. |
| `bootstrap_generate_env_vars_capsule_min_cpu_count` | Minimum Capsule vCPU count (`capsule_install_min_cpu_count`). Default `4`. |
| `bootstrap_generate_env_vars_capsule_min_pulp_size` | Minimum Pulp storage in GB (`capsule_install_min_pulp_size`). Default `300`. |
| `bootstrap_generate_env_vars_capsule_min_pgsql_size` | Minimum PostgreSQL storage in GB (`capsule_install_min_pgsql_size`). Default `20`. |
| `bootstrap_generate_env_vars_capsule_data_disk_min_size` | Minimum Capsule data disk size in GB (`capsule_install_data_disk_min_size`). Default `500`. |
| `bootstrap_generate_env_vars_capsule_selinux_state` | SELinux state for the Capsule patch path (`capsule_install_selinux_state`). Default `enforcing`. |
| `bootstrap_generate_env_vars_capsule_scenario` | ``satellite-installer`` scenario name (`capsule_install_scenario`). Default `capsule`. |
| `bootstrap_generate_env_vars_capsule_admin_username` | Satellite admin user for Capsule registration (`capsule_install_admin_username`). Default `admin`. |
| `bootstrap_generate_env_vars_capsule_pulp_size` | Pulp LV size (`capsule_install_pulp_size`). Default `1500g`. |
| `bootstrap_generate_env_vars_capsule_pgsql_size` | PostgreSQL LV size (`capsule_install_pgsql_size`). Default `150g`. |
| `bootstrap_generate_env_vars_capsule_vg_name` | Capsule LVM volume group (`capsule_install_vg_name`). Default `capsule`. |
| `bootstrap_generate_env_vars_capsule_req_dirs` | Capsule storage mount definitions (`capsule_install_req_dirs`). |
| `bootstrap_generate_env_vars_capsule_data_device` | Capsule data disk path prefix. Default `/dev`. |
| `bootstrap_generate_env_vars_capsule_data_device_name` | Optional Capsule data disk basename. |
| `bootstrap_generate_env_vars_capsule_lifecycle_environments` | Lifecycle environments for Capsule post-config. |
| `bootstrap_generate_env_vars_capsule_sync_wait_time` | Capsule content sync wait timeout in seconds. Default `86400`. |
| `bootstrap_generate_env_vars_capsule_setup_insights` | Register Capsule with Insights during RHSM subscribe. Default `false`. |
| `bootstrap_generate_env_vars_capsule_satellite_haproxy` | Enable load-balanced Capsule install path. Default `false`. |
| `bootstrap_generate_env_vars_capsule_loadbalancer_fqdn` | Load balancer FQDN when HAProxy Capsule install is enabled. |
| `bootstrap_generate_env_vars_capsule_loadbalancer_activation_key` | Activation key for load balancer registration. |

OpenShift preflight JSON can include `component_options.openshift` to opt into
optional OpenShift configuration. `admin_htpasswd` writes HTPasswd admin user
vault values, and `console_banner` writes console banner vars. When those
options are omitted, stale generated HTPasswd and banner values are removed.

Preflight `additional_environments` (space/comma-separated names) is combined
with the primary `environment` value to build AAP survey
`environment_choices`. Empty / `none` means only the primary environment is
offered. The old hardcoded `dev/test/preprod/prod` survey list is not used when
choices are generated from preflight.

When IdM AD Trust is selected, this role overlays IdM AD trust settings into
`vars_idm.yml` / IdM vault secrets (including
`vault_ad_trust_admin_password`) and ensures the IdM inventory is present so
`ADO | IdM Manage AD Trust` can target IdM hosts.

Generated AAP inventories are split by purpose:

- `<org>-inventory` contains only `localhost` for controller-side and local
  bootstrap jobs.
- `<org>-RHEL-Inventory` contains RHEL managed hosts supplied through the
  preflight RHEL or Patching form fields (`component_config.rhel` /
  `component_config.patching`) or CLI vars. The inventory is also created when
  only the Patching group is selected, because patching job templates target it,
  and when Satellite ``satellite_client_tools`` is selected (for example
  ``ADO | Register Host to Satellite``) even if dynamic inventory is disabled.
  Set ``component_config.patching.inventory_mode: existing`` with
  ``inventory_name`` to reuse an inventory that already exists in AAP instead of
  creating ``<org>-RHEL-Inventory`` or adding static hosts. When Satellite
  dynamic inventory is enabled, the inventory source attaches to this same
  managed-host inventory so synced Satellite hosts become managed RHEL targets;
  when dynamic inventory is off, the inventory is still created as an empty
  static inventory for registration jobs.
- `<org>-IDM-Inventory` contains IDM server and replica hosts when IDM is
  selected under RHEL or Patching.
- `<org>-Satellite-Server-Inventory` contains the Satellite server host when
  Satellite is selected.

Additional AAP credentials, the primary AAP Vault credential, the primary AAP
Machine credential, and Satellite dynamic inventory objects are normalized to
the organization-prefixed name pattern. For example, `IDM-Cred`,
`test-machine`, and `test-vault` under organization `RH` become `RH-IDM-Cred`,
`RH-test-machine`, and `RH-test-vault`.

Generated AAP project names are normalized the same way. If the organization is
`RH` and the project field is `test-project`, the generated AAP project becomes
`RH-test-project`.

Generated AAP labels include the organization name, for example `ADO`, plus
organization-prefixed component labels such as `ADO | rhel`,
`ADO | satellite`, and `ADO | bootstrap`. These labels are attached to the
generated automation so AAP can group and filter by organization and component.

Satellite dynamic inventory creates an AAP inventory source named like
`ADO-Satellite-Dynamic-Inventory` on the RHEL inventory. It is not a separate
inventory named `ADO Satellite Dynamic Inventory`; it is a source attached to
`ADO-RHEL-Inventory` so synced Satellite hosts become managed RHEL targets.

### Shared AWS credentials (`vault_aws.yml`)

Bootstrap now generates shared AWS account credentials for all AWS consumers
under `group_vars/all/<env>/`:

| File | Purpose |
|------|---------|
| `vault_aws.yml` | `vault_aws_access_key_id`, `vault_aws_secret_access_key`, optional `vault_aws_session_token` |
| `vars_aws.yml` | `aws_profile`, `aws_default_region` |

Consumers include ``infra.ado.ec2_ami_copy`` (``ado-copy-ami-bootstrap``),
cert-manager AWS PCA (``ado-install-and-configure-awspca-bootstrap``), and
future AWS bootstrap apps. Set credentials in preflight
``component_config.aws`` (or legacy per-component keys that overlay into
``vault_aws.yml`` during generation).

#### Migrating existing environments (legacy AWS PCA vault)

Older bootstrap output scaffolded PCA credentials in generated vault templates
as ``ocp_awspca_access_key_id`` and ``ocp_awspca_secret_access_key`` under
``vault_openshift.yml`` (OpenShift vault template) and/or wrote them into
``vault_cert_manager.yml`` during preflight overlay. Those template keys are
**no longer generated**.

**New path:** store account credentials once in ``vault_aws.yml``. The
``ado-install-and-configure-awspca-bootstrap`` playbook loads
``vault_aws.yml`` and maps shared keys to ``ocp_awspca_access_key_id`` /
``ocp_awspca_secret_access_key`` before calling ``infra.ado.ocp_awspca``.
Non-secret PCA settings (``ocp_awspca_region``, ``ocp_awspca_pca_arn``, etc.)
remain in ``vars_cert_manager.yml``.

**Migration steps for an existing Controller project / env directory:**

1. Open ``group_vars/all/<env>/vault_aws.yml`` (create from bootstrap if
   missing) and copy legacy values:
   - ``vault_aws_access_key_id`` ← ``ocp_awspca_access_key_id`` (from
     ``vault_cert_manager.yml`` or ``vault_openshift.yml``)
   - ``vault_aws_secret_access_key`` ← ``ocp_awspca_secret_access_key``
2. Re-encrypt ``vault_aws.yml`` if your project uses Ansible Vault.
3. Remove the legacy ``ocp_awspca_access_key_id`` /
   ``ocp_awspca_secret_access_key`` entries from ``vault_cert_manager.yml``
   and ``vault_openshift.yml`` when convenient (optional cleanup).
4. Sync the bootstrap playbook repo so
   ``playbooks/cert-manager/ado-install-and-configure-awspca-bootstrap.yml``
   includes the ``vault_aws.yml`` ``vars_files`` entry and credential remap
   pre-task.

**Backward compatibility:** If ``vault_aws.yml`` is empty but
``vault_cert_manager.yml`` still contains ``ocp_awspca_*`` keys, the awspca
bootstrap playbook continues to work—the remap pre-task is skipped and the
role reads the legacy variables from ``vault_cert_manager.yml``. New
environments should use ``vault_aws.yml`` only.

To regenerate from preflight instead of manual edits, include AWS credentials
under ``component_config.aws`` (``access_key_id``, ``secret_access_key``) or
cert-manager PCA fields (``awspca_access_key_id``, ``awspca_secret_access_key``)
and re-run bootstrap env-var generation for that ``<env>``.

## 🚀 Role Usage

```yaml
- name: Generate bootstrap environment variables
  hosts: localhost
  gather_facts: false
  vars:
    env: prod
    preflight_json: ado-preflight-prod.json
  roles:
    - role: infra.ado.bootstrap_generate_env_vars
```

## 🧪 Role Molecule Testing

Validate with a sample preflight JSON and local bootstrap repository fixture.

```bash
ansible-lint --offline roles/bootstrap_generate_env_vars
yamllint roles/bootstrap_generate_env_vars/tasks
```

## 📁 Role Structure

```text
roles/bootstrap_generate_env_vars/
  defaults/main.yml
  tasks/main.yml
  README.md
```
