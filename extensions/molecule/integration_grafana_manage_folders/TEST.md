# TEST: integration_grafana_manage_folders

## Purpose

Validate extension-level Molecule scenario wiring for
`infra.automation_development_office.grafana_manage_folders`.

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- `prepare` and `destroy` are no-op safe steps.
- `verify` confirms role README presence.
- `converge` supports optional live execution when
  `GRAFANA_MANAGE_FOLDERS_ENABLE_LIVE_CHECKS=true`.
- For live execution, pass supported auth variables like
  `grafana_manage_folders_api_key` or `grafana_api_key`.

## Run

```bash
cd extensions/molecule
molecule test -s integration_grafana_manage_folders
```
