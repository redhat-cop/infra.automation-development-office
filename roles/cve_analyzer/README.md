# Role: infra.automation_development_office.cve_analyzer

RHACS CVE Analyzer: export findings from ACS Central, optionally enrich them,
publish Grafana posture/triage dashboards and Prometheus metrics, and run
optional CVE Intelligence collection. Phase 0 experimental panels are gated to
allowlisted non-production dashboard UIDs only.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Contoller/CLI must set ``cve_analyzer_action`` explicitly (no role default).
- ``env`` required when ``cve_analyzer_require_env`` is true (default).
- ACS Central URL + API token or admin password (``acs_central_url`` /
  ``acs_api_token`` or vault aliases).
- Grafana URL + admin credentials for publish actions.
- OpenShift ``host`` / ``token`` (or ``api_host`` / ``openshift_token``) for
  metrics, cluster inventory, and CVE Intel Postgres secret lookup.
- Execution environment with ``python3``, ``kubernetes.core``, and the Python
  packages the bundled scripts already expect (see role ``files/``).
- Distinct from ``acs_report`` (lighter Central CSV reports). Do not merge.

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `cve_analyzer_action` | **Required.** `fetch_export` \| `pipeline` \| `publish_grafana` \| `publish_rhacs_posture` \| `publish_metrics` \| `repair_posture_metrics` \| `cve_intel` \| `full` \| `enrichment`. |
| `cve_analyzer_data_dir` | Working directory. Empty → `/tmp/cve-analyzer-{{ env }}`. |
| `cve_analyzer_repair_mode` | For `repair_posture_metrics`: `repair` (default) or `verify`. |
| `cve_analyzer_metrics_input_dir` | Durable path with scrubbed CSV and/or `cve_posture.prom` for Contoller EEs that do not share `/tmp`. |
| `cve_analyzer_grafana_dashboard_backup_dir` | Persistent directory for pre-publish Grafana JSON backups. Required when the target UID already exists. Must not be EE `/tmp` (unless `cve_analyzer_grafana_dashboard_backup_allow_ephemeral` for local tests). |
| `cve_analyzer_grafana_dashboard_backup_allow_ephemeral` | Allow backup under `/tmp` for local/Molecule only. Default `false`. Never enable on Contoller. |
| `cve_analyzer_scrubbed_csv_retention_enabled` | After a successful Dashboard Build, retain the exact scrubbed CSV + `validation-meta.json` for independent panel verification. Default `false` (existing Contoller schedules unchanged). When `true`, retention failure **fails the job**. |
| `cve_analyzer_scrubbed_csv_retention_dir` | Durable mount for retention (NFS/PVC/host path). Required when retention is enabled. Must not be EE `/tmp` unless `cve_analyzer_scrubbed_csv_retention_allow_ephemeral`. Do not commit retained CSVs to Git. |
| `cve_analyzer_scrubbed_csv_retention_days` | Prune `job*` retention directories older than this many days. Default `30`. |
| `cve_analyzer_scrubbed_csv_retention_allow_ephemeral` | Allow retention under `/tmp` for local/Molecule only. Default `false`. Never enable on Contoller. |
| `cve_analyzer_run_enrichment` | Caller flag for `full` / `pipeline` / `publish_grafana`. Default `false`. Action `enrichment` does **not** mutate this; it sets per-invocation `cve_analyzer_effective_run_enrichment` so a later role include cannot inherit enrichment. |
| `cve_analyzer_vuln_dashboard_uid` | Live posture UID. Default `ado-rhacs-vuln-posture` (production; Phase 0 features refused). Contoller survey on Publish RHACS Posture / Full must set this — undeclared launch extra_vars are stripped. |
| `cve_analyzer_vuln_dashboard_title` | Grafana dashboard title for the selected UID (rename tests change title only). |
| `cve_analyzer_phase0_publish_only` | When true, refuse production UID/aliases before publish. Contoller survey default `true` for Phase 0 safety. |
| `cve_analyzer_phase0_feature_uids` | Extra approved nonprod UIDs for Lite / CVE Intel panels. |
| `cve_analyzer_cve_intel_panels` | Append Recent-reports panels on allowlisted UIDs only. Default `false`. |
| `cve_analyzer_cve_intel_enabled` | Run CVE Intelligence collection on `full` (or use action `cve_intel`). |
| `cve_analyzer_send_report_url` | Optional Contoller JT link for dashboard header. Empty omits. |
| `cve_analyzer_prometheus_datasource_uid` | Grafana Prometheus/Thanos datasource UID for Findings over time. Empty → auto-select when Grafana has exactly one Prometheus datasource; fail when zero or many (never invent a UID). |
| `cve_analyzer_metrics_namespace` | Namespace for `cve-analyzer-ns-metrics` ConfigMap/Deployment/Service/ServiceMonitor. Default `grafana`. |
| `cve_analyzer_print_banner` | Print endpoint banner/recap for `full` / `enrichment`. Default `true`. |
| `cve_analyzer_acs_*` / `cve_analyzer_grafana_*` | ACS/Grafana connection overrides; fall back to `acs_*` / `grafana_*`. |
| `cve_analyzer_ocp_*` | Resolved from `host`/`token` by `resolve_ocp_auth.yml`; feed task-scoped `K8S_AUTH_*` environments. |

