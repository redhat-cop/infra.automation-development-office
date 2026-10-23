# Molecule scenario: integration_elastic

This scenario validates the `infra.automation_development_office.elastic` role using the
normalized extension-level Molecule layout.

## Scenario flow

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

The scenario-level `molecule.yml` maps to shared playbooks under
`extensions/molecule/utils/playbooks`:

- `prepare`: `elastic_prepare.yml`
- `converge`: `elastic_converge.yml`
- `verify`: `elastic_verify.yml`
- `destroy`: `elastic_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_elastic
```

## Live-check mode

Converge is safe by default and skips live endpoint checks unless explicitly enabled.
To run role status checks against a real Elasticsearch endpoint:

```bash
export ELASTIC_ENABLE_LIVE_CHECKS=true
export ELASTIC_URL="http://localhost:9200"
molecule test -s integration_elastic
```
