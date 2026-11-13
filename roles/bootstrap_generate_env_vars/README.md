# Role: infra.automation_development_office.bootstrap_generate_env_vars

Generate environment group variables and vault files used by the ADO bootstrap
playbook repository.

When Default Ingress Certificate is selected
(``component_options.openshift`` contains ``update_default_ingress`` or
``component_config.cert_manager.update_default_ingress``), this role publishes
``bootstrap_controller_update_default_ingress`` and
``bootstrap_controller_cert_manager_explicit`` from preflight so No-AAP runs
(that skip ``aap_config_vars.yml``) still keep the ingress playbook gate
aligned with AAP mode. Ingress-only does not mark Certificate Manager deploy
as an explicit selection.

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
| `preflight_json` | Optional JSON file containing UI or CLI preflight answers. OpenShift-routed app hostnames inherit `openshift.apps_domain` as `<prefix>.<apps_domain>` unless `component_config.<app>.hostname_manual` is true. A typed apps domain that differs from ``apps.<domain>`` sets ``apps_domain_manual``. ``component_options.quay`` ``minio`` sets ``ocp_quay_storage_backend=minio`` and S3 pointers from Quay form fields (``s3_hostname``, ``s3_access_key``, ``s3_secret_key``, ``s3_bucket``). It does not add the MinIO component. Quay ``admin_user`` / ``admin_password`` write ``ocp_quay_admin_user`` and ``vault_ocp_quay_admin_password``. |
| `generate_env_vars_base_dir` | Base directory for generated environment variables. |
| `generate_env_vars_create_dirs` | Creates bootstrap repository directories when true. |
| `generate_env_vars_encrypt_vault_files` | Encrypts generated vault files when true. |
| `generate_env_vars_components` | Component list for generated `vars_*.yml` and `vault_*.yml` files. |
| `bootstrap_generate_env_vars_preflight_ui_openshift_apps` | OpenShift app ids the preflight UI exposes as checkboxes. Selected `component_apps.openshift` values outside this list are ignored for playbook and job-template generation. Includes `ocp_compliance`. |
| `bootstrap_generate_env_vars_non_ui_openshift_playbook_apps` | Collection playbook apps that are not preflight UI checkboxes. Stale imports in top-level `components[]` are ignored (`gitlab_runner`, `web_terminal`, `ocp_descheduler`). |
| `generate_env_vars_force` | Allows generated files to be overwritten. |
| `generate_env_vars_force_overwrite` | Compatibility overwrite flag mapped to `generate_env_vars_force`. |
| `bootstrap_generate_env_vars_machine_credential_enabled` | Creates an AAP Machine credential when using CLI vars without `preflight_json`. |
| `bootstrap_generate_env_vars_machine_credential_name` | AAP Machine credential name. Default `<org>-machine`. Custom names are normalized to the organization prefix. |
| `bootstrap_generate_env_vars_machine_credential_username` | SSH username for the Machine credential. Default `cloud-user`. |
| `bootstrap_generate_env_vars_machine_credential_ssh_key_data` | SSH private key data written to `vault_machine_cred.yml`. |
| `bootstrap_generate_env_vars_machine_credential_ssh_key_unlock` | Optional SSH private key passphrase written to `vault_machine_cred.yml`. |
| `bootstrap_generate_env_vars_machine_credential_become_method` | Become method for the Machine credential. Default `sudo`. |
| `bootstrap_generate_env_vars_machine_credential_become_username` | Become username for the Machine credential. Default `root`. |
| `bootstrap_generate_env_vars_machine_credential_become_password` | Optional sudo password for the Machine credential. Omitted from the Controller credential and `vault_machine_cred.yml` when blank. |
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
| `bootstrap_generate_env_vars_capsule_pulp_size` | Pulp LV size (`capsule_install_pulp_size`). Default `1500g`. Written only when `component_options.satellite` includes `satellite_capsule_install`. |
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
optional OpenShift configuration. ``admin_htpasswd`` must be explicitly selected
to generate the HTPasswd admin playbook and vault values (presence of
``openshift.admin_username`` / ``admin_password`` alone is not enough).
Set ``openshift.htpasswd_idp_name`` for the console login button label
(OAuth identity provider name; default ``htpasswd-admin``); the secret name
defaults to ``<idp>-secret``. ``console_banner`` writes console banner vars and selects the console playbook.
``integrated_image_registry`` enables the OpenShift integrated image registry
option (``ocp_image_registry_*`` / ``openshift_integrated_registry_*`` vars,
Contoller JT, and optional install-during-bootstrap before NFS CSI).
Stale ``openshift.banner_text`` alone does not select console. When those
options are omitted, stale generated HTPasswd and banner values are removed. OpenShift
``component_apps`` entries that are not in the preflight UI checkbox catalog are
ignored so leftover import ghosts do not generate playbooks.
``component_apps.satellite`` is a first-class target-platform group (same flatten
as OpenShift/RHEL/Patching). Satellite also remains selectable under
``component_apps.rhel`` and ``component_apps.patching`` for existing JSON.