Action summary:

| Action | Behavior |
|--------|----------|
| `full` | Auth → export → optional enrichment/triage → posture (creates metrics scrape stack + gauges) → optional ns metrics / CVE intel |
| `enrichment` | Auth → export → enrichment → triage Grafana → posture (one timing session; posture publishes gauges) |
| `fetch_export` | Auth + export/CSV only |
| `pipeline` | Auth + enrichment scripts (requires `cve_analyzer_run_enrichment`) |
| `publish_grafana` | Triage dashboard (+ ns metrics when OCP auth ready) |
| `publish_rhacs_posture` | Build/publish posture dashboard; ensure metrics ConfigMap/Deployment/Service/ServiceMonitor; merge `cve_posture_findings*` (+ Phase 0 gates) |
| `publish_metrics` | Ensure scrape stack; preserve in-cluster gauges across jobs; rebuild from scrubbed CSV when local `/tmp` is empty |
| `repair_posture_metrics` | Ad-hoc repair/verify of the scrape stack only. No ACS export. No Grafana dashboard overwrite. Not in the workflow. |
| `cve_intel` | CVE Intelligence collection only |

Findings over time requires the scrape stack in ``cve_analyzer_metrics_namespace``
(default ``grafana``). Order is Dashboard Build → Metrics Publish (assert
gauges in textfile) → Grafana Publish. ``METRICS_FAILED`` fails the Contoller
job **before** Grafana publish so a green job cannot ship an updated board with
empty trend panels. Contoller jobs do **not** share ``/tmp``; posture stores
gauges on ConfigMap key ``cve_posture.prom``, and ``publish_metrics`` restores
from that handoff key or rebuilds from a scrubbed CSV when local files are
missing. Merge replaces prior ``cve_posture_findings*`` families (no duplicate
series). Workload ensure uses fixed names + ``state: present`` (no second
Deployment/ServiceMonitor).

### Ad-hoc repair / verify (no ACS export)

```bash
# Repair missing ConfigMap/Deployment/Service/ServiceMonitor + restore gauges
ansible-playbook playbooks/cve_analyzer/ado-cve-analyzer-bootstrap.yml \
  -e env=preprod \
  -e cve_analyzer_action=repair_posture_metrics \
  -e cve_analyzer_repair_mode=repair \
  -e cve_analyzer_metrics_input_dir=/path/to/durable/artifacts \
  --ask-vault-pass

# Read-only verify (resources, gauges, endpoint, optional Prom series)
ansible-playbook playbooks/cve_analyzer/ado-cve-analyzer-bootstrap.yml \
  -e env=preprod \
  -e cve_analyzer_action=repair_posture_metrics \
  -e cve_analyzer_repair_mode=verify \
  --ask-vault-pass
```

Example durable input layout (must be readable by the Contoller EE):

```text
/path/to/durable/artifacts/
  cve_posture.prom          # optional
  RHACS_*_scrubbed.csv      # optional; used to rebuild gauges locally
```

If none of ConfigMap gauges, local ``cve_posture.prom``, or scrubbed CSV is
available, repair fails with a clear prerequisite message (does not invent
empty SUCCESS metrics). Contoller JT:
``ADO | CVE Analyzer | Repair Posture Metrics``.

## 🚀 Role Usage

```yaml
- name: CVE Analyzer Full
  hosts: localhost
  gather_facts: false
  vars_files:
    - "group_vars/all/{{ env }}/vars.yml"
    - "group_vars/all/{{ env }}/vault.yml"
  roles:
    - role: infra.automation_development_office.cve_analyzer
      vars:
        cve_analyzer_action: full
```

Enrichment compound (replaces four separate role invocations):

```yaml
- role: infra.automation_development_office.cve_analyzer
  vars:
    cve_analyzer_action: enrichment
```

Phase 0 nonprod posture UID example:

