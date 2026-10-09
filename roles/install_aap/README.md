# Role: infra.ado.install_aap

Install Ansible Automation Platform using validated **`infra.aap_utilities`**:

| Target | Validated roles |
|--------|-----------------|
| **openshift** | `aap_ocp_install` (+ ADO Fernet/DB reset and license attach) |
| **rhel** | `aap_setup_download` → `aap_setup_prepare` → `aap_setup_install` (`aap_remove` when absent) |

## Role Author

Automation Development Office

## ✅ Role Requirements

- Collection: `infra.aap_utilities` (Automation Hub / Galaxy)
- **OpenShift:** Python `kubernetes`, `kubernetes.core` / `redhat.openshift`, cluster credentials.
  The AAP operator must already be available in the cluster catalog
  (typically ``redhat-operators`` /
  ``ansible-automation-platform-operator``). This role does not add that
  catalog source.
- **RHEL:** installer download credentials / local tarball, inventory node map, become as needed

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `install_aap_state` | `present` (default) or `absent`. Legacy `state` accepted. |
| `install_aap_target` | `openshift` or `rhel`. Auto-detects from `aap_ocp_install_*` vs `aap_setup_prep_inv_nodes` when empty. |
| `aap_ocp_install_*` | Pass-through to `infra.aap_utilities.aap_ocp_install` plus ADO `reset_database` / license helpers. |
| `aap_ocp_install_license_mode` | `none` (default), `manifest`, or `rhn`. `none`/`skip` installs the operator and platform only. Attach a subscription later with `aap_ocp_install_license_only` or the AAP wizard. |
| `aap_ocp_install_license_only` | When `true`, skip operator install and only run license attach. |
| `aap_ocp_install_reset_database` | When `true`, wipe leftover AAP Fernet secrets and Postgres PVCs before install. Default `false` (greenfield). Missing CR / 403 is skipped, not a hard fail. |
| `aap_setup_*` | Pass-through to `aap_setup_download` / `prepare` / `install`. |
| `install_aap_rhel_download` | Run download role (default `true`). |
| `install_aap_rhel_prepare` | Run prepare role (default `true`). |
| `install_aap_rhel_install` | Run install role (default `true`). |

## 🚀 Role Usage

### OpenShift

```yaml
- name: Install AAP on OpenShift
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.install_aap
      vars:
        install_aap_target: openshift
        aap_ocp_install_namespace: aap
        aap_ocp_install_connection:
          host: https://api.example.com:6443
          api_key: "{{ vault_ocp_token }}"
          validate_certs: false
        aap_ocp_install_operator:
          channel: stable-2.7
        aap_ocp_install_platform:
          instance_name: aap
          component_deployment: unified
        aap_ocp_install_controller:
          install: true
```

### RHEL / non-OpenShift

```yaml
- name: Install AAP on RHEL
  hosts: bastion
  become: true
  roles:
    - role: infra.ado.install_aap
      vars:
        install_aap_target: rhel
        aap_setup_down_type: setup-bundle
        aap_setup_prep_inv_nodes:
          automationcontroller:
            aap.example.com:
          database:
            aap.example.com:
        aap_setup_prep_inv_vars:
          all:
            admin_password: "{{ vault_aap_admin_password }}"
```

Contoller bootstrap calls this role from
`ado-aap-ocp-install-bootstrap.yml` (OpenShift) or
`ado-aap-rhel-install-bootstrap.yml` (standalone RHEL, inventory host
`bastion`). Prefer `infra.aap_utilities.*` directly only when you do not need
ADO reset/license helpers.

When `aap_ocp_install_license_mode` is `none`/`skip`, a live platform/gateway
route is enough for install success. `aap_ocp_install` may still wait for
controller/hub/eda routes that only appear after a subscription; ADO accepts
that wait failure so you can license later.

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via Contoller bootstrap
JTs (`ado-aap-ocp-install-bootstrap`, `ado-aap-rhel-install-bootstrap`) or a
local playbook against lab inventory.

## 📁 Role Structure

```text
roles/install_aap/
  README.md
  defaults/
  tasks/
    main.yml
    openshift.yml
    rhel.yml
    reset_stale_database.yml
    activate_license.yml
    accept_unlicensed_platform.yml
```
