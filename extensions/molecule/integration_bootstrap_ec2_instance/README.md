# Molecule scenario: integration_bootstrap_ec2_instance

Generate-and-verify bootstrap for GovCloud EC2 instance management. Does **not**
call AWS. Modeled on `integration_bootstrap_ec2_ami_copy`.

The fixture uses Pre-Flight provision app `aws_instance`, which bootstrap aliases
to collection app `ec2_instance`.

```bash
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
cd extensions/molecule
ln -sfn . molecule
molecule test -s integration_bootstrap_ec2_instance
```
