# TEST: integration_rhel_repos_default

## Purpose

Validate extension-level Molecule scenario wiring for `infra.automation_development_office.rhel_repos`
on UBI 8 and UBI 9 using Podman.

## Sequence

- `create`
- `prepare`
- `converge`
- `idempotence`
- `verify`
- `destroy`

## Notes

- Uses the Podman driver with UBI 8 and UBI 9 images from
  `registry.access.redhat.com`.
- `prepare` installs Python 3.11 on UBI 8 and creates per-repo fixture files
  under `/etc/yum.repos.d/`.
- Converge exercises `file-edit` on both platforms and `yum_repository` on UBI
  9 only.
- `verify` checks README format, OS version, repository file state, backup
  files, and `dnf` health.

## Run

```bash
cd extensions/molecule
molecule test -s integration_rhel_repos_default
```
