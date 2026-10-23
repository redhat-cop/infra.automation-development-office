# TEST: integration_rhel_ext_system_roles

## Purpose

Validate the extension-level Molecule scenario for `infra.automation_development_office.rhel_ext_system_roles`.

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- `prepare` and `destroy` are intentionally minimal no-op-safe steps.
- `converge` applies selected system roles through the wrapper role.
- `verify` checks role documentation presence.

## Run

```bash
cd extensions/molecule
molecule test -s integration_rhel_ext_system_roles
```