```yaml
cve_analyzer_action: publish_rhacs_posture
cve_analyzer_vuln_dashboard_uid: ado-rhacs-vuln-posture-phase0
cve_analyzer_phase0_feature_uids:
  - ado-rhacs-vuln-posture-new
cve_analyzer_cve_intel_panels: true
```

Bootstrap seeds (when component ``cve_analyzer`` is selected):

- Playbook: ``playbooks/cve_analyzer/ado-cve-analyzer-bootstrap.yml``
  (one thin entrypoint; each Contoller JT sets ``cve_analyzer_action`` via
  ``extra_vars``). Standalone CLI:

  ```bash
  ansible-playbook playbooks/cve_analyzer/ado-cve-analyzer-bootstrap.yml \
    -e env=<env> \
    -e cve_analyzer_action=enrichment \
    --ask-vault-pass
  ```

- Job templates: ``ADO | CVE Analyzer | <action>`` for ``full``,
  ``enrichment``, ``fetch_export``, ``publish_rhacs_posture``,
  ``publish_metrics``, ``repair_posture_metrics``, ``publish_grafana``,
  and ``cve_intel``
- Optional workflow: ``ADO | CVE Analyzer Workflow`` —
  **Fetch Export → Publish RHACS Posture → Publish Namespace Metrics**
  Posture creates the metrics scrape stack and writes gauges into the
  ConfigMap (jobs do not share ``/tmp``). Metrics refreshes idempotently.
  ``repair_posture_metrics`` is **not** in this workflow (standalone JT only).
  This is a lightweight posture refresh only. It does **not** run the
  enrichment pipeline or publish the triage Grafana dashboard. Use the
  standalone **Full** or **Enrichment** job templates for those paths.
  Enrichment JT path: Fetch → Enrichment → triage Grafana → RHACS Posture.
- Vars/vault: ``vars_cve_analyzer.yml`` (URLs, titles, UIDs, Phase 0 flags)
  / ``vault_cve_analyzer.yml`` (``acs_api_token``, Grafana admin password).
  Org, project, inventory, EE, and Vault credential names come from
  ``bootstrap_controller_*`` (shared primitives); JT seeds do not hard-code
  lab org names.
- Posture identity (stable — never randomize):
  title ``RHACS Vulnerability Posture (ADO)``,
  UID ``ado-rhacs-vuln-posture``. Phase 0 board UID
  ``ado-rhacs-vuln-posture-phase0``. Empty
  ``cve_analyzer_phase0_feature_uids`` keeps experimental panels off
  production.

Preflight UI form fields are a follow-up. Keep ``acs_report`` separate.

## 🧪 Role Molecule Testing

No Molecule scenario ships yet. Python regression tests live under
``roles/cve_analyzer/files/tests/`` (Phase 0 UIDs, CVE Intel panels, filters):

```bash
python3 -m pytest roles/cve_analyzer/files/tests/ -q
```

Top KPI cards (Total / severity / Fixable) must not sum hierarchical
``namespace_rollups`` under Phase 1 Cluster/Namespace All filters — that
inflated totals ~4× versus the older board on the same CSV. Additive KPIs use
per-namespace age slices plus all-ages per real cluster+namespace only.
**Unique CVEs** is ``COUNT(DISTINCT CVE ID)`` after filters — never a sum of
per-ownership, per-source, or per-age-bucket uniques. The card uses equal-key
rollups (``ClusterKey`` × ``SreKey`` × Age × Source). Supported multi-selects
emit exact **set unions** (both clusters, ownership pairs, RH+NRS, and
combined Finding-age keys such as Over 14 / Over 30). RH+NRS copies the
All-sources age matrix so Source=RH+NRS × any Age (including multi-age) stays
correct. Unsupported combinations show Grafana ``n/a`` (``noValue``), never a
misleading zero or inflated sum. Grafana **SRE managed** ``allValue`` is
``__ALL__`` (coordinated with ``OwnershipAll`` on additive KPIs and ownership
tables).

**Severity totals vs Total Findings:** Critical + Important + Moderate + Low
KPI cards cover those four ACS severities only. **Total Findings** also
includes rows whose severity is Unknown/other, so
``C+I+M+L`` can be less than Total on the same scrubbed CSV. That gap is
expected — do not “fix” additive KPIs by forcing Unknown into a severity card.

**Detail panel size:** Detail (panel id 90) caps at **16,000** rows so the
published Grafana JSON stays under the **16 MiB** API limit (target
**< 14.5 MiB**). Local builder fingerprint format:
``builder-2.1.2-<sha8>`` of ``build_rhacs_vuln_dashboard.py`` (collection
version stays **2.1.2**; do not bump for these fixes).

