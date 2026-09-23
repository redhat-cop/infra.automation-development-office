# infra.ado

[![Ansible Collection CI/CD](https://github.com/redhat-cop/infra.automation-development-office/actions/workflows/main.yml/badge.svg)](https://github.com/redhat-cop/infra.automation-development-office/actions/workflows/main.yml)
[![Security Check](https://github.com/redhat-cop/infra.automation-development-office/actions/workflows/security-check.yml/badge.svg)](https://github.com/redhat-cop/infra.automation-development-office/actions/workflows/security-check.yml)
[![Certification checker](https://github.com/redhat-cop/infra.automation-development-office/actions/workflows/certification.yml/badge.svg)](https://github.com/redhat-cop/infra.automation-development-office/actions/workflows/certification.yml)

Automation Development Office (`infra.ado`) Ansible collection for building and
operating platform automation across Ansible Automation Platform, OpenShift,
RHEL, Satellite, identity services, and supporting tooling.

This collection packages reusable **roles** and **modules** used by ADO
bootstrap and day-2 workflows so teams can install, configure, and operate
infrastructure components consistently.

## Collection purpose

`infra.ado` provides:

- **Roles** for opinionated platform automation:
  - **AAP and bootstrap** — install and configure Ansible Automation Platform,
    build execution environments, and generate bootstrap playbook repositories
    and controller objects
  - **OpenShift platform** — operators, namespaces, routes, storage, logging,
    security, GitOps, virtualization, and related cluster services
  - **Identity** — Red Hat IdM (FreeIPA), Red Hat build of Keycloak (RHBK),
    LDAP, and OIDC authentication integrations
  - **RHEL and Satellite** — repositories, patching, registration, services,
    mounts, and Satellite install/content-view management
  - **Observability and devops tooling** — Grafana, Elastic, Kafka, GitLab,
    Jira, and related helpers
- **Modules** for focused tasks that do not fit a role, such as copying an AWS
  AMI between regions without depending on `community.aws`

<!--start requires_ansible-->
## Ansible version compatibility

This collection has been tested against the following Ansible versions: **>=2.17.0**.

Plugins and modules within a collection may be tested with only specific Ansible versions.
A collection may contain metadata that identifies these versions.
PEP440 is the schema used to describe the versions of Ansible.
<!--end requires_ansible-->

## Content index

| Type | Name | Description |
| --- | --- | --- |
| Module | [`infra.ado.ec2_ami_copy`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/docs/modules/ec2_ami_copy.md) | Copy an AWS AMI between regions; optionally rename with `name` or omit it to keep the source name. |
| Role | See [Role documentation](#role-documentation) | Platform automation roles (AAP, OpenShift, RHEL, identity, and more). |

## Module documentation

Each module keeps its detailed usage, parameters, and examples under `docs/modules/`.
Use this index as the starting point for operators and automation users.

| Module | Description |
| --- | --- |
| [`infra.ado.ec2_ami_copy`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/docs/modules/ec2_ami_copy.md) | Copy an AWS AMI between regions; optionally rename with `name` or omit it to keep the source name. |

## Role documentation

Each role keeps its detailed usage, variables, and examples in its own README.
Use this index as the starting point for operators and automation users.

| Role | Description |
| --- | --- |
| [`infra.ado.aap_build_ee`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/aap_build_ee/README.md) | Build a custom Ansible Execution Environment (EE) image with ansible-builder. |
| [`infra.ado.aap_configuration`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/aap_configuration/README.md) | Collect user-provided AAP configuration files and dispatch them to the upstream infra.aap_configuration.dispatch role for processing. |
| [`infra.ado.acs_report`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/acs_report/README.md) | Generate RHACS vulnerability reports from Central and optional CVE enrichment via acs-cve-plugin. |
| [`infra.ado.acs_upload_policies`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/acs_upload_policies/README.md) | Upload RHACS policy bundles to Central from role files or custom paths. |
| [`infra.ado.bootstrap_controller`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bootstrap_controller/README.md) | Generate and apply Ansible Automation Platform controller objects for an ADO bootstrap repository. |
| [`infra.ado.bootstrap_flatten_vars`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bootstrap_flatten_vars/README.md) | Flatten a named dictionary into top-level Ansible facts for bootstrap playbooks that expect direct variable names. |
| [`infra.ado.bootstrap_framework_defaults`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bootstrap_framework_defaults/README.md) | Load shared bootstrap framework defaults before component-specific roles resolve their effective configuration. |
| [`infra.ado.bootstrap_generate_env_vars`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bootstrap_generate_env_vars/README.md) | Generate environment group variables and vault files used by the ADO bootstrap playbook repository. |
| [`infra.ado.bootstrap_generate_playbook_repo`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bootstrap_generate_playbook_repo/README.md) | Create or refresh the generated bootstrap playbook repository structure used by ADO component automation. |
| [`infra.ado.bootstrap_resolve_component`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bootstrap_resolve_component/README.md) | Resolve one bootstrap component into the effective variable set used by its generated playbook. |
| [`infra.ado.bookstack_openshift`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/bookstack_openshift/README.md) | Deploy BookStack on OpenShift with MariaDB, Routes, and optional RHBK OIDC. |
| [`infra.ado.elastic`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/elastic/README.md) | Operational checks and actions for Elasticsearch through a state-driven interface. |
| [`infra.ado.gitlab_install`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/gitlab_install/README.md) | Install and configure GitLab on OpenShift using the GitLab Operator and Custom Resource (CR). |
| [`infra.ado.grafana_create_datasource`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/grafana_create_datasource/README.md) | Configure a Grafana Prometheus datasource from the OpenShift Prometheus route and a service-account token. |
| [`infra.ado.grafana_install`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/grafana_install/README.md) | Deploy Grafana on OpenShift with the Grafana Operator, storage, credentials, optional OIDC, and a Route. |
| [`infra.ado.grafana_manage_folders`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/grafana_manage_folders/README.md) | Create and manage Grafana dashboard folders. |
| [`infra.ado.grafana_upload_dashboards`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/grafana_upload_dashboards/README.md) | Render and upload Grafana dashboards with OpenShift datasource substitution. |
| [`infra.ado.idm_ad_trust`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/idm_ad_trust/README.md) | Establish IdM ↔ Active Directory trust and map AD groups for SSH/sudo. |
| [`infra.ado.idm_client`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/idm_client/README.md) | Register hosts as Red Hat IdM (FreeIPA) clients. |
| [`infra.ado.idm_configure_replica`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/idm_configure_replica/README.md) | Install and configure an IdM replica server. |
| [`infra.ado.idm_dns`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/idm_dns/README.md) | Manage IdM DNS records via redhat.rhel_idm. |
| [`infra.ado.idm_server`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/idm_server/README.md) | Install and configure a Red Hat Identity Management (IdM/FreeIPA) server. |
| [`infra.ado.install_aap`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/install_aap/README.md) | Install AAP on OpenShift or RHEL via validated ``infra.aap_utilities`` (``aap_ocp_install`` / ``aap_setup_*``). |
| [`infra.ado.install_dirsrv`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/install_dirsrv/README.md) | Install and configure 389 Directory Server (DirSrv) on OpenShift. |
| [`infra.ado.install_elastic`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/install_elastic/README.md) | Deploy Elastic Cloud on Kubernetes (ECK) operator and Elasticsearch/Kibana on OpenShift. |
| [`infra.ado.install_gitlab`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/install_gitlab/README.md) | Install standalone GitLab CE/EE on RHEL (Omnibus packages or offline RPM). |
| [`infra.ado.install_postfix`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/install_postfix/README.md) | Deploy a Postfix relay on OpenShift with ConfigMap, Secret, and Pod resources. |
| [`infra.ado.install_rhbk`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/install_rhbk/README.md) | Install or tear down Red Hat build of Keycloak (RHBK) on OpenShift or as a standalone RHEL zip install. |
| [`infra.ado.jira`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/jira/README.md) | Create Jira issues and subtasks from track templates for ADO automation workflows. |
| [`infra.ado.jira_stories`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/jira_stories/README.md) | Create and manage Jira stories and optional subtasks from selected track templates. |
| [`infra.ado.kafka_install`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/kafka_install/README.md) | Install the AMQ Streams / Kafka operator and related resources on OpenShift. |
| [`infra.ado.netbox_oidc`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/netbox_oidc/README.md) | Wire NetBox login to Keycloak / RHBK OIDC (client `netbox`). |
| [`infra.ado.ocp_aap_hub_harden`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_aap_hub_harden/README.md) | Harden AAP Hub for shared-Postgres LWLock stability (replicas/workers/maintenance). |
| [`infra.ado.ocp_acm`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_acm/README.md) | Install Advanced Cluster Management (ACM) and deploy MultiClusterHub on OpenShift. |
| [`infra.ado.ocp_acs`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_acs/README.md) | Install Red Hat Advanced Cluster Security (ACS) Central and related resources on OpenShift. |
| [`infra.ado.ocp_alt_routes`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_alt_routes/README.md) | Ensure alternate OpenShift Routes exist from a configured candidate list. |
| [`infra.ado.ocp_awspca`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_awspca/README.md) | Manage an AWS PCA-backed AWSPCAClusterIssuer and its credentials Secret in OpenShift/Kubernetes. |
| [`infra.ado.ocp_cert_manager`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_cert_manager/README.md) | Install and configure cert-manager on OpenShift, with optional AWS PCA intermediate CA material. |
| [`infra.ado.ocp_compliance_install`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_compliance_install/README.md) | Validate that Compliance Operator pods are present and at least one pod reaches the Running phase. |
| [`infra.ado.ocp_compliance_profiles`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_compliance_profiles/README.md) | Create or delete a Compliance Operator ComplianceProfile resource. |
| [`infra.ado.ocp_compliance_remediation`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_compliance_remediation/README.md) | Trigger an ACS remediation request by calling the ACS API when remediation is enabled. |
| [`infra.ado.ocp_compliance_scan`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_compliance_scan/README.md) | Create Compliance Operator scan resources for scheduled or immediate scan execution. |
| [`infra.ado.ocp_component_route`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_component_route/README.md) | Resolve primary and alternate OpenShift Route hostnames for an ADO component. |
| [`infra.ado.ocp_console_banner`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_console_banner/README.md) | Manage OpenShift console notification banners using ConsoleNotification resources. |
| [`infra.ado.ocp_data_foundation`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_data_foundation/README.md) | Create an OpenShift Data Foundation (ODF) StorageCluster. |
| [`infra.ado.ocp_descheduler`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_descheduler/README.md) | Install and configure the Kubernetes Descheduler on OpenShift. |
| [`infra.ado.ocp_devspaces`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_devspaces/README.md) | Install or remove the OpenShift Dev Spaces operator and related resources. |
| [`infra.ado.ocp_devspaces_user_config`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_devspaces_user_config/README.md) | Configure per-user OpenShift Dev Spaces resources (certs, bashrc ConfigMap, PVC). |
| [`infra.ado.ocp_dev_hub`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_dev_hub/README.md) | Deploy Red Hat Developer Hub (RHDH) on OpenShift via the RHDH operator with optional GitLab catalog and Keycloak OIDC. |
| [`infra.ado.ocp_discover_routes`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_discover_routes/README.md) | Discover OpenShift Route hostnames cluster-wide and build alternate-route candidates. |
| [`infra.ado.ocp_efs_csi`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_efs_csi/README.md) | Create an AWS EFS CSI StorageClass on OpenShift. |
| [`infra.ado.ocp_gitlab_runner`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_gitlab_runner/README.md) | Deploy GitLab Runner to OpenShift using a Kubernetes deployment. |
| [`infra.ado.ocp_gitops`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_gitops/README.md) | Deploy and configure an OpenShift GitOps (Argo CD) instance and optional route. |
| [`infra.ado.ocp_htpasswd_admin`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_htpasswd_admin/README.md) | Create or remove an htpasswd OAuth identity provider and admin user on OpenShift. |
| [`infra.ado.ocp_iscsi_storage`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_iscsi_storage/README.md) | Install Synology CSI (iSCSI) on OpenShift using kubernetes.core.k8s. |
| [`infra.ado.ocp_ldap_auth`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_ldap_auth/README.md) | Configure OpenShift LDAP OAuth authentication from vault ldap_config. |
| [`infra.ado.ocp_logging`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_logging/README.md) | Configure OpenShift Cluster Log Forwarder (for example Splunk) for cluster logging. |
| [`infra.ado.ocp_loki`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_loki/README.md) | Create or delete a LokiStack for OpenShift logging and observability. |
| [`infra.ado.ocp_minio`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_minio/README.md) | Deploy MinIO object storage on OpenShift with API/console Routes and optional Keycloak OIDC console login. |
| [`infra.ado.ocp_namespace`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_namespace/README.md) | Create OpenShift/Kubernetes namespaces. |
| [`infra.ado.ocp_nfs_storage`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_nfs_storage/README.md) | Install the NFS CSI driver via Helm and configure NFS-backed storage on OpenShift. |
| [`infra.ado.ocp_oadp`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_oadp/README.md) | Configure OpenShift API for Data Protection (OADP) DataProtectionApplication and credentials. |
| [`infra.ado.ocp_oidc_auth`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_oidc_auth/README.md) | Configure OpenShift OIDC OAuth authentication (typically via Keycloak/RHBK). |
| [`infra.ado.ocp_operator_defaults`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_operator_defaults/README.md) | Resolve OpenShift operator PackageManifest defaults for downstream operator installs. |
| [`infra.ado.ocp_operator_subscription`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_operator_subscription/README.md) | Create or update OLM OperatorGroups and Subscriptions for OpenShift operators. |
| [`infra.ado.ocp_operatorgroups`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_operatorgroups/README.md) | Create or delete OperatorGroups used by OpenShift operator installs. |
| [`infra.ado.ocp_print_crd`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_print_crd/README.md) | Discover an operator Subscription in a namespace and print related CRD and operator info. |
| [`infra.ado.ocp_pull_secrets`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_pull_secrets/README.md) | Manage the cluster pull-secret (registry auth) for OpenShift. |
| [`infra.ado.ocp_quay`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_quay/README.md) | Install or remove Red Hat Quay (namespace, PVC, operator) on OpenShift. |
| [`infra.ado.ocp_rhbk_client_secrets`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_rhbk_client_secrets/README.md) | Fetch RHBK client secrets and materialize them as OpenShift Secrets for components. |
| [`infra.ado.ocp_routes`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_routes/README.md) | List and print OpenShift Route hostnames for one or more namespaces. |
| [`infra.ado.ocp_search_dirsrv`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_search_dirsrv/README.md) | Locate a running DirSrv pod for subsequent directory operations. |
| [`infra.ado.ocp_secret_replicator`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_secret_replicator/README.md) | Replicate a Kubernetes Secret to namespaces and/or HashiCorp Vault. |
| [`infra.ado.ocp_service_accounts`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_service_accounts/README.md) | Create or delete OpenShift/Kubernetes ServiceAccounts across target namespaces. |
| [`infra.ado.ocp_virtualization`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_virtualization/README.md) | Build lab Virt VM specs (DataSource + Multus) and create via `infra.openshift_virtualization_ops.vm_provision`. |
| [`infra.ado.ocp_zabbix`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_zabbix/README.md) | Deploy Zabbix monitoring on OpenShift (MariaDB, Zabbix server, web UI, and Route). |
| [`infra.ado.ocp_wait_operator`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_wait_operator/README.md) | Wait until an OLM Operator CSV reaches the installed/succeeded state. |
| [`infra.ado.ocp_wait_pods`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/ocp_wait_pods/README.md) | Wait until pods in a namespace are running and ready. |
| [`infra.ado.rhbk_client`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_client/README.md) | Manage Red Hat build of Keycloak (RHBK) clients. |
| [`infra.ado.rhbk_client_scope`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_client_scope/README.md) | Manage Red Hat build of Keycloak (RHBK) client scopes. |
| [`infra.ado.rhbk_groups`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_groups/README.md) | Manage Red Hat build of Keycloak (RHBK) groups. |
| [`infra.ado.rhbk_manage_federation`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_manage_federation/README.md) | Manage Red Hat build of Keycloak (RHBK) user federation (for example LDAP). |
| [`infra.ado.rhbk_manage_idp`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_manage_idp/README.md) | Configure and remove identity provider settings for Red Hat build of Keycloak. |
| [`infra.ado.rhbk_realm`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_realm/README.md) | Manage Red Hat build of Keycloak (RHBK) realms. |
| [`infra.ado.rhbk_setup_mapper`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_setup_mapper/README.md) | Manage LDAP group mapper components in Red Hat build of Keycloak. |
| [`infra.ado.rhbk_users`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhbk_users/README.md) | Manage Red Hat build of Keycloak users and user-group membership operations. |
| [`infra.ado.rhel_cron`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_cron/README.md) | Manage special cron schedule entries (@hourly, @daily, @weekly, @monthly, @yearly, @annually, @reboot). |
| [`infra.ado.rhel_ext_system_roles`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_ext_system_roles/README.md) | Thin adapter/wrapper to call RHEL System Roles by short keys. |
| [`infra.ado.rhel_facts`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_facts/README.md) | Gather extended RHEL host facts (tuned, firewalld, memory, release, time). |
| [`infra.ado.rhel_mount`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_mount/README.md) | Mount filesystems (NFS, CIFS, local) with optional auto-detection of filesystem type. |
| [`infra.ado.rhel_patching`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_patching/README.md) | Comprehensive patching for Red Hat Enterprise Linux (RHEL) servers. |
| [`infra.ado.rhel_repos`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_repos/README.md) | Manage repository enable and disable operations on Red Hat Enterprise Linux systems. |
| [`infra.ado.rhel_sat_reg`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_sat_reg/README.md) | Register or unregister RHEL hosts with Red Hat Satellite via subscription-manager. |
| [`infra.ado.rhel_stig_cac`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_stig_cac/README.md) | Apply DISA STIG Compliance-as-Code on RHEL 8, 9, and 10 with OpenSCAP. |
| [`infra.ado.rhel_services_management`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/rhel_services_management/README.md) | Manage RHEL system services with version-aware paths for RHEL 8/9/10. |
| [`infra.ado.satellite_config`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/satellite_config/README.md) | Configure a Red Hat Satellite server after installation. |
| [`infra.ado.satellite_content_view`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/satellite_content_view/README.md) | Manage Red Hat Satellite Content Views with create, publish, and promote actions. |
| [`infra.ado.satellite_install`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/satellite_install/README.md) | Prepare and install a Red Hat Satellite host on supported RHEL systems. |
| [`infra.ado.satellite_oidc`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/satellite_oidc/README.md) | Wire Satellite login to Keycloak / RHBK OIDC (client `ado-satellite`). |
| [`infra.ado.terraform`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/terraform/README.md) | Run Terraform or OpenTofu plan/apply/destroy for customer stacks in a generated bootstrap repository. |
| [`infra.ado.vm_image_management`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/vm_image_management/README.md) | Create a qcow2 virtual machine image from an existing base image. |

## Using this collection

```bash
ansible-galaxy collection install infra.ado
```

You can also include it in a `requirements.yml` file and install it via
`ansible-galaxy collection install -r requirements.yml` using the format:

```yaml
collections:
  - name: infra.ado
```

To upgrade the collection to the latest available version, run the following
command:

```bash
ansible-galaxy collection install infra.ado --upgrade
```

You can also install a specific version of the collection, for example, if you
need to downgrade when something is broken in the latest version (please report
an issue in this repository). Use the following syntax where `X.Y.Z` can be any
[available version](https://galaxy.ansible.com/infra/ado):

```bash
ansible-galaxy collection install infra.ado:==X.Y.Z
```

See
[Ansible Using Collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)
for more details.

## Release notes

See the
[changelog](https://github.com/redhat-cop/infra.automation-development-office/blob/main/CHANGELOG.rst).

## Testing

### Molecule scenarios

Collection integration scenarios live under `extensions/molecule/` and are executed by the CI workflow.

Run scenarios locally before opening a PR.

From the collection root:

```bash
cd /path/to/your/git/checkout/infra.ado
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix --force -p ~/.ansible/collections
```

Set collection path in your shell:

```bash
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
```

For fish shell:

```fish
set -gx ANSIBLE_COLLECTIONS_PATH "$HOME/.ansible/collections:/usr/share/ansible/collections"
```

Run a scenario from `extensions/`:

```bash
cd /path/to/your/git/checkout/infra.ado/extensions
molecule test -s integration_rhel_cron_full_special
```

### GitHub Actions manual runs

The `Ansible Collection CI/CD` workflow supports manual execution through `workflow_dispatch`.

- Each Molecule scenario is exposed as a boolean input in the Run workflow form.
- **Run security_checks.py on collection roles** runs `scripts/security_checks.py` and
  `scripts/security_data_exposure_scan.py` on `roles/`.
- Checked scenarios are included in the test matrix.
- Matrix jobs run in parallel.

Pull requests run Molecule for all scenarios under `extensions/molecule/` except
those listed in `extensions/molecule/pr_exclude.txt` (currently all `ocp_*`
scenarios, which need a live OpenShift cluster).

To run OpenShift scenarios in CI, use **Ansible Collection CI/CD** → **Run workflow** and enable
**Run all ocp_* Molecule scenarios** (configure `K8S_AUTH_HOST`, `K8S_AUTH_API_KEY`, and
`K8S_AUTH_VERIFY_SSL` as repository secrets first).

Pull requests also run the standalone **Security Check** workflow automatically.
Results appear in the workflow job summary and the `security-check-report` artifact. This check is
not enforced in the PR gate yet. You can also re-run it from the **Security Check** workflow page.

## More information

- [Ansible collection development forum](https://forum.ansible.com/c/project/collection-development/27)
- [Ansible User guide](https://docs.ansible.com/ansible/devel/user_guide/index.html)
- [Ansible Developer guide](https://docs.ansible.com/ansible/devel/dev_guide/index.html)
- [Ansible Collections Checklist](https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html)
- [Ansible Community code of conduct](https://docs.ansible.com/ansible/devel/community/code_of_conduct.html)
- [The Bullhorn (the Ansible Contributor newsletter)](https://docs.ansible.com/ansible/devel/community/communication.html#the-bullhorn)
- [News for Maintainers](https://forum.ansible.com/tag/news-for-maintainers)

## Licensing

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.
