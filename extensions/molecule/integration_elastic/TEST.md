# TEST: integration_elastic

## Purpose

Validate the extension-level Molecule scenario wiring for
`infra.automation_development_office.elastic`.

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- `prepare` and `destroy` are no-op safe steps.
- `verify` checks role README presence.
- `converge` supports optional live endpoint checks through
  `ELASTIC_ENABLE_LIVE_CHECKS=true`.

## Run

```bash
cd extensions/molecule
molecule test -s integration_elastic
```
