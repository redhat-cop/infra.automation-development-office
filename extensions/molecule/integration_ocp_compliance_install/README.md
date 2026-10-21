# Molecule scenario: integration_ocp_compliance_install

This scenario validates wiring for the `infra.automation_development_office.ocp_compliance_install` role
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

- `prepare`: `ocp_compliance_install_prepare.yml`
- `converge`: `ocp_compliance_install_converge.yml`
- `verify`: `ocp_compliance_install_verify.yml`
- `destroy`: `ocp_compliance_install_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_compliance_install
```

## Live-check mode

Converge is safe by default and skips live OpenShift calls unless explicitly
enabled. To run against a real cluster:

```bash
export OCP_COMPLIANCE_INSTALL_ENABLE_LIVE_CHECKS=true
export OCP_COMPLIANCE_INSTALL_OPERATOR_NAMESPACE="openshift-compliance"
molecule test -s integration_ocp_compliance_install
```
