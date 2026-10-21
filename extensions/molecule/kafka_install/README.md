# Molecule scenario: kafka_install

This scenario validates the `infra.automation_development_office.kafka_install` role using the
extension-level Molecule layout.

## Scenario flow

CI runs the `verify` stage to validate the role README and layout. Full cluster
integration (converge, idempotence, destroy) requires OpenShift credentials via
`K8S_AUTH_*` environment variables.

1. `verify` (default CI sequence)
2. `destroy` (via `destroy_sequence`, noop by default)

## Playbook mapping

The scenario-level `molecule.yml` maps to shared playbooks under
`extensions/molecule/utils/playbooks`:

- `converge`: `kafka_install_converge.yml`
- `verify`: `kafka_install_verify.yml`
- `destroy`: `noop.yml` (CI default) or `kafka_install_destroy.yml` for cleanup

## Run

From `extensions/molecule`:

```bash
ln -sfn . molecule
molecule test -s kafka_install
```

For full integration against a cluster:

```bash
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="..."
export K8S_AUTH_VERIFY_SSL="no"
molecule converge -s kafka_install
molecule idempotence -s kafka_install
molecule verify -s kafka_install
molecule destroy -s kafka_install
```
