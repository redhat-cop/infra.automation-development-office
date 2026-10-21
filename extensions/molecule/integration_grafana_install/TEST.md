# TEST: integration_grafana_install

## Purpose

Validate extension-level Molecule scenario wiring for `infra.automation_development_office.grafana_install`.

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- `prepare` and `destroy` are no-op safe.
- `verify` checks README format via `scripts/verify_readme.py`.
- `converge` supports optional live execution when
  `GRAFANA_INSTALL_ENABLE_LIVE_CHECKS=true`.

## Run

```bash
cd extensions/molecule
molecule test -s integration_grafana_install
```
