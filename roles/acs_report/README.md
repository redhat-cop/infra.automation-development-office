# Role: infra.automation_development_office.acs_report

Generate Red Hat Advanced Cluster Security (RHACS) vulnerability reports from
Central's workload export API. The role uses ``ansible.builtin.get_url`` (Python
stdlib HTTP) plus the bundled parser. It does **not** require ``curl``.

## Role Author

Automation Development Office

## ✅ Role Requirements

- RHACS Central API reachable from the Ansible controller
- Bearer token (`acs_api_token`) or admin basic auth
- Optional: cluster kubeconfig when `acs_report_cve_enrich_cluster` is enabled

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `acs_report_mode` | `raw` \| `rhsource` \| `age` \| `all`. Default `rhsource`. |
| `acs_report_outdir` | Output directory for CSV / summary JSON / text. |
| `acs_central_url` | Central base URL. Derived from route + `app_domain` when empty. |
| `acs_api_token` | Bearer token (preferred). Also accepts `ROX_API_TOKEN` env. |
| `acs_admin_user` / `acs_admin_password` | Basic auth fallback when token unset. |
| `acs_namespace` | Namespace for route derivation. Default `stackrox`. |
| `acs_report_all_scope` | Expand raw/rhsource to all product groups. |
| `acs_report_rhsre` | ROSA/SRE responsibility boundary only. |
| `acs_report_component` | Limit to one group (`acm`, `devspaces`, …). |
| `acs_report_show_sev` | Add Critical/High columns. |
| `acs_report_cve_enrich` | Enable acs-cve-plugin enrichment. Default `false`. |
| `acs_report_cve_enrich_security_view` | Write ATO-style `*-fp.csv` and `*-poam.csv`. |
| `acs_report_cve_enrich_actionable_only` | Pass `--actionable-only`. |
| `acs_report_cve_enrich_rh_images_only` | Pass `--rh-images-only`. |
| `acs_report_cve_enrich_cluster` | Install `acs-cve-tool[cluster]`. |
| `acs_report_cve_enrich_sort` | `status` \| `age` \| `severity`. Default `status`. |

Mode summary:

| `acs_report_mode` | Output |
|-------------------|--------|
| `raw` | Live workloads, Critical+Important, all sources |
| `rhsource` | Red Hat CVE/errata source only |
| `age` | Red Hat source, age buckets `>15` / `>30` / `>90` days |
| `all` | Scrubbed CSV of all severities/sources |

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.acs_report
      vars:
        acs_report_mode: rhsource
        acs_report_show_sev: true
        acs_central_url: https://central-stackrox.apps.example.com
        acs_api_token: "{{ vault_acs_api_token }}"
        acs_report_outdir: /tmp/acs-reports
        acs_report_cve_enrich: true
```

Bootstrap registers **ADO | ACS RHACS Report (CVE Enriched)** and appends it
to the RHACS report workflow after the age report.

Local optional wrapper (still uses ``curl``; the role does not):

```bash
export ROX_ENDPOINT=https://central-stackrox.apps.example.com
export ROX_API_TOKEN=...
bash roles/acs_report/files/rhacs-report.sh --rhsource --sev
```

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via Contoller workflow
**ADO | ACS Report** or JT `ado-acs-report-cve-enriched-bootstrap`.

## 📁 Role Structure

```text
roles/acs_report/
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
  tasks/cve_enrich.yml
  README.md
  files/
    rhacs-report.sh
    rhacs_report_parser.py
    grafana/rhacs-vulnerability-overview.json
```

Artifacts: Slack-friendly text table, `RHACS_summary_*.json`, scrubbed/enriched
CSVs, optional Grafana dashboard under `files/grafana/`.
