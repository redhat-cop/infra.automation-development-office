# Molecule scenario: integration_aap_configuration

This scenario validates wiring for the `infra.automation_development_office.aap_configuration` role in
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

- `prepare`: `aap_configuration_prepare.yml`
- `converge`: `aap_configuration_converge.yml`
- `verify`: `aap_configuration_verify.yml`
- `destroy`: `aap_configuration_destroy.yml`

## Run

Install the collection from the repository root, then run the scenario from
`extensions/molecule`:

```bash
cd /path/to/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

cd extensions/molecule
molecule test -s integration_aap_configuration
```

## Default (mock dispatch) mode

By default, `prepare` installs a mock `infra.aap_configuration.dispatch` role under
`integration_aap_configuration/mock_collections`. The converge step validates that
playbook-side config files are copied into the role and that the wrapper invokes the
dispatcher with `aap_configuration_config_path`.

## Live-check mode

To run against the real `infra.aap_configuration.dispatch` role, install that
collection from Ansible Galaxy and enable live checks:

```bash
export AAP_CONFIGURATION_ENABLE_LIVE_CHECKS=true
molecule test -s integration_aap_configuration
```

Provide valid AAP configuration YAML files under
`extensions/molecule/utils/playbooks/configs/` before running live checks.
