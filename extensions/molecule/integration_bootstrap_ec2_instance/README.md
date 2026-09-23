# Molecule scenario: integration_bootstrap_ec2_instance

Generate-and-verify bootstrap for GovCloud EC2 instance management. Does **not**
call AWS. Modeled on `integration_bootstrap_ec2_ami_copy`.

The fixture selects the AWS platform umbrella with app `ec2_instance` (primary
path). Legacy Pre-Flight `provision` / `aws_instance` JSON remains supported via
bootstrap aliasing but is not the scenario under test.

```bash
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
cd extensions/molecule
ln -sfn . molecule
molecule test -s integration_bootstrap_ec2_instance
```
