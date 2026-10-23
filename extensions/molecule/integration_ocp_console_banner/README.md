# Molecule scenario: integration_ocp_console_banner

This scenario validates wiring for the `infra.automation_development_office.ocp_console_banner` role in
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

- `prepare`: `ocp_console_banner_prepare.yml`
- `converge`: `ocp_console_banner_converge.yml`
- `verify`: `ocp_console_banner_verify.yml`
- `destroy`: `ocp_console_banner_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_console_banner
```

## Live-check mode

Converge is safe by default and skips live OpenShift calls unless explicitly
enabled. To run against a real cluster:

```bash
export OCP_CONSOLE_BANNER_ENABLE_LIVE_CHECKS=true
export OCP_CONSOLE_BANNER_TEXT="Hello from Molecule"
molecule test -s integration_ocp_console_banner
```