Preflight `additional_environments` (space/comma-separated names) is combined
with the primary `environment` value to build AAP survey
`environment_choices`. Empty / `none` means only the primary environment is
offered. The old hardcoded `dev/test/preprod/prod` survey list is not used when
choices are generated from preflight. Set
`additional_environments_create_group_vars` to `true` to also copy
`group_vars/all/<environment>` into each other selected name. The primary
environment directory is not copied onto itself.

When IdM AD Trust is selected, this role overlays IdM AD trust settings into
`vars_idm.yml` / IdM vault secrets (including
`vault_ad_trust_admin_password`) and ensures the IdM inventory is present so
`ADO | IdM Manage AD Trust` can target IdM hosts.

Generated AAP inventories are split by purpose:

- `<org>-inventory` contains only `localhost` for controller-side and local
  bootstrap jobs.
- `<org>-RHEL-Inventory` contains RHEL managed hosts supplied through the
  preflight RHEL or Patching form fields (`component_config.rhel` /
  `component_config.patching`) or CLI vars. Those hosts are also placed in
  Contoller group ``rhel_servers`` for playbooks that still use that host
  pattern. ``ADO | Register Host to Satellite`` and ``ADO | RHEL Patch Host``
  target ``hosts: all`` so Contoller inventory selection (and Limit) works
  without requiring that group. The inventory is also created when
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
  Satellite install or OIDC is selected. Client registration, content view, and
  RHEL/patching-only runs do not create this inventory. Content view uses the
  local bootstrap inventory.

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

Consumers include ``infra.automation_development_office.ec2_ami_copy`` (``ado-copy-ami-bootstrap``),
EC2 instance bootstrap playbooks under ``playbooks/aws/ec2/``,
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
``ocp_awspca_secret_access_key`` before calling ``infra.automation_development_office.ocp_awspca``.
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

### OpenShift OIDC (Keycloak/RHBK or an existing Keycloak)

When ``openshift`` is selected with the ``oauth_rhbk`` option, generation
produces the variables the ``ocp_oidc_auth`` role already reads. There are two
modes, chosen by whether RHBK is part of the run.

| Input (``openshift.oauth_rhbk.*``) | RHBK in the run | Existing Keycloak (no RHBK in the run) |
| --- | --- | --- |
| ``keycloak_hostname`` | ignored; always inherited from the RHBK hostname. Route host only, no ``http://``, ``https://``, or trailing ``/``. | required; same host-only rule |
| ``realm`` | ignored; always inherited from the RHBK realm | required |
| ``client_id`` | required (see below) | required |
| ``admin_user`` | ignored; always inherited from the RHBK admin user | required |
| ``admin_password`` | ignored; always inherited from the RHBK admin password | required |
| ``verify_ssl`` | optional, default on (``ocp_rhbk_verify_ssl``) | optional, default on |
| ``idp_name``, ``mapping_method``, ``extra_scopes`` | optional. ``mapping_method`` defaults to ``add`` (``claim`` fails with ``Could not create user`` when that OpenShift username already exists) | optional. same default |

