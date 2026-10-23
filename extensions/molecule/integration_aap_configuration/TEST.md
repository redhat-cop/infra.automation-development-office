# TEST: integration_aap_configuration

## Purpose

Validate extension-level Molecule scenario wiring for
`infra.automation_development_office.aap_configuration`.

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- `prepare` creates a mock `infra.aap_configuration.dispatch` collection and a
  sample config file under `utils/playbooks/configs/`.
- `converge` runs the wrapper role against localhost using the mock dispatcher
  by default.
- `verify` checks copied config files, mock dispatch invocation, and README
  format via `scripts/verify_readme.py`.
- `destroy` removes fixtures from the playbook configs directory, role configs
  directories, and the scenario `mock_collections` directory.
- Set `AAP_CONFIGURATION_ENABLE_LIVE_CHECKS=true` to skip mock-dispatch
  assertions and run against a real `infra.aap_configuration` installation.

## Run

```bash
cd /path/to/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

cd extensions/molecule
molecule test -s integration_aap_configuration
```
