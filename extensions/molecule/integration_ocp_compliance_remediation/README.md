# Molecule scenario: integration_ocp_compliance_remediation

This scenario validates wiring for the `infra.automation_development_office.ocp_compliance_remediation`
role in the normalized extension-level Molecule layout.

## Scenario flow

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

Scenario `molecule.yml` points to shared playbooks in
`extensions/molecule/utils/playbooks`:

- `prepare`: `ocp_compliance_remediation_prepare.yml`
- `converge`: `ocp_compliance_remediation_converge.yml`
- `verify`: `ocp_compliance_remediation_verify.yml`
- `destroy`: `ocp_compliance_remediation_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_compliance_remediation
```

## Live-check mode

Converge is safe by default and skips live ACS API calls unless explicitly
enabled. To run against a real ACS endpoint:

```bash
export OCP_COMPLIANCE_REMEDIATION_ENABLE_LIVE_CHECKS=true
export OCP_COMPLIANCE_REMEDIATION_ACS_API_URL="acs.example.com"
export OCP_COMPLIANCE_REMEDIATION_ACS_TOKEN="token"
export OCP_COMPLIANCE_REMEDIATION_PROFILE="ocp4-cis"
export OCP_COMPLIANCE_REMEDIATION_SCAN_ID="latest-scan"
molecule test -s integration_ocp_compliance_remediation
```
