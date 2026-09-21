# infra.ado.ec2_ami_copy

Copy an Amazon Machine Image (AMI) from a source AWS region into a destination
region. Returns the new AMI ID. Designed for environments that have
`amazon.aws` available but **not** `community.aws`.

Module source: [`plugins/modules/ec2_ami_copy.py`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/plugins/modules/ec2_ami_copy.py)

## Requirements

- Ansible `>=2.17.0` (required by the `amazon.aws` dependency)
- Collection dependency: [`amazon.aws`](https://docs.ansible.com/ansible/latest/collections/amazon/aws/index.html)
  `>=8.0.0` (declared in `galaxy.yml`; provides AWS authentication helpers)
- Python packages on the controller / execution environment: `boto3`, `botocore`
- IAM permissions in both regions to describe images, copy images, create tags,
  and (when encrypting) use the target KMS key

Installing this collection from Galaxy also pulls in `amazon.aws`. For offline
or EE builds, ensure `amazon.aws` is already bundled (see
`collections/requirements.yml`).

```yaml
collections:
  - name: infra.ado
```

## Authentication and region

Use the standard `amazon.aws` credential options (`access_key`, `secret_key`,
`session_token`, `profile`, environment variables, or instance/role credentials).

- `source_region` — region that currently holds the AMI to copy
- `region` — destination region where the new AMI is created (from the
  `amazon.aws` region fragment)

## Parameters

| Parameter         | Required | Default   | Description                                                                                    |
| ----------------- | -------- | --------- | ---------------------------------------------------------------------------------------------- |
| `source_region`   | yes      |           | Source AWS region of the AMI.                                                                  |
| `source_image_id` | yes      |           | AMI ID in the source region.                                                                   |
| `region`          | yes\*    |           | Destination AWS region (\*via `amazon.aws` region options / env).                              |
| `name`            | no       | source AMI name | Name for the new AMI; omit to keep the source name, or set to rename during copy.             |
| `description`     | no       | `""`      | Description for the new AMI.                                                                   |
| `encrypted`       | no       | `false`   | Encrypt destination EBS snapshots.                                                             |
| `kms_key_id`      | no       |           | KMS key ID/ARN/alias for encryption; account default EBS CMK if omitted when `encrypted=true`. |
| `copy_image_tags` | no       | `false`   | Also copy tags from the source AMI.                                                            |
| `tags`            | no       |           | Tags to apply to the new AMI.                                                                  |
| `tag_equality`    | no       | `false`   | If `true`, skip copy when a destination AMI already has the same `tags` (requires `tags`).     |
| `wait`            | no       | `false`   | Wait until the AMI is `available`.                                                             |
| `wait_timeout`    | no       | `600`     | Seconds to wait when `wait=true`.                                                              |

Supports check mode (`ansible-playbook --check`).

## Examples

Basic copy and wait for availability:

```yaml
- name: Copy AMI to us-west-2 with a new name
  infra.ado.ec2_ami_copy:
    source_region: us-east-1
    region: us-west-2
    source_image_id: ami-0123456789abcdef0
    name: my-app-image-west
    wait: true
  register: copied_ami

- name: Copy AMI keeping the source name
  infra.ado.ec2_ami_copy:
    source_region: us-east-1
    region: us-west-2
    source_image_id: ami-0123456789abcdef0
    wait: true
  register: copied_ami_same_name

- name: Show new AMI ID
  ansible.builtin.debug:
    var: copied_ami.image_id
```

Encrypted, tagged, idempotent copy (safe to re-run):

```yaml
- name: Copy AMI with encryption and tag-based idempotency
  infra.ado.ec2_ami_copy:
    source_region: us-east-1
    region: eu-west-1
    source_image_id: ami-0123456789abcdef0
    name: my-app-image
    description: "Promoted golden image"
    encrypted: true
    kms_key_id: alias/aws/ebs
    tags:
      Name: my-app-image
      Environment: prod
    tag_equality: true
    wait: true
    wait_timeout: 1200
  register: copied_ami
```

Using an AWS named profile:

```yaml
- name: Copy AMI with a named profile
  infra.ado.ec2_ami_copy:
    profile: my-aws-profile
    source_region: us-east-1
    region: us-west-2
    source_image_id: "{{ source_ami_id }}"
    name: "{{ ami_name }}"
    wait: true
```

## Return values

| Key        | Description                                                                         |
| ---------- | ----------------------------------------------------------------------------------- |
| `image_id` | AMI ID of the copied AMI, or the existing match when `tag_equality` skips the copy. |
| `changed`  | `true` when a new copy was started; `false` when an existing AMI was reused.        |
