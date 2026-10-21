# Molecule scenario: integration_rhel_ext_system_roles

This integration scenario validates `infra.automation_development_office.rhel_ext_system_roles`
using the extension-level Molecule layout under `extensions/molecule`.

## Scenario flow

The configured sequence is:

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

The scenario `molecule.yml` points to shared playbooks in
`extensions/molecule/utils/playbooks`:

- `prepare`: `rhel_ext_system_roles_prepare.yml`
- `converge`: `rhel_ext_system_roles_converge.yml`
- `verify`: `rhel_ext_system_roles_verify.yml`
- `destroy`: `rhel_ext_system_roles_destroy.yml`

### Step intent

- `prepare`: no-op-safe setup hook (currently minimal).
- `converge`: includes `infra.automation_development_office.rhel_ext_system_roles` with `timesync`, `selinux`, and `cockpit`.
- `idempotence`: reruns converge and expects no unexpected changes.
- `verify`: asserts role README existence at `roles/rhel_ext_system_roles/README.md`.
- `destroy`: no-op-safe teardown hook (currently minimal).

## Run

Run from `extensions/molecule`:

```bash
molecule test -s integration_rhel_ext_system_roles
```

You can also run individual stages:

```bash
molecule converge -s integration_rhel_ext_system_roles
molecule verify -s integration_rhel_ext_system_roles
molecule destroy -s integration_rhel_ext_system_roles
```
