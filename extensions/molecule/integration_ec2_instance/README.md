# integration_ec2_instance

Functional fakecloud coverage for the EC2 instance collection playbooks, driven
the same way Contoller/bootstrap users invoke them after seed generation:

1. Promote facts with the seed ``promote-ec2-instance-facts.yml`` tasks
2. ``import_playbook`` collection FQCNs:
   - ``infra.automation_development_office.aws.ec2.ado_ec2_instance_create`` (twice for idempotency)
   - ``infra.automation_development_office.aws.ec2.ado_ec2_instance_info``
   - ``infra.automation_development_office.aws.ec2.ado_ec2_instance_modify``
   - ``infra.automation_development_office.aws.ec2.ado_ec2_instance_delete`` (destroy)

Listed in ``extensions/molecule/fakecloud_scenarios.txt`` so CI starts fakecloud.

## Local run

```bash
scripts/ci/fakecloud-service.sh start
source scripts/ci/fakecloud-env.sh
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
ansible-galaxy collection install -r extensions/molecule/integration_ec2_instance/requirements.yml \
  -p ~/.ansible/collections
pip install boto3 botocore
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections"
cd extensions/molecule && ln -sfn . molecule
molecule test -s integration_ec2_instance
scripts/ci/fakecloud-service.sh stop
```

## Notes

fakecloud may ignore the requested subnet on ``RunInstances``. Create uses
``ec2_instance_filters`` keyed by ``tag:Name`` so matching stays idempotent.
