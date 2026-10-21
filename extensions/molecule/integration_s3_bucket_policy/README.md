# integration_s3_bucket_policy

Functional fakecloud coverage for the S3 bucket policy collection playbooks,
driven through the same bootstrap promote + ``import_playbook`` path Contoller
uses after seed generation:

1. ``infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set`` (twice for idempotency)
2. ``infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set_from_file`` (sample policy)
3. ``infra.automation_development_office.aws.s3.ado_s3_bucket_policy_info``

Listed in ``extensions/molecule/fakecloud_scenarios.txt`` so CI starts fakecloud.

## Local run

```bash
scripts/ci/fakecloud-service.sh start
source scripts/ci/fakecloud-env.sh
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
ansible-galaxy collection install -r extensions/molecule/integration_s3_bucket_policy/requirements.yml \
  -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections"
cd extensions/molecule
ln -sfn . molecule
molecule test -s integration_s3_bucket_policy
scripts/ci/fakecloud-service.sh stop
```

The sample policy under ``playbooks/aws/s3/policies/allow_list_and_read.json``
is Jinja-templated (account id / reader role / bucket name) and is also seeded
into generated bootstrap repos for SCM editing.
