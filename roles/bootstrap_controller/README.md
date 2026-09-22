# Role: infra.ado.bootstrap_controller

Generate and apply Ansible Automation Platform controller objects for an ADO
bootstrap repository.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- A reachable AAP controller or automation controller endpoint
- Controller credentials supplied through environment variables, inventory, or
  generated group variables
- Controller collections listed in `collections/requirements.yml`
- Generated controller configuration files under `configs/controller`,
  `configs/job_templates`, and `configs/workflows`

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `bootstrap_controller_enabled_objects` | Ordered list of controller object groups to manage. |
| `bootstrap_controller_generate_job_templates_from_manifest` | Enables rendering job template definitions from bundled bootstrap manifests. |
| `bootstrap_controller_aap_connectivity_check_enabled` | Checks AAP controller API connectivity and authentication before applying controller objects. Defaults to `true`. |
| `bootstrap_controller_aap_smoke_test_enabled` | Launches a harmless AAP job template before applying controller objects. Defaults to `true`. |
| `bootstrap_controller_aap_smoke_test_job_template` | Job template used for the AAP smoke test. Defaults to `Demo Job Template`. |
| `bootstrap_controller_aap_install_during_bootstrap` | When true, run `infra.ado.install_aap` (OpenShift / `aap_utilities.aap_ocp_install`) before apply and omit the Install AAP JT. |
| `aap_auth_configure_gateway` | When true (from preflight `aap.auth`), apply `gateway_authenticators` / `gateway_authenticator_maps` on AAP 2.5+. |
| `gateway_authenticators` | Automation Gateway authenticator definitions (Keycloak OIDC, LDAP, SAML). |
| `gateway_authenticator_maps` | Authenticator map rules (superuser / organization). |
| `bootstrap_controller_organization` | Default organization used for generated controller objects. |
| `bootstrap_controller_inventory_name` | Default inventory assigned to generated job templates. |
| `bootstrap_controller_local_inventory_name` | Local bootstrap inventory name. Defaults to `bootstrap_controller_inventory_name`. |
| `bootstrap_controller_rhel_inventory_name` | RHEL managed-host inventory used by RHEL patching, Satellite registration, IDM client, compliance, and STIG job templates. |
| `bootstrap_controller_idm_inventory_name` | IDM server inventory used by IDM server, replica, DNS, topology, sudo, and server settings job templates. |
| `bootstrap_controller_satellite_inventory_name` | Satellite server inventory used by Satellite install, configure, and content-view job templates. |
| `bootstrap_controller_project_name` | Default project assigned to generated job templates. |
| `bootstrap_controller_execution_environment_name` | Default execution environment assigned to generated job templates. |
| `bootstrap_controller_controller_organizations` | Organization definitions to create or update. |
| `bootstrap_controller_controller_credentials` | Credential definitions to create or update. |
| `bootstrap_controller_controller_projects` | Project definitions to create or update. |
| `bootstrap_controller_controller_inventories` | Inventory definitions to create or update. |
| `bootstrap_controller_templates` | Job template definitions loaded from generated YAML. |
| `bootstrap_controller_workflow_job_templates` | Workflow job template definitions loaded from generated YAML. |
| `bootstrap_controller_controller_labels` | Controller labels to create. Generated runs include an organization label such as `ADO` alongside component labels such as `ADO | rhel`. |
| `bootstrap_controller_hub_publish_timeout` | Hub collection upload timeout (seconds). Defaults to `900`. |
| `bootstrap_controller_hub_publish_verify_retries` | Pulp import/promote poll retries. Defaults to `60` (~10m with delay `10`). |
| `bootstrap_controller_hub_publish_large_bytes` | Tarball size threshold for the large-collection wait path. Defaults to `30000000`. |
| `bootstrap_controller_hub_publish_large_verify_retries` | Pulp poll retries for large tarballs. Defaults to `120` (~20m). |
| `bootstrap_controller_hub_ee_skopeo_retry_times` | skopeo `--retry-times` for Hub EE push. Defaults to `8`. |
| `bootstrap_controller_hub_ee_push_retries` | Ansible retries around Hub EE skopeo push (502/gateway flakes). Defaults to `5`. |

## Install / configure matrix

Generated job templates follow the same OpenShift vs RHEL split as the collection
README. ✅ = JT / playbook generated when selected. ❌ = not generated.

### Install

| Component | OpenShift | RHEL / Linux |
|-----------|:---------:|:------------:|
| AAP | ✅ | ❌ |
| ACS / ACM / Cert Manager / Dev Spaces / DirSrv / ECK / GitOps / GitLab / Grafana / Kafka / OADP / PEGA / Quay / RHBK | ✅ | ❌ |
| Satellite | ❌ | ✅ |
| IdM (server / replica) | ❌ | ✅ |
| RHEL OS / patching / compliance / STIG | ❌ | ❌ |
| OpenShift base cluster | ❌ | ❌ |

