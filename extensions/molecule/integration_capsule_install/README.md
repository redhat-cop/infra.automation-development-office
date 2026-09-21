# Molecule scenario: integration_capsule_install

This scenario validates wiring for the `infra.ado.capsule_install` role in the
normalized extension-level Molecule layout.

## Scenario flow

1. `prepare`
2. `converge`
3. `idempotence`
4. `verify`
5. `destroy` (via `destroy_sequence`)

## Playbook mapping

Scenario `molecule.yml` points to shared playbooks in
`extensions/molecule/utils/playbooks`:

- `prepare`: `capsule_install_prepare.yml`
- `converge`: `capsule_install_converge.yml`
- `verify`: `capsule_install_verify.yml`
- `destroy`: `capsule_install_destroy.yml`

## Run

Install the collection from the repository root, then run the scenario from
`extensions/molecule`:

```bash
cd /path/to/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

cd extensions/molecule
molecule test -s integration_capsule_install
```

## Default (pre_check) mode

By default, `converge` is offline-only because live Capsule installation requires
Satellite credentials. `verify` checks task file layout, `main.yml` wiring, HAProxy
template presence, and README format via `scripts/verify_readme.py`.

## Verify checks

- Renamed task files exist (`install_capsule.yml`, `post_config.yml`,
  `sync_capsule.yml`, `haproxy.yml`)
- Numbered legacy task files are absent
- `templates/haproxy.cfg.j2` exists
- `main.yml` includes the wired task files
- Role README format via `scripts/verify_readme.py`
