# Test Notes: kafka_install

This scenario validates the `infra.automation_development_office.kafka_install` role.

## Sequence

Default CI sequence:

```text
verify
```

Destroy sequence:

```text
destroy
```

## Playbook mapping

- `converge` -> `../utils/playbooks/kafka_install_converge.yml`
- `verify` -> `../utils/playbooks/kafka_install_verify.yml`
- `destroy` -> `../utils/playbooks/noop.yml` (CI default)

For manual cluster cleanup, use `../utils/playbooks/kafka_install_destroy.yml`.

## Run

From `extensions/molecule/`:

```bash
ln -sfn . molecule
molecule test -s kafka_install
```

## Full integration (optional)

Requires a reachable OpenShift cluster and Confluent for Kubernetes Operator CRDs:

```bash
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="..."
export K8S_AUTH_VERIFY_SSL="no"
molecule converge -s kafka_install
molecule idempotence -s kafka_install
molecule verify -s kafka_install
molecule destroy -s kafka_install
```

## Verify checks

The verify playbook asserts that `roles/kafka_install/README.md` includes:

- Role heading (`# Role:`)
- Variables table
- Example code block
- Role Requirements, Role Variables, Role Usage, Role Molecule Testing, and Role Structure sections
- Auth via environment subsection
