#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the infra.automation_development_office collection
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Copy an AWS AMI from one region to another."""

from __future__ import absolute_import, division, print_function


__metaclass__ = type


DOCUMENTATION = r"""
---
module: ec2_ami_copy
version_added: 1.1.0
short_description: Copy an AMI between AWS regions
description:
  - Copies an Amazon Machine Image (AMI) from a source region
    to the destination region selected by O(region).
  - Returns the new AMI ID in the destination region.
  - Runtime authentication uses C(amazon.aws) helpers
    (C(AnsibleAWSModule)). Documentation is self-contained so
    Automation Hub C(ansible-doc) does not require amazon.aws
    doc fragments to be installed during import.
options:
  source_region:
    description:
      - The AWS region that currently holds the source AMI.
    required: true
    type: str
  source_image_id:
    description:
      - The AMI ID in O(source_region) to copy.
    required: true
    type: str
  name:
    description:
      - Name for the new AMI in the destination region.
      - When omitted, the source AMI name is reused so the copy keeps
        the same name unless you set this option to rename it.
    type: str
  description:
    description:
      - Optional description for the new AMI.
    type: str
    default: ""
  encrypted:
    description:
      - Whether destination EBS snapshots of the copied AMI
        should be encrypted.
    type: bool
    default: false
  kms_key_id:
    description:
      - KMS key ID or ARN used to encrypt destination snapshots.
      - When omitted and O(encrypted=true), uses the account
        default EBS CMK.
    type: str
  copy_image_tags:
    description:
      - Copy tags from the source AMI to the new AMI.
    type: bool
    default: false
  wait:
    description:
      - Wait until the copied AMI reaches state V(available)
        before returning.
    type: bool
    default: false
  wait_timeout:
    description:
      - Seconds to wait for the AMI to become available when
        O(wait=true).
    type: int
    default: 600
  tags:
    description:
      - Tags to apply to the new AMI in the destination region.
      - When O(tag_equality=true), these tags are also used to
        detect an existing matching AMI and skip a duplicate copy.
    type: dict
  tag_equality:
    description:
      - If V(true), look for an existing AMI in the destination
        region whose tags match O(tags) exactly (plus state
        V(available) or V(pending)).
      - When a match is found, return that AMI ID without
        copying again.
      - Requires O(tags) to be set.
    type: bool
    default: false
  access_key:
    description:
      - AWS access key ID.
      - See the AWS documentation for more information about access tokens
        U(https://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys).
      - The C(AWS_ACCESS_KEY_ID) or C(AWS_ACCESS_KEY) environment variables
        may also be used in decreasing order of preference.
      - Mutually exclusive with O(profile).
    type: str
    aliases: [aws_access_key_id, aws_access_key]
  secret_key:
    description:
      - AWS secret access key.
      - See the AWS documentation for more information about access tokens
        U(https://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys).
      - The C(AWS_SECRET_ACCESS_KEY) or C(AWS_SECRET_KEY) environment variables
        may also be used in decreasing order of preference.
      - Mutually exclusive with O(profile).
    type: str
    aliases: [aws_secret_access_key, aws_secret_key]
  session_token:
    description:
      - AWS STS session token for use with temporary credentials.
      - See the AWS documentation for more information about access tokens
        U(https://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys).
      - The C(AWS_SESSION_TOKEN) environment variable may also be used.
      - Mutually exclusive with O(profile).
    type: str
    aliases: [aws_session_token]
  profile:
    description:
      - A named AWS profile to use for authentication.
      - See the AWS documentation for more information about named profiles
        U(https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html).
      - The C(AWS_PROFILE) or C(AWS_DEFAULT_PROFILE) environment variables may
        also be used.
      - Mutually exclusive with O(access_key), O(secret_key), and
        O(session_token).
    type: str
    aliases: [aws_profile]
  region:
    description:
      - Destination AWS region for the copied AMI.
      - The C(AWS_REGION) or C(AWS_DEFAULT_REGION) environment variables may
        also be used.
      - See U(http://docs.aws.amazon.com/general/latest/gr/rande.html#ec2_region).
    type: str
    aliases: [aws_region]
  endpoint_url:
    description:
      - URL to connect to instead of the default AWS endpoints.
      - The C(AWS_URL) environment variable may also be used.
    type: str
    aliases: [aws_endpoint_url]
  aws_ca_bundle:
    description:
      - The location of a CA Bundle to use when validating SSL certificates.
      - The C(AWS_CA_BUNDLE) environment variable may also be used.
    type: path
  validate_certs:
    description:
      - When V(false), SSL certificates will not be validated for
        communication with the AWS APIs.
      - Setting O(validate_certs=false) is strongly discouraged; consider
        O(aws_ca_bundle) instead.
    type: bool
    default: true
  aws_config:
    description:
      - A dictionary to modify the botocore configuration.
      - Parameters can be found in the AWS documentation
        U(https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html#botocore.config.Config).
    type: dict
  debug_botocore_endpoint_logs:
    description:
      - When V(true), use a C(botocore.endpoint) logger to parse unique
        C(resource:action) API calls made during a task.
      - The C(ANSIBLE_DEBUG_BOTOCORE_LOGS) environment variable may also be used.
    type: bool
    default: false
author:
  - Automation Development Office (@Automation-Development-Office)
notes:
  - Requires the C(amazon.aws) collection at runtime for
    C(AnsibleAWSModule) and tagging helpers (C(amazon.aws) >= 8.0.0 per
    this collection's dependency).
  - Inline AWS option documentation mirrors C(amazon.aws) common/region
    module doc fragments so Hub C(ansible-doc) does not need those fragments
    installed. Runtime argument handling still comes from
    C(AnsibleAWSModule) / C(aws_argument_spec).
  - For modules, environment variables and configuration files are read from
    the Ansible host context. The AWS SDK (boto3) may also read credentials
    and region from host files such as C(~/.aws/credentials).
    See U(https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).
requirements:
  - python >= 3.6
  - boto3 >= 1.35.0
  - botocore >= 1.35.0
  - amazon.aws >= 8.0.0
"""

EXAMPLES = r"""
- name: Copy an AMI to another region with a new name
  infra.automation_development_office.ec2_ami_copy:
    source_region: us-east-1
    region: us-west-2
    source_image_id: ami-0123456789abcdef0
    name: my-app-image
    wait: true
  register: copied_ami

- name: Copy an AMI keeping the source name
  infra.automation_development_office.ec2_ami_copy:
    source_region: us-east-1
    region: us-west-2
    source_image_id: ami-0123456789abcdef0
    wait: true
  register: copied_ami_same_name

- name: Encrypted AMI copy with tags (idempotent via tag_equality)
  infra.automation_development_office.ec2_ami_copy:
    source_region: us-east-1
    region: eu-west-1
    source_image_id: ami-0123456789abcdef0
    name: my-app-image
    encrypted: true
    kms_key_id: alias/aws/ebs
    tags:
      Name: my-app-image
      Environment: prod
    tag_equality: true
    wait: true
    wait_timeout: 1200
"""

RETURN = r"""
image_id:
  description: AMI ID of the copied (or matched existing) AMI.
  returned: always
  type: str
  sample: ami-0abcdef1234567890
changed:
  description: Whether a new AMI copy was started.
  returned: always
  type: bool
"""

from typing import Any, Optional


try:
    from botocore.exceptions import BotoCoreError, ClientError, WaiterError
except ImportError:
    pass  # Caught by AnsibleAWSModule

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict
from ansible_collections.amazon.aws.plugins.module_utils import modules as aws_modules
from ansible_collections.amazon.aws.plugins.module_utils import tagging as aws_tagging


AnsibleAWSModule = aws_modules.AnsibleAWSModule
ansible_dict_to_boto3_tag_list = aws_tagging.ansible_dict_to_boto3_tag_list


def find_existing_image(ec2: Any, tags: dict) -> Optional[dict]:
    """Return first destination AMI matching all provided tags."""
    filters = [{"Name": f"tag:{key}", "Values": [value]} for key, value in tags.items()]
    filters.append(
        {"Name": "state", "Values": ["available", "pending"]},
    )
    response = ec2.describe_images(Filters=filters)
    images = response.get("Images") or []
    if not images:
        return None
    return images[0]


def resolve_destination_image_name(
    module: AnsibleAWSModule,
    ec2: Any,
    params: dict,
) -> str:
    """Return destination AMI name, optionally renamed from the source."""
    name = params.get("name")
    if name:
        return name

    try:
        response = ec2.describe_images(ImageIds=[params["source_image_id"]])
    except (BotoCoreError, ClientError) as exc:
        module.fail_json_aws(
            exc,
            msg="Could not describe source AMI to determine its name",
        )

    images = response.get("Images") or []
    if not images:
        module.fail_json(
            msg=(
                "Source AMI {0} was not found in {1}. "
                "Set name= to choose a destination AMI name."
            ).format(
                params["source_image_id"],
                params["source_region"],
            ),
        )

    image_name = images[0].get("Name")
    if not image_name:
        module.fail_json(
            msg="Source AMI has no Name attribute; set name= to choose a destination AMI name.",
        )
    return image_name


def build_copy_params(params: dict, destination_name: str) -> dict:
    """Build boto3 CopyImage kwargs from module params."""
    copy_params = {
        "SourceRegion": params["source_region"],
        "SourceImageId": params["source_image_id"],
        "Name": destination_name,
        "Description": params.get("description") or "",
        "Encrypted": params.get("encrypted", False),
        "CopyImageTags": params.get("copy_image_tags", False),
    }
    if params.get("kms_key_id"):
        copy_params["KmsKeyId"] = params["kms_key_id"]

    tags = params.get("tags") or {}
    if tags:
        copy_params["TagSpecifications"] = [
            {
                "ResourceType": "image",
                "Tags": ansible_dict_to_boto3_tag_list(tags),
            },
        ]
    return copy_params


def wait_for_image(ec2: Any, image_id: str, wait_timeout: int) -> None:
    """Wait until the AMI is available."""
    delay = 15
    max_attempts = max(1, wait_timeout // delay)
    ec2.get_waiter("image_available").wait(
        ImageIds=[image_id],
        WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts},
    )


def copy_image(module: AnsibleAWSModule, ec2: Any) -> None:
    """Copy an AMI into the destination region."""
    params = module.params
    tags = params.get("tags") or {}
    image = None
    changed = False

    if params.get("tag_equality"):
        if not tags:
            module.fail_json(
                msg="tag_equality=true requires tags to be set",
            )
        try:
            image = find_existing_image(ec2, tags)
        except (BotoCoreError, ClientError) as exc:
            module.fail_json_aws(
                exc,
                msg="Could not search for an existing AMI",
            )

    if image is None:
        if module.check_mode:
            module.exit_json(
                changed=True,
                image_id="ami-xxxxxxxxxxxxxxxxx",
                msg="AMI would be copied",
            )

        source_ec2 = module.client("ec2", region=params["source_region"])
        destination_name = resolve_destination_image_name(
            module,
            source_ec2,
            params,
        )
        copy_params = build_copy_params(params, destination_name)
        try:
            image = ec2.copy_image(**copy_params)
            changed = True
        except (BotoCoreError, ClientError) as exc:
            module.fail_json_aws(exc, msg="Could not copy AMI")
    elif module.check_mode:
        result = camel_dict_to_snake_dict(image)
        result["image_id"] = image.get("ImageId")
        module.exit_json(changed=False, **result)

    image_id = image.get("ImageId")
    if not image_id:
        module.fail_json(
            msg="AMI copy response did not include ImageId",
        )

    if params.get("wait"):
        try:
            wait_for_image(
                ec2,
                image_id,
                params.get("wait_timeout") or 600,
            )
        except WaiterError as exc:
            module.fail_json_aws(
                exc,
                msg=("An error occurred waiting for the image " "to become available"),
            )
        except (BotoCoreError, ClientError) as exc:
            module.fail_json_aws(
                exc,
                msg="Could not wait for AMI availability",
            )

    result = camel_dict_to_snake_dict(image)
    result["image_id"] = image_id
    module.exit_json(changed=changed, **result)


def main() -> None:
    """Module entry point."""
    argument_spec = dict(
        source_region=dict(type="str", required=True),
        source_image_id=dict(type="str", required=True),
        name=dict(type="str"),
        description=dict(type="str", default=""),
        encrypted=dict(type="bool", default=False),
        kms_key_id=dict(type="str"),
        copy_image_tags=dict(type="bool", default=False),
        wait=dict(type="bool", default=False),
        wait_timeout=dict(type="int", default=600),
        tags=dict(type="dict"),
        tag_equality=dict(type="bool", default=False),
    )

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    ec2 = module.client("ec2")
    copy_image(module, ec2)


if __name__ == "__main__":
    main()
