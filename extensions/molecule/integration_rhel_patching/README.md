# Molecule scenario: integration_rhel_patching

This scenario validates wiring for the `infra.automation_development_office.rhel_patching` role on UBI 8
and UBI 9 in the normalized extension-level Molecule layout.

RHEL 7 is not covered by automated Molecule testing.

## Platforms

| Instance | Image | Coverage |
|----------|-------|----------|
| `rhel-patching-el8` | UBI 8 | RHEL 8 happy path (dnf CLI in test playbooks only) |
| `rhel-patching-el9` | UBI 9 | RHEL 9 happy path (role via `ansible.builtin.dnf`) |

UBI 8 uses Python 3.11 for Ansible connectivity, which lacks `python3-dnf`
bindings. Converge and prepare therefore exercise EL8 with `command`-based `dnf`
CLI tasks in the Molecule playbooks. UBI 9 runs the role directly.

## Converge phases

1. **Discovery mode** — `rhel_patching_package_list: []` exercises repo and
   update discovery without applying updates.
2. **Targeted update** — updates the `tar` package on each platform.

## Run locally with Podman

```bash
cd /path/to/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix containers.podman community.general \
  --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"

pip install 'molecule-plugins[podman]'

cd extensions/molecule
molecule test -s integration_rhel_patching
```
