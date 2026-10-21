# Molecule scenario: integration_grafana_install

This scenario validates wiring for the `infra.automation_development_office.grafana_install` role in the
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

- `prepare`: `grafana_install_prepare.yml`
- `converge`: `grafana_install_converge.yml`
- `verify`: `grafana_install_verify.yml`
- `destroy`: `grafana_install_destroy.yml`

## Run

From `extensions/molecule`:

```bash
molecule test -s integration_grafana_install
```

## Live-check mode

Converge is safe by default and skips live OpenShift calls unless explicitly
enabled. The Grafana Operator and target namespace must already exist before
running live checks.

`verify` runs `scripts/verify_readme.py` against
`roles/grafana_install/README.md`.

```bash
export GRAFANA_INSTALL_ENABLE_LIVE_CHECKS=true
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="..."
export K8S_AUTH_VERIFY_SSL="no"
export GRAFANA_INSTALL_HOSTNAME="grafana.apps.example.com"
export GRAFANA_INSTALL_ADMIN_USER="admin"
export GRAFANA_INSTALL_ADMIN_PASSWORD="***"
export GRAFANA_INSTALL_STORAGE_CLASS="synology-iscsi-storage"
molecule test -s integration_grafana_install
```
