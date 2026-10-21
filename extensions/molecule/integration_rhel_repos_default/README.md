# Molecule scenario: integration_rhel_repos_default

This scenario validates wiring for the `infra.automation_development_office.rhel_repos` role on UBI 8
and UBI 9 in the normalized extension-level Molecule layout.

## Platforms

| Instance | Image | Coverage |
|----------|-------|----------|
| `rhel-repos-el8` | UBI 8 | `file-edit` enable/disable |
| `rhel-repos-el9` | UBI 9 | `file-edit` enable/disable and `yum_repository` enable |

UBI 8 uses Python 3.11 for Ansible connectivity, which lacks `python3-dnf`
bindings. The `yum_repository` method is tested on UBI 9 only.

## Converge phases

1. **file-edit enable** — enables `test-repo-disabled` on both platforms.
2. **file-edit disable** — disables `test-repo-enabled` with backup on both
   platforms.
3. **yum_repository enable** — enables `test-repo-yum` on UBI 9 only.

## Run locally with Podman

```bash
cd /path/to/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix containers.podman community.general \
  --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

pip install 'molecule-plugins[podman]'

cd extensions/molecule
molecule test -s integration_rhel_repos_default
```

## Related scenarios

`integration_rhel_repos_rhsm` is manual-only and excluded from PR CI. It is
intended for registered RHEL hosts with working RHSM access.