### Configure

| Component | OpenShift | RHEL / Linux |
|-----------|:---------:|:------------:|
| AAP Controller objects (org, project, inventories, JTs, workflows) | ✅ | ❌ |
| OpenShift prep (htpasswd, banner, LDAP, OAuth, routes, pull secret, CSI, image registry) | ✅ | ❌ |
| Platform apps above (deploy+configure / options) | ✅ | ❌ |
| Satellite configure / content view / client registration | ❌ | ✅ |
| IdM client / DNS / AD trust / settings / sudo / topology | ❌ | ✅ |
| RHEL patch / compliance / STIG | ❌ | ✅ |

## 🚀 Role Usage

```yaml
- name: Apply generated ADO controller configuration
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.bootstrap_controller
      vars:
        bootstrap_controller_organization: ado-lab
        bootstrap_controller_project_name: ado-project
        bootstrap_controller_inventory_name: ado-inventory
```

## 🧪 Role Molecule Testing

This role is normally validated through the bootstrap scaffolding playbook and
targeted lint checks because it talks to a live AAP controller.

Generated workflows use simplified workflow nodes so the AAP configuration
collection creates both the workflow template and its links reliably.
The apply path maps generated workflow files to `controller_workflows`, which
is the dispatcher variable used by `infra.aap_configuration` for workflow job
templates.

Generated AAP 2.5+ runs create the organization name as a normal org-scoped
controller label and add component labels to generated templates. The AAP
Automation Templates "Domains" toolbar is a user interface customization and is
not managed by the supported controller or gateway configuration objects used by
this role.

Generated patching workflows are created when RHEL, Satellite, and IDM are
selected. The workflow chain is `Register Host to Satellite` ->
`RHEL Patch Host` -> `IdM Manage Client`. Selecting only the patching group
(or RHEL without compliance/STIG) creates the patch-host job template only;
Compliance and STIG job templates are generated when those components (or the
matching RHEL options) are selected.

Generated RHEL bootstrap workflows are created when the selected component set
includes RHEL, Satellite, IDM, compliance, and STIG. The workflow chain is
`Register Host to Satellite` -> `RHEL Patch Host` -> `IdM Manage Client` ->
`RHEL Compliance` -> `RHEL STIG Hardening`.

Generated Satellite workflows are created when Satellite is selected and run
`Satellite Server Install` -> `Satellite Server Configure`.

Generated IdM AD trust automation is created when the IdM AD Trust option is
selected (`idm_ad_trust_install`). That adds the
`ADO | IdM Manage AD Trust` job template from
`playbooks/idm/ado-manage-ad-trust-bootstrap.yml` and targets the IdM inventory.
See `roles/idm_ad_trust/README.md` for trust prerequisites (AD conditional
forwarder for two-way trust) and client SSSD notes.

Generated OpenShift workflows are created when OpenShift is selected. The
workflow starts with generated OpenShift prep jobs, runs the nested
**Cert Manager Workflow** (deploy plus optional IdM ACME / AWS PCA / default
ingress nodes, pruned by mode), then fans out through **RHBK Workflow** and
selected platform services such as Grafana, GitLab, Pega, Kafka, AAP, ECK,
GitOps, 389ds, OADP, Quay, ACS, and ACM. The console banner job uses
`playbooks/openshift/ado-configure-console-banner-bootstrap.yml` and its survey
offers `add`, `update`, and `delete`; `update` removes ADO-managed banners and
creates one replacement banner. Workflow nodes are pruned when their job
templates were not generated, so single-app and partial OpenShift selections
remain valid.

```bash
ansible-lint --offline roles/bootstrap_controller
yamllint roles/bootstrap_controller/tasks roles/bootstrap_controller/defaults
```

## 📁 Role Structure

```text
roles/bootstrap_controller/
  defaults/main.yml
  files/job_templates/
  files/workflows/
  tasks/
  templates/
  vars/main.yml
  README.md
```

Workflow seeds live only under ``files/workflows/`` (copied into the bootstrap
repo). Do not keep a parallel ``templates/workflows/`` tree.

Project synchronization waits for an existing update after source configuration
changes. It reuses that update only when its SCM URL and branch match the desired
project. A differing-source update must finish before a new update is launched.
Timeouts and failed dependency installation stop bootstrap; an older successful
revision does not override the failure. The local
`integration_project_sync` Molecule scenario covers active, failed, pending,
different-branch and idle updates without contacting a Controller.
