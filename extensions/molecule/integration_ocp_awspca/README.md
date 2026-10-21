# Molecule scenario: integration_ocp_awspca

This scenario validates wiring for the `infra.automation_development_office.ocp_awspca` role in the
normalized extension-level Molecule layout.

## Scenario flow

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

Scenario `molecule.yml` points to shared playbooks in
`extensions/molecule/utils/playbooks`:

- `prepare`: `ocp_awspca_prepare.yml`
- `converge`: `ocp_awspca_converge.yml`
- `verify`: `ocp_awspca_verify.yml`
- `destroy`: `ocp_awspca_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_awspca
```

## Live-check mode

Converge is safe by default and skips live OpenShift calls unless explicitly
enabled. To run the role against a real cluster:

```bash
export OCP_AWSPCA_ENABLE_LIVE_CHECKS=true
export OCP_AWSPCA_PCA_ARN="arn:aws-us-gov:acm-pca:region:account:certificate-authority/example"
export OCP_AWSPCA_ACCESS_KEY_ID="***"
export OCP_AWSPCA_SECRET_ACCESS_KEY="***"
molecule test -s integration_ocp_awspca
```