``idp_name`` is the OpenShift OAuth identity-provider name (default
``Keycloak``). The cluster callback is the exact path
``https://oauth-openshift.<apps_domain>/oauth2callback/<idp_name>``
(OpenShift oauth-server does not append a further path segment). Overlay
writes that URI as ``openshift_oidc_auth.openshift_oauth_redirect_uri``
and rewrites auto-generated ``oauth2callback`` URIs — including a legacy
trailing ``/*`` — on **managed** OpenShift client rows in ``rhbk_clients``.
Externally managed OpenShift clients (``create_client: false``) are not sent
to ``ADO | Deploy RHBK Client``; register that exact callback URI on the
existing Keycloak client yourself. Custom non-callback redirect URIs on a
managed row are left unchanged.

When RHBK is overlaid, ``rhbk_clients`` is always rebuilt from the current
preflight ``clients`` list. Missing or empty lists drop seed and prior
``rhbk_clients`` so a retained row cannot keep provisioning an unmanaged or
MinIO client.

Grafana OIDC ``component_config.grafana.oidc.enabled: false`` is preserved.
Overlay does not force ``enabled: true``, does not copy that Grafana client
into ``rhbk_clients``, and does not add the ``grafana_oidc`` job template
when the flag is explicitly off. Missing ``enabled`` with the Grafana
``oidc`` option still defaults on. When RHBK is in the run, Grafana OIDC
inherits hostname and realm from the RHBK component (same Keycloak as
Client and OpenShift OAuth). Leftover ``oidc.issuer`` values are replaced
unless ``issuer_manual`` is true. Overlay does not invent ``Dev`` or
``rhlab``. Mapping method is OpenShift-only.

Keycloak TLS verification is on in both modes. ``verify_ssl`` is parsed
strictly: blank or missing means on; ``true`` / ``yes`` / ``on`` / ``1`` verify;
``false`` / ``no`` / ``off`` / ``0`` turn verification off; any other value
(``garbage``, ``tru``, ``flase``, unexpected numbers) is a validation error and
is never read as false. Generation writes ``ocp_rhbk_verify_ssl`` only when the
preflight sets a recognized explicit value, and never removes a value that is
already in ``vars_rhbk.yml``, so an existing explicit ``ocp_rhbk_verify_ssl:
false`` keeps working. For a private CA, trust it in the execution environment
or set ``ocp_oidc_auth_ca_pem`` (see the ``ocp_oidc_auth`` role); verification
is not turned off for an internal CA.

Neither mode creates or changes a Keycloak client. The role only reads the client
secret with the admin credentials, so the client must already exist in the realm.
No ``rhbk_client`` / ``rhbk_clients`` entry is generated for OpenShift OAuth itself.

Keycloak client ownership is per row in ``component_config.rhbk.clients``:

* ``create_client`` omitted, null, blank, or true (default) — ADO creates or
  updates that client. The id is copied into generated ``rhbk_clients`` for
  ``ADO | Deploy RHBK Client``.
* ``create_client: false`` — use an existing client. The row and the
  application's OIDC client ID stay; the id is **not** copied into
  ``rhbk_clients``, and a prior run's provision entry for that id is dropped
  so the next Deploy RHBK Client job cannot recreate it. Dismissing the row is
  not required.

Existing JSON exports without ``create_client`` keep the automated install
path. Satellite ``oidc.create_client`` and AAP Gateway OIDC are unchanged.

With RHBK in the run, OpenShift OAuth always uses that Keycloak instance and
realm. Leftover ``openshift.oauth_rhbk`` hostname, realm, and admin values are
ignored so a previous export cannot silently point OAuth at a different
Keycloak. Client-only and other existing-Keycloak RHBK operations require
``component_config.rhbk.realm``; overlay does not invent ``Dev`` or ``rhlab``
from the environment name. Use the OAuth-only path (RHBK not selected) for an
external Keycloak. RHBK's own ``rhbk_hostname``, ``rhbk_realm`` and ``rhbk_admin_*``
are left alone. Without RHBK, ``vars_rhbk.yml`` and ``vault_rhbk.yml`` are
created because the OpenShift OAuth playbook loads them; a leftover RHBK form
that is not selected is ignored. The admin password is written only to
``vault_rhbk.yml`` (``vault_ocp_oidc_auth_rhbk_admin_password``);
``vars_rhbk.yml`` holds a ``{{ vault_... }}`` reference.

The client ID is resolved in this order:

1. ``openshift.oauth_rhbk.client_id`` (or ``keycloak_client_id``)
2. ``component_config.rhbk.openshift_oidc_client_id``
3. a row in ``component_config.rhbk.clients`` with ``source: openshift`` or an
   ``id`` that starts with ``openshift``

The first Keycloak client (``component_config.rhbk.client``) is never used, because
it can belong to another app such as Grafana. When OpenShift OIDC is not requested,
no OpenShift OIDC overrides are generated and values left by an earlier run are
removed.

### OIDC validation before generation

``files/preflight_oidc.py`` validates the preflight JSON before any component vars
are generated (a role task runs it first; the overlay runs it again). It mirrors
the Preflight UI so the form is not the only protection:

* OpenShift OIDC must have an explicit client ID (it has no default client);
* with RHBK in the run, an enabled integration (Grafana, BookStack, NetBox,
  Quay, MinIO, Developer Hub, OpenShift) must not reference a client listed in
  ``component_config.rhbk.clients_dismissed`` and absent from ``clients``. An empty
  client ID means the framework's default client (``grafana-client``, ``bookstack``,
  ``netbox``, ``quay``, ``minio``, ``rhdh``), so that default is checked too. The
  defaults are read from ``bootstrap_resolve_component/files/components_defaults.yml``;
  the Preflight UI resolves blank IDs from a file generated from the same source
  (``scripts/sync-oidc-client-defaults.py`` in ``ado-preflight-ui``). GitLab is
  not an OIDC consumer unless ``oidc_enabled`` / ``component_options.gitlab``
  ``oidc`` is already set in the JSON; selecting GitLab does not add a Keycloak
  client. When that leftover GitLab OIDC flag is on, GitLab has no default and
  needs an explicit client ID;
* without RHBK, or when the component's own "managed elsewhere" flag is set
  (``grafana.oidc.client_secret_manual``, ``quay``/``minio``
  ``fetch_oidc_secret_from_rhbk: false``, ``openshift.oauth_rhbk.fetch_client_secret:
  false``), the client list is not consulted and an existing realm client is accepted;
* OpenShift OIDC connection inputs in the table above are present, the hostname is
  a valid host with no ``http://`` or ``https://`` scheme and no trailing ``/``,
  and ``mapping_method`` is ``claim``, ``lookup`` or ``add``;
* Client-only and other existing-Keycloak RHBK operations require
  ``component_config.rhbk.realm`` even when Realm creation is unselected.

Only selected, enabled integrations are checked. Failures stop generation with a
list of what to fix; secrets are never printed. Run it on its own with
``ADO_PREFLIGHT_JSON=<file> ADO_SELECTED_COMPONENTS='["openshift"]' python3 roles/bootstrap_generate_env_vars/files/preflight_oidc.py``.

``component_config.rhbk.clients_dismissed`` is Preflight UI bookkeeping for
clients removed in the form. It is not written to generated vars.
``create_client`` on a client row is also UI/preflight input; only managed
clients appear in generated ``rhbk_clients``. The overlay may still copy the
preflight ``clients`` list into ``vars_rhbk.yml`` as passthrough. ``ADO |
Deploy RHBK Client`` loops ``rhbk_clients`` (or singular ``rhbk_client`` when
that dict is empty). No playbook loops the passthrough ``clients`` list to
create, update, or delete Keycloak clients, so an unmanaged row can remain
there without being provisioned.

RHBK playbook and job-template selection follows the same pattern as Grafana.
``component_apps.openshift`` ``rhbk`` with no ``component_options.rhbk`` (or
with ``install``) generates ``ADO | Deploy RHBK``. Selecting only ``client``
generates ``ADO | Deploy RHBK Client`` and does not install Keycloak, create
client scopes, or deploy the login-events exporter. ``client_scopes`` is
generated only when that option is checked. The login-events exporter is
optional Keycloak login/logout monitoring and stays off unless
``component_config.rhbk.login_events_exporter_enabled`` is true.
``Configure OAuth/RHBK in OpenShift`` is the OpenShift ``oauth_rhbk`` option,
not an RHBK client option.

### MinIO and Developer Hub client IDs

MinIO and Developer Hub OIDC client IDs follow the Preflight form through
generated ``group_vars``. The first Keycloak client row is never substituted.

* MinIO canonical field is ``component_config.minio.oidc_client_id`` (the form
  field). Nested ``component_config.minio.oidc.client_id`` is accepted for older
  JSON. When both are set, the top-level field wins. Overlay writes
  ``minio_oidc_client_id``.
* Developer Hub canonical field is ``component_config.dev_hub.keycloak_client_id``.
  ``oidc_client_id`` is a leftover preset field: used when ``keycloak_client_id``
  is blank, or when the form still has the framework default ``rhdh`` and
  ``oidc_client_id`` is a different custom value. Overlay writes
  ``dev_hub_keycloak_client_id`` and drops ``oidc_client_id`` from generated
  Dev Hub vars so the two fields cannot stay in conflict.

``create_client`` on the matching ``rhbk.clients`` row still controls whether
ADO may mutate that Keycloak client. Application OIDC vars are written either
way. The MinIO OIDC client is an exception to ``rhbk_clients``: when MinIO is
selected, overlay omits that id from ``rhbk_clients`` and writes
``minio_oidc_create_keycloak_client`` / ``minio_oidc_create_policy_mapper``
instead. ``ocp_minio`` is the only provisioner for that client (client +
policy mapper). ``create_client: false`` sets both flags false so the MinIO
playbook cannot update an externally managed client, including mappers.

GitLab is not an OIDC application in ADO. Overlay omits ``source: gitlab``
rows and, when GitLab is selected, the historical ``gitlab`` client id /
``component_config.gitlab.oidc_client_id`` from generated ``rhbk_clients``.
Existing Keycloak clients and preflight rows are not deleted. A hand-edited
``rhbk_clients`` entry can still be applied by Deploy RHBK Client.

BookStack OIDC secrets: overlay writes ``bookstack_oidc_client_secret`` only
when preflight supplies one. The BookStack role fetches the Keycloak secret
when that value is empty (including unmanaged clients) and fails if the
secret is still empty.

## 🚀 Role Usage

```yaml
- name: Generate bootstrap environment variables
  hosts: localhost
  gather_facts: false
  vars:
    env: prod
    preflight_json: ado-preflight-prod.json
  roles:
    - role: infra.automation_development_office.bootstrap_generate_env_vars
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

### Pega disconnected inputs

`component_config.pega` maps local chart/values paths, database mode and allowed
registry hosts into `ocp_pega_*` variables. Database mode defaults to `new`; an
existing initialized database can be selected explicitly. Paths refer to files
inside the execution environment. See `docs/PEGA_DISCONNECTED.md` and the
`ocp_pega` role README for artifact preparation and the full input contract.

Dev Spaces `component_config.devspaces.delivery_mode` (`direct`/`generate`) and
`gitops_repo_url`, `gitops_revision`, `gitops_path`, `gitops_namespace`,
`gitops_project`, `gitops_destination` map to `ocp_devspaces_*`. Blank GitOps paths
use the environment-specific default. ACM `component_config.acm.policy_enabled`
and `policy_name`, `policy_namespace`, `policy_target_namespace`, `policy_label_key`,
`policy_label_value`, `policy_cluster_set`, `policy_selector_key`,
`policy_selector_value`, `policy_remediation` map to `ocp_acm_policy_*` variables.
Bootstrap's playbook-repo generator consumes these variables before committing
files. Neither generator applies Argo CD applications or ACM policies.

Public Galaxy access is controlled by `aap.galaxy_credentials`: set the public
credential entry to `enabled: false` and `attach_to_org: false` for local Hub
only operation. Mirror the complete dependency closure into Hub first. Existing
JSON exports retain their explicit settings; importing an older export can
re-enable its public source. New Preflight defaults leave public Galaxy disabled.

Galaxy setup (`aap.galaxy_setup_enabled`) creates and attaches Controller Galaxy
credentials from each enabled `aap.galaxy_credentials[]` entry that has a name
and URL. With no platforms in `components[]`, that is AAP-tabs-only: do not
expand an empty list into every OpenShift/RHEL playbook. The shared `aap.galaxy_hub_token` is optional. A per-credential
`token` is used when set; otherwise the shared Hub token is used; otherwise the
credential is created with an empty token so public Galaxy or later token
updates still work. Hub-only collection publish without Galaxy setup still
skips these credentials.
