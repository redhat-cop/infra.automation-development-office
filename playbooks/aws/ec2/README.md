# Standalone EC2 instance playbooks

Thin wrappers around `amazon.aws.ec2_instance` and
`amazon.aws.ec2_instance_info`, based on the collection documentation examples.

Requires `amazon.aws` (see collection `galaxy.yml`).

Collection path: `playbooks/aws/ec2/`.

| Playbook | Collection FQCN | Purpose |
| --- | --- | --- |
| `ado_ec2_instance_create.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_create` | Create / ensure present |
| `ado_ec2_instance_delete.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_delete` | Terminate by ID or Name tag |
| `ado_ec2_instance_modify.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_modify` | Stop/start/restart, type, tags, termination protection |
| `ado_ec2_instance_info.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_info` | Describe / filter instances |

Run via collection FQCN (collection must be installed):

```bash
ansible-playbook infra.automation_development_office.aws.ec2.ado_ec2_instance_create -e @vars.yml
```

Or import from another playbook:

```yaml
- ansible.builtin.import_playbook: infra.automation_development_office.aws.ec2.ado_ec2_instance_create
```

## Bootstrap (Contoller)

When ``aws`` / ``ec2_instance`` is selected in preflight, bootstrap seeds:

| Seed playbook | Imports |
| --- | --- |
| `ado-ec2-instance-create-bootstrap.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_create` |
| `ado-ec2-instance-delete-bootstrap.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_delete` |
| `ado-ec2-instance-modify-bootstrap.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_modify` |
| `ado-ec2-instance-info-bootstrap.yml` | `infra.automation_development_office.aws.ec2.ado_ec2_instance_info` |

Seeds load ``vault_aws.yml`` + ``vars_ec2_instance.yml`` for ``env``, resolve
component defaults, then ``import_playbook`` the collection FQCN.

Functional fakecloud coverage (bootstrap promote + ``import_playbook`` path):
``extensions/molecule/integration_ec2_instance``.

## Auth

Use any one of:

- AWS environment variables / instance role
- `aws_profile: myprofile`
- `vault_aws_access_key_id`, `vault_aws_secret_access_key`, optional `vault_aws_session_token`

Set `ec2_instance_region` when not using the default/profile region.

## Example extra vars

Create:

```yaml
ec2_instance_name: public-compute-instance
ec2_instance_image_id: ami-0123456789abcdef0
ec2_instance_type: t3.small
ec2_instance_subnet_id: subnet-0123456789abcdef0
ec2_instance_key_name: prod-ssh-key
ec2_instance_security_group: default
ec2_instance_assign_public_ip: true
ec2_instance_tags:
  Environment: Testing
```

Info:

```yaml
ec2_instance_filters:
  "tag:Name": public-compute-instance
  instance-state-name: ["running"]
```

Modify (stop):

```yaml
ec2_instance_ids:
  - i-0123456789abcdef0
ec2_instance_state: stopped
```

Delete:

```yaml
ec2_instance_ids:
  - i-0123456789abcdef0
```

Docs:

- https://docs.ansible.com/ansible/latest/collections/amazon/aws/ec2_instance_module.html
- https://docs.ansible.com/ansible/latest/collections/amazon/aws/ec2_instance_info_module.html
