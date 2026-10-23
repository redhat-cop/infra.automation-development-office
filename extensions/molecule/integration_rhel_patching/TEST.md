# TEST: integration_rhel_patching

## Purpose

Validate extension-level Molecule scenario wiring for `infra.automation_development_office.rhel_patching`
on UBI 8 and UBI 9.

RHEL 7 is not covered by this scenario.

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
- `prepare` installs Python 3.11 on UBI 8 for Ansible compatibility.
- UBI 8 converge uses `command`-based `dnf` CLI tasks (Python 3.11 lacks
  `python3-dnf`). UBI 9 converge runs the role with `ansible.builtin.dnf`.
- Converge runs discovery mode first, then a targeted `tar` package update.
- `verify` checks README format, OS version, dnf health, and targeted package
  installation.

## Run

```bash
cd extensions/molecule
molecule test -s integration_rhel_patching
```
