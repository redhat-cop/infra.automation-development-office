# Role: infra.automation_development_office.rhel_stig_cac

Audit, and with explicit approval remediate, DISA STIG controls on RHEL 8, 9,
and 10 hosts using `scap-security-guide` and OpenSCAP. The default run changes
nothing on the host except writing evidence files.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core 2.17.0 or later
- Target host: RHEL 8, 9, or 10 with `become: true`. The content must match
  the host's major version.
- `openscap-scanner`, `openscap-utils`, and `scap-security-guide` installed.
  Only mode `prepare` installs them, from repositories the host can reach.
  Disconnected hosts need those RPMs in their own repositories or Satellite.
- Python 3.7 or later on the managed host (the helper modules use the standard
  library only).
- Enough free space under `rhel_stig_cac_results_dir`. One scan writes about
  19 MB of XML on RHEL 9 because OpenSCAP embeds the benchmark in the results.
- No other collection is required.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `rhel_stig_cac_mode` | `audit` scans only. `prepare` installs OpenSCAP. `remediate` audits, remediates, and re-audits the listed controls. `verify` audits the listed controls and fails if any is not compliant. | No | `audit` |
| `rhel_stig_cac_remediation_approved` | Must be `true` for `remediate`. Never implied. | No | `false` |
| `rhel_stig_cac_recovery_confirmed` | Operator attests a snapshot or backup exists. Required for `remediate`. | No | `false` |
| `rhel_stig_cac_controls` | STIG IDs (`RHEL-09-255100`), vulnerability IDs (`V-257996`), rule IDs (`SV-257996r1134915_rule`), or SSG rule names. Required for `remediate` and `verify`. Optional for `audit` (empty scans the whole profile). | No | `[]` |
| `rhel_stig_cac_allow_protected` | Controls allowed to bypass the protected patterns. Every entry must resolve to a rule in the profile; unmatched allow-list entries fail the run (no silent ignore). | No | `[]` |
| `rhel_stig_cac_protected_patterns` | Regular expressions matched against SSG rule names. Remediation refuses a match unless allowed. | No | FIPS, SSH, SSSD/IdM, authentication, sudo, firewall/network (see `defaults/main.yml`) |
| `rhel_stig_cac_fail_on_findings` | Fail `audit` when a control is failed, errored, or not evaluated. Default `false`: audit completes and reports findings without failing the job. `remediate` and `verify` always fail on non-compliance. | No | `false` |
| `rhel_stig_cac_scan_timeout` | Seconds to wait for one `oscap` run. | No | `3600` |
| `rhel_stig_cac_profile_label` | Preflight/JT label. `Match host OS` (default) uses the target host major version. `RHEL 8/9/10 STIG` forces that content and requires the host major to match. | No | `""` |
| `rhel_stig_cac_os_major` | Force content major version (`8`, `9`, or `10`). Empty uses label map or host facts. | No | `""` |
| `rhel_stig_cac_xccdf_profile` | XCCDF profile ID from scap-security-guide. | No | `xccdf_org.ssgproject.content_profile_stig` |
| `rhel_stig_cac_packages` | RPM packages installed by mode `prepare`. | No | see `defaults/main.yml` |
| `rhel_stig_cac_oscap_path` | Path to the `oscap` binary. | No | `/usr/bin/oscap` |
| `rhel_stig_cac_results_dir` | Host directory for XML results, HTML reports, tailoring, and findings. | No | `/var/log/ado-stig-cac` |
| `rhel_stig_cac_fetch_dir` | Controller directory. When set, gzip results, the HTML report, and findings are fetched to `<dir>/<host>/`. | No | `""` |
| `rhel_stig_cac_publish_stats` | Publish the per-host result as the AAP job artifact `ado_stig_cac`. | No | `true` |

`rhel_stig_cac_remediate` is retired. Setting it to `true` fails the run with
a message that names the new variables (`rhel_stig_cac_mode=remediate` plus
approvals and an explicit control list). Nothing is scanned or changed. Remove
the old variable from generated `group_vars` so audit jobs can run.

## 🚀 Role Usage

Audit the whole STIG profile (the default, read-only):

```yaml
- name: Audit RHEL against the DISA STIG
  hosts: rhel_servers
  become: true
  roles:
    - role: infra.automation_development_office.rhel_stig_cac
```

Install the scanner first on a host that does not have it:

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: infra.automation_development_office.rhel_stig_cac
      vars:
        rhel_stig_cac_mode: prepare
```

Remediate two reviewed controls. Both approvals are required:

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: infra.automation_development_office.rhel_stig_cac
      vars:
        rhel_stig_cac_mode: remediate
        rhel_stig_cac_remediation_approved: true
        rhel_stig_cac_recovery_confirmed: true
        rhel_stig_cac_controls:
          - RHEL-09-432010
          - V-258083
```

