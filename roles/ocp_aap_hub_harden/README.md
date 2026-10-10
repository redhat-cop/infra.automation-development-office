# Role: infra.ado.ocp_aap_hub_harden

Separate Automation Hub onto dedicated Postgres when it still shares
Controller PG, then pin replicas/workers and install a maintenance CronJob
that vacuums `core_apiappstatus` on the dedicated Hub database.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core with `kubernetes.core` collection
- OpenShift/Kubernetes API access to the AAP namespace
- Existing `AnsibleAutomationPlatform` and `AutomationHub` custom resources
- Opt-in from preflight **AAP → AAP tools → Separate Hub onto dedicated Postgres**
  (`component_options.aap: [dedicated_hub_postgres]`) so bootstrap generates
  `playbooks/aap/ado-aap-hub-harden-bootstrap.yml` and the matching job
  template. The role is not run during the bootstrap apply itself.

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_aap_hub_harden_namespace` | Namespace containing AAP CRs. Empty discovers the first `AnsibleAutomationPlatform`. |
| `ocp_aap_hub_harden_aap_name` | `AnsibleAutomationPlatform` CR name. Empty discovers it. |
| `ocp_aap_hub_harden_automationhub_name` | `AutomationHub` CR name. Empty discovers it (`aap-hub`, `aap-chad-hub`, …). |
| `ocp_aap_hub_harden_separate_database` | Create dedicated Postgres and migrate when Hub is not already on the dedicated secret. Default `true`. |
| `ocp_aap_hub_harden_sts_name` | Dedicated Postgres StatefulSet/service name. Default `aap-hub-dedicated-postgres`. |
| `ocp_aap_hub_harden_pvc_name` | Dedicated Postgres PVC name. Default `aap-hub-dedicated-postgres-data`. |
| `ocp_aap_hub_harden_admin_secret` | Dedicated Postgres admin secret. Created only if missing. Default `aap-hub-dedicated-postgres-admin`. |
| `ocp_aap_hub_harden_storage_class` | Dedicated PVC storage class. Empty copies the shared Controller Postgres PVC. |
| `ocp_aap_hub_harden_storage_size` | Dedicated PVC size. Default `20Gi`. |
| `ocp_aap_hub_harden_postgres_image` | Dedicated STS image. Empty copies the shared Controller Postgres image. |
| `ocp_aap_hub_harden_postgres_pod` | Pod used for vacuum/LWLock cleanup. Default `aap-hub-dedicated-postgres-0`. |
| `ocp_aap_hub_harden_postgres_secret` | Unmanaged Hub DB secret. Default `external-hub-postgres-configuration`. |
| `ocp_aap_hub_harden_api_replicas` | Hub API replica count. Default `1`. |
| `ocp_aap_hub_harden_content_replicas` | Hub content replica count. Default `1`. |
| `ocp_aap_hub_harden_gunicorn_api_workers` | Gunicorn API workers. Default `1`. |
| `ocp_aap_hub_harden_install_maintenance_cronjob` | Install stability CronJob. Default `true`. |
| `ocp_aap_hub_harden_cron_schedule` | CronJob schedule. Default `*/15 * * * *`. |

Reruns are idempotent: when Hub already uses
`external-hub-postgres-configuration`, migrate is skipped and only the
worker pins plus CronJob are applied.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_aap_hub_harden
      vars:
        # Leave names empty to discover AAP/Hub CRs on the cluster.
        ocp_aap_hub_harden_separate_database: true
```

See `ado-preflight-ui/docs/hub-recovery.md` for the permanent dedicated-DB
layout and emergency recovery (restart dedicated Hub Postgres only).

## 🧪 Role Molecule Testing

This role targets live OpenShift clusters with AAP Hub installed. No Molecule
scenario is shipped; contract coverage lives in
`extensions/molecule/integration_component_regressions/check_runner.py`.
Apply against a lab cluster and confirm Hub CR replica counts, dedicated DB
secret pins, and the `aap-hub-stability` CronJob.

```bash
ansible-playbook -i localhost, -c local playbooks/aap/ado-aap-hub-harden-bootstrap.yml
```

## 📁 Role Structure

```text
roles/ocp_aap_hub_harden/
  README.md
  defaults/
  meta/
  tasks/
    main.yml
    discover.yml
    separate_database.yml
    install_cronjob.yml
```
