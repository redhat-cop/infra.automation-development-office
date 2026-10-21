# Role: infra.automation_development_office.acs_upload_policies

Upload Red Hat Advanced Cluster Security (ACS) policy and report configuration
JSON files from a local path or git repository to ACS Central.

Policy files are applied with validated
[`infra.rhacs_configuration.rhacs_policy`](https://galaxy.ansible.com/ui/repo/published/infra/rhacs_configuration/)
(or `rhacs_policy_import` when the JSON is an export bundle with a `policies`
list). Report configuration JSON still uses the Central REST API (no matching
`rhacs_policy` path).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core on a host with network access to ACS Central
- Collection: `infra.rhacs_configuration`
- ACS Central admin credentials (`acs_admin_user` / `acs_admin_password` or
  `ocp_acs_admin_user` / `ocp_acs_admin_password`)
- Policy or report source files as plain `.json` or templated `.json.j2`
- Optional git access when `acs_policies_source_type` or
  `acs_reports_source_type` is `git`

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `acs_policies_source` | Local directory path or git URL for ACS policy JSON files. |
| `acs_policies_source_type` | Source type: `path` (default) or `git`. |
| `acs_policies_version` | Git ref when cloning policy source. Default `HEAD`. |
| `acs_policies_overwrite` | When importing export bundles, overwrite existing user policies. Default `true`. |
| `acs_reports_source` | Local directory path or git URL for ACS report configs. |
| `acs_reports_source_type` | Report source type: `path` (default) or `git`. |
| `acs_reports_version` | Git ref when cloning report source. Default `HEAD`. |
| `acs_central_url` | Full ACS Central API base URL. Derived from route/namespace when unset. |
| `acs_namespace` | ACS namespace for route derivation. Default `stackrox`. |
| `acs_route_name` | ACS route name prefix. Default `central`. |
| `acs_admin_user` | ACS API username. Default `admin`. |
| `acs_admin_password` | ACS API password from vault or extra-vars. |
| `acs_skip_validate_certs` | Skip TLS verify for `rhacs_*` modules. Default `true`. |

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  vars:
    acs_central_url: https://central-stackrox.apps.example.com
    acs_admin_password: "{{ vault_acs_admin_password }}"
    acs_policies_source_type: git
    acs_policies_source: https://github.com/example/acs-policies.git
    acs_policies_version: main
  roles:
    - role: infra.automation_development_office.acs_upload_policies
```

Plain JSON files are applied as-is; `.json.j2` files are rendered with Ansible
before upload. Single-policy documents use `rhacs_policy`; export bundles use
`rhacs_policy_import`.

## 🧪 Role Molecule Testing

This role targets live ACS Central endpoints. No Molecule scenario is shipped;
run against a lab cluster after ACS install and confirm policies appear in the
ACS UI.

```bash
ansible-playbook playbooks/acs/ado-acs-policies-bootstrap.yml \
  -e acs_policies_source=/path/to/policies \
  --vault-password-file .vault_pass
```

## 📁 Role Structure

```text
roles/acs_upload_policies/
  README.md
  meta/
  tasks/
    main.yml
    upload-one.yml
```
