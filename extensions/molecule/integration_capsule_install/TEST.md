# TEST: integration_capsule_install

## Purpose

Validate extension-level Molecule scenario wiring for `infra.ado.capsule_install`.

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- `converge` is offline-only; live Capsule installation is not exercised.
- `verify` checks task file layout, `main.yml` wiring, HAProxy template presence,
  and README format via `scripts/verify_readme.py`.
- Live Capsule installation against Satellite is not exercised in this scenario.

## Run

```bash
cd /path/to/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

cd extensions/molecule
molecule test -s integration_capsule_install
```