Findings over time (production ``ado-rhacs-vuln-posture`` and Phase 0 UIDs):

- **Panel 11** — historical PromQL / filter behavior **unchanged** in this
  workstream. Filterable by cluster / namespace
  (``cve_posture_findings_by_cluster`` / ``_by_ns``). All severities are
  always plotted. Source, Finding age, Component, and SRE managed are **not**
  in the Prometheus series labels — do not treat those toolbar filters as
  functional on Panel 11 until metrics grow those dimensions.
- **Panel 12** — legacy all-cluster reference (``cve_posture_findings``,
  filter-independent).
- **Panel 16** (SRE-managed OpenShift images bar) — retains ``Category`` /
  ``xField`` after groupBy so the bar chart renders; honors Ownership and
  Cluster/Source filters per the filter contract.

CSV toolbar filter contract (Phase 0):

- **Source** is a multiselect (Red Hat / Non-Red Hat). Grafana **All** maps to
  the All-sources slice via ``allValue`` (no redundant ``All sources`` chip).
- **Finding age** — Unique CVEs use equal Age keys + exact multi-age set
  unions (do not sum disjoint age buckets). Additive KPIs keep per-bucket
  age slices.
- **Simple view** honors Cluster, Source, Namespace, and Finding age.
- **Findings by namespace** honors Cluster, Source, Namespace, Finding age,
  Component, and SRE managed (component×ownership slices roll up after
  filters). Severity stays as Critical/High/Moderate/Low **columns**.
- **SRE managed** filters top KPI cards, Remediation Paths, Findings by
  namespace / components / ownership tables, and the OCP images bar (ownership
  = Red Hat SRE Managed Services). Grafana All maps to ``__ALL__`` (Unique
  distinct rollup + ``OwnershipAll`` on additive/table rows). Leave **All**
  selected when unrestricted (same as Namespace).
- **SRE-managed OpenShift** CVE-by-age tables honor Cluster and Source; they
  show the full ``AGE_BUCKETS`` **distribution** (Finding age toolbar N/A —
  different bucket scheme). The images bar also honors SRE managed.
- Component / image / ownership / over-30 tables honor Source plus Cluster /
  Namespace / Finding age / Component / SRE where those columns exist.
- **Severity toolbar removed** — Panel 11 always plots all severities.
  Severity-specific KPI cards remain. Detail drills may still pin a hidden
  severity var. See ``files/tests/test_filter_contract.py``.

Legacy PromQL aggregates per-pod then median across pods
(``quantile by (severity) (0.5, sum by (severity, pod) (…))``) so
``last_over_time[1d]`` does not multiply stale or double-published scrape
series after metrics rollouts.

Cluster/Namespace Grafana ``allValue`` is ``name1|name2|…|__ALL__`` so
additive KPI stats (Total/Critical/…) match the scrubbed CSV when All is
selected. Bare ``allValue=__ALL__`` only matches Unique-CVE rollup rows and
zeros the other KPIs.

Dashboard Build / Grafana publish reliability:

- Builder failures are captured and **fail** the Contoller job (no silent
  static-sample fallback).
- Grafana is not overwritten unless ``cve_analyzer_posture_live_ok`` is true.
- Before overwrite, ADO GETs the existing dashboard and writes a full JSON
  backup under ``cve_analyzer_grafana_dashboard_backup_dir/<uid>/`` (plus a
  small ``.meta.json`` sidecar). Missing UID (404) is treated as new. Backup
  failure refuses publish. Credentials are never written into backup files.
- After a successful publish, ADO GETs the dashboard by UID and asserts UID
  and title match the configured values.
- Lite/compare still refuses production UID ``ado-rhacs-vuln-posture``.

Example durable backup layout (Contoller EE must mount this path):

```text
/var/lib/cve-analyzer/grafana-backups/
  ado-rhacs-vuln-posture-phase0/
    ado-rhacs-vuln-posture-phase0-v41-20261101T131500Z.json
    ado-rhacs-vuln-posture-phase0-v41-20261101T131500Z.meta.json
```

### Same-job scrubbed CSV retention (Gate 2 validation)

Enable only when a durable mount is available. Default remains **off** so
existing Contoller schedules are unchanged.

```yaml
cve_analyzer_scrubbed_csv_retention_enabled: true
cve_analyzer_scrubbed_csv_retention_dir: /var/lib/cve-analyzer/scrubbed-csv
cve_analyzer_scrubbed_csv_retention_days: 30
```

After Dashboard Build succeeds, the role copies the **exact** scrubbed CSV
that fed the builder into:

