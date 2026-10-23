# Molecule scenario: integration_ocp_compliance_scan

This scenario validates wiring for the `infra.automation_development_office.ocp_compliance_scan` role in
the normalized extension-level Molecule layout.

## Scenario flow

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

Scenario `molecule.yml` points to shared playbooks in
`extensions/molecule/utils/playbooks`:

- `prepare`: `ocp_compliance_scan_prepare.yml`
- `converge`: `ocp_compliance_scan_converge.yml`
- `verify`: `ocp_compliance_scan_verify.yml`
- `destroy`: `ocp_compliance_scan_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_compliance_scan
```

## Live-check mode

Converge is safe by default and skips live OpenShift calls unless explicitly
enabled. To run against a real cluster:

```bash
export OCP_COMPLIANCE_SCAN_ENABLE_LIVE_CHECKS=true
export OCP_COMPLIANCE_SCAN_PROFILE="ocp4-cis"
export OCP_COMPLIANCE_SCAN_SCAN_NAME="daily-node-scan"
export OCP_COMPLIANCE_SCAN_SUITE_NAME="daily-suite"
molecule test -s integration_ocp_compliance_scan
```
