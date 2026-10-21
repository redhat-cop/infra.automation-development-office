# Standalone S3 bucket policy playbooks

Thin wrappers around `amazon.aws.s3_bucket` and `amazon.aws.s3_bucket_info`
for creating a bucket (if needed) and setting or reading its resource policy.

Requires `amazon.aws` (see collection `galaxy.yml`).

Collection path: `playbooks/aws/s3/`.

| Playbook | Collection FQCN | Purpose |
| --- | --- | --- |
| `ado_s3_bucket_policy_set.yml` | `infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set` | Create bucket + set inline policy |
| `ado_s3_bucket_policy_set_from_file.yml` | `infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set_from_file` | Create bucket + set policy from JSON/Jinja file |
| `ado_s3_bucket_policy_info.yml` | `infra.automation_development_office.aws.s3.ado_s3_bucket_policy_info` | Read bucket policy |

Sample policy (Jinja-templated): `policies/allow_list_and_read.json`.

## Bootstrap (Contoller)

When ``aws`` / ``s3_bucket_policy`` is selected in preflight, bootstrap seeds
promote + ``import_playbook`` wrappers and a copy of the sample policy for SCM
editing. Shared credentials stay in ``vault_aws.yml``.

Functional fakecloud coverage:
``extensions/molecule/integration_s3_bucket_policy``.

## Auth

- AWS environment variables / instance role
- `aws_profile`
- `vault_aws_access_key_id` / `vault_aws_secret_access_key` / optional session token

For fakecloud / custom endpoints set `s3_bucket_endpoint_url` or
`AWS_ENDPOINT_URL` (path-style addressing is enabled automatically).

## Example

```bash
ansible-playbook infra.automation_development_office.aws.s3.ado_s3_bucket_policy_set \
  -e s3_bucket_name=my-bucket \
  -e s3_bucket_aws_account_id=111122223333 \
  -e s3_bucket_reader_role_name=AppReader
```
