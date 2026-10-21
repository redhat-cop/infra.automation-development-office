# Molecule scenario: integration_ocp_compliance_profiles

This scenario validates wiring for the `infra.automation_development_office.ocp_compliance_profiles` role
in the normalized extension-level Molecule layout.

## Scenario flow

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

Scenario `molecule.yml` points to shared playbooks in
`extensions/molecule/utils/playbooks`:

- `prepare`: `ocp_compliance_profiles_prepare.yml`
- `converge`: `ocp_compliance_profiles_converge.yml`
- `verify`: `ocp_compliance_profiles_verify.yml`
- `destroy`: `ocp_compliance_profiles_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_compliance_profiles
```

## Live-check mode

Converge is safe by default and skips live OpenShift calls unless explicitly
enabled. To run against a real cluster:

```bash
export OCP_COMPLIANCE_PROFILES_ENABLE_LIVE_CHECKS=true
export OCP_COMPLIANCE_PROFILES_PROFILE_NAME="custom-hardening"
export OCP_COMPLIANCE_PROFILES_PROFILE_TITLE="Custom Hardening Profile"
export OCP_COMPLIANCE_PROFILES_PROFILE_DESCRIPTION="Site-specific compliance profile"
molecule test -s integration_ocp_compliance_profiles
```
