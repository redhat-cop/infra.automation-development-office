# Molecule: terraform bootstrap generation

Generates playbooks, `terraform/stacks` seed content, vars/vault files, and
Contoller job templates for the optional `terraform` component. Does not run
Terraform.

From the collection root:

```bash
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
cd extensions/molecule
ln -sfn . molecule
molecule test -s integration_bootstrap_terraform
```