```text
/var/lib/cve-analyzer/scrubbed-csv/
  job<JOB_ID>-<UTC>/
    RHACS_*_SCRUBBED_*.csv
    validation-meta.json   # job id, export stamp, sha256, row count,
                           # builder fingerprint, dashboard UID, 2.1.2
```

Meta is paths + hashes only (no finding rows in Contoller logs). Retention
failures are **visible** (job fails). Do **not** store retained CSVs in Git,
public CI artifacts, or unrestricted logs. Gate 2: compare every Grafana panel
to this same-job CSV — never substitute a different ACS snapshot.

Validate end-to-end with Contoller/CLI against a nonprod Grafana UID before
touching production ``ado-rhacs-vuln-posture``.

### Hub / Contoller delivery (collection 2.1.2)

Keep ``galaxy.yml`` version **2.1.2**. Same-version Hub republish is expected
for these Unique/age/retention fixes — Contoller EE/project must pull the
tarball that embeds the intended builder fingerprint.

1. Build: ``ansible-galaxy collection build`` →
   ``infra-automation_development_office-2.1.2.tar.gz``.
2. Publish/upload to Hub (force same version if needed); sync Contoller
   project / EE so the installed collection matches the commit under review.
3. Contoller job stdout must show
   ``RHACS dashboard builder fingerprint: builder-2.1.2-<sha8>``.
   Local expected fingerprint for this branch (recalculate after builder
   edits): see pre-merge readiness report / ``python3 -c`` on
   ``builder_fingerprint_tag()``.
4. Production UID ``ado-rhacs-vuln-posture`` and Contoller schedules stay
   **unchanged** by this workstream. Phase 0 uses a nonprod UID + survey
   ``cve_analyzer_phase0_publish_only=true``.
5. For Gate 2 CSV-to-dashboard verification, enable scrubbed CSV retention on
   that Phase 0 job only (extra vars / ``vars_cve_analyzer``), then compare
   Grafana to the retained CSV + ``validation-meta.json``.

### Phase 0 rename + filter validation (collection 2.1.2+)

Do **not** launch until the Contoller JT survey includes UID/title/
``cve_analyzer_phase0_publish_only`` (seeded in
``ado-cve-analyzer-publish-rhacs-posture-bootstrap.jt.yml``). Launch the
standalone **Publish RHACS Posture** JT (not the multi-node workflow) so the
survey is answered explicitly.

1. Deliver collection **2.1.2** to Hub/Contoller (see Hub / Contoller delivery
   above); confirm project/EE shows 2.1.2 and the expected builder fingerprint.
2. Sync Contoller project + apply JT surveys.
3. Pre-flight: job stdout must show
   ``uid=ado-rhacs-vuln-posture-phase0`` and
   ``phase0_publish_only=True``. If UID is production, **stop**.
4. Rename publish: title
   ``RHACS Vulnerability Posture - Phase 0 Filter Test``, UID phase0 only.
5. Grafana: title updated, UID unchanged, no duplicate dashboard, panels
   11/12/16/90 present, variables + PromQL + CSV intact; JSON under 16 MiB.
6. Browser filter matrix (Source multiselect, Cluster/Ns/Age/Component/SRE),
   including Unique Over-14 / Over-30 set unions and RH+NRS × age.
7. With retention enabled: copy retained CSV off-box; independently recompute
   Unique/severity/age KPIs and compare to Grafana (Gate 2).
8. Restore title to ``RHACS Vulnerability Posture (ADO) - Phase 0``.
9. Only after Gate 1 + Gate 2 sign-off: consider production UID (set Refuse
   production=false).

## 📁 Role Structure

```text
roles/cve_analyzer/
  README.md
  meta/main.yml
  defaults/main.yml
  tasks/
    main.yml                 # action dispatcher + timing
    preflight.yml            # env / action / URL checks
    banner.yml / recap.yml
    resolve_ocp_auth.yml
    ensure_acs_token.yml
    fetch_export.yml
    run_pipeline.yml
    publish_grafana.yml
    publish_rhacs_posture.yml
    retain_scrubbed_csv.yml  # optional same-job CSV validation snapshot
    backup_grafana_dashboard.yml
    publish_ns_metrics.yml
    repair_posture_metrics.yml
    discover_ns_metrics_resources.yml
    verify_ns_metrics_pipeline.yml
    ensure_posture_metrics_gauges.yml
    ensure_ns_metrics_workload.yml
    resolve_prometheus_datasource_uid.yml
    cve_intel.yml
    phase_*.yml / execution_summary.yml
  files/
    scripts/                 # enrichment pipeline
    cve_intel/               # intel collectors + panel builder
    build_rhacs_vuln_dashboard.py
    tests/
```