### Modes

| Mode | Changes the host | What it does |
| ---- | ---------------- | ------------ |
| `audit` | No (evidence files only) | Fails if OpenSCAP is missing. Scans the profile, or only `rhel_stig_cac_controls`. Completes successfully when findings are non-compliant unless `rhel_stig_cac_fail_on_findings=true`. Job artifacts distinguish audit completed from host compliant. |
| `prepare` | Installs packages | Installs `rhel_stig_cac_packages`. Does not scan. |
| `remediate` | Yes | Gates, audit `before`, `oscap --remediate`, audit `after`. Fails if any selected control is still not compliant. |
| `verify` | No (evidence files only) | Audits `rhel_stig_cac_controls`. Fails if any is not compliant. |

### Remediation gates

`remediate` stops before any scan or change when any of these is not met:

1. `rhel_stig_cac_remediation_approved` is `true`.
2. `rhel_stig_cac_recovery_confirmed` is `true`.
3. `rhel_stig_cac_controls` is not empty and every entry exists in this host's
   STIG content and is selected by the profile.
4. No selected control matches a protected pattern, unless it is listed in
   `rhel_stig_cac_allow_protected`.

Only the listed controls are remediated. The role writes an XCCDF tailoring
file that deselects every other control, so `oscap --remediate` cannot touch
anything else.

OpenSCAP can drop a selected rule when a rule it `requires` is not selected.
The role adds those required rules to the selection, includes them in the
protected check, and reports them. A selected rule OpenSCAP still does not
evaluate is reported as `not_evaluated` and counts as non-compliant.

### Protected controls

Protected controls can lock you out of the host or break the AAP connection:
FIPS and crypto policy, `sshd`/`openssh`, SSSD/IdM/Kerberos/smart cards,
PAM and password policy, `sudo`, and `firewalld`/network. They are blocked from
remediation by default. Audit still reports them, marked `protected`.

### Recovery boundary

SCAP remediation edits system files, services, and packages. This role has no
undo. `rhel_stig_cac_recovery_confirmed` records that you took a VM snapshot or
backup first. Some controls need a reboot to take effect; the role does not
reboot.

### Results and evidence

For each phase (`audit`, `verify`, or `before`/`remediate`/`after`) the role
writes to `rhel_stig_cac_results_dir`:

- `stig-<N>-<phase>-results.xml`: the OpenSCAP results (audit evidence).
- `stig-<N>-<phase>-report.html`: the human-readable report.
- `stig-<N>-<phase>-findings.json`: one record per control with `stig_id`,
  `vuln_id`, `sv_id`, `srg_ids`, CAT severity, result, and status. Schema
  `ado.rhel_stig_cac.findings/v1`.
- `stig-<N>-tailoring.xml`: when controls were listed.

The results XML and HTML report include the host name, IP and MAC addresses,
and the account that ran the scan. Treat them as sensitive. The findings JSON
carries only the target name and the control results.

Statuses are `passed`, `failed`, `error`, `not_applicable`, `skipped`, and
`not_evaluated`. A non-zero `oscap` exit code `2` is never treated as success on
its own; the findings decide the result.

The job artifact `ado_stig_cac` holds one result per host (summary and file
paths). Set `rhel_stig_cac_fetch_dir` to copy the evidence to the controller;
in AAP that path must be on a persistent volume, because execution
environments are ephemeral.

## 🧪 Role Molecule Testing

There is no Molecule scenario. Molecule's UBI containers do not carry the
`scap-security-guide` content, so a scenario would not exercise the role.
Unit tests cover the helper modules and the bootstrap wiring:

```bash
pytest tests/unit/plugins/modules/test_rhel_stig_cac.py \
  tests/unit/bootstrap/test_stig_bootstrap_wiring.py
```

To validate on a lab RHEL host, audit first, then verify a single control:

```bash
ansible-playbook -i inventory playbooks/rhel/ado-stig-hardening-bootstrap.yml \
  -e stig_mode=audit
```

## 📁 Role Structure

```text
rhel_stig_cac/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   ├── audit.yml
│   ├── evidence.yml
│   ├── finish.yml
│   ├── main.yml
│   ├── prepare.yml
│   ├── prerequisites.yml
│   ├── remediate.yml
│   ├── resolve.yml
│   ├── scan.yml
│   └── verify.yml
└── vars/
    └── main.yml
```

The role uses the modules `rhel_stig_cac_resolve` and `rhel_stig_cac_report`
and the module utility `rhel_stig_cac`.

For the RHEL System Roles STIG instead, use `stig_engine: system_role` with
`infra.automation_development_office.rhel_ext_system_roles`. That engine always
changes the host, so the bootstrap playbook requires the same approval and
recovery confirmation first.
