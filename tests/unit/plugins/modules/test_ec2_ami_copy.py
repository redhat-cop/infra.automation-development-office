"""Unit tests for infra.automation_development_office.ec2_ami_copy helpers."""

from __future__ import absolute_import, division, print_function


__metaclass__ = type

import importlib.util
import sys

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


pytest.importorskip("botocore")
pytest.importorskip("boto3")
pytest.importorskip(
    "ansible_collections.amazon.aws.plugins.module_utils.modules",
)

_MODULE_PATH = Path(__file__).resolve().parents[4] / "plugins" / "modules" / "ec2_ami_copy.py"
_SPEC = importlib.util.spec_from_file_location(
    "ec2_ami_copy",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
ami_copy = importlib.util.module_from_spec(_SPEC)
sys.modules["ec2_ami_copy"] = ami_copy
_SPEC.loader.exec_module(ami_copy)


def test_resolve_destination_image_name_uses_explicit_name() -> None:
    """An explicit name renames the destination AMI."""
    module = MagicMock()
    ec2 = MagicMock()

    resolved = ami_copy.resolve_destination_image_name(
        module,
        ec2,
        {
            "name": "renamed-ami",
            "source_image_id": "ami-src",
            "source_region": "us-east-1",
        },
    )

    assert resolved == "renamed-ami"
    ec2.describe_images.assert_not_called()


def test_resolve_destination_image_name_reuses_source_name() -> None:
    """Omitted name reuses the source AMI Name attribute."""
    module = MagicMock()
    ec2 = MagicMock()
    ec2.describe_images.return_value = {
        "Images": [{"Name": "golden-image"}],
    }

    resolved = ami_copy.resolve_destination_image_name(
        module,
        ec2,
        {
            "source_image_id": "ami-src",
            "source_region": "us-east-1",
        },
    )

    assert resolved == "golden-image"
    ec2.describe_images.assert_called_once_with(ImageIds=["ami-src"])


def test_build_copy_params_minimal() -> None:
    """Copy params include required CopyImage fields."""
    params = {
        "source_region": "us-east-1",
        "source_image_id": "ami-abc",
        "name": "copied",
        "description": "",
        "encrypted": False,
        "copy_image_tags": False,
        "tags": None,
    }
    result = ami_copy.build_copy_params(params, "copied")
    assert result == {
        "SourceRegion": "us-east-1",
        "SourceImageId": "ami-abc",
        "Name": "copied",
        "Description": "",
        "Encrypted": False,
        "CopyImageTags": False,
    }


def test_build_copy_params_with_encryption_and_tags() -> None:
    """Encryption and tags map to boto3 CopyImage kwargs."""
    params = {
        "source_region": "us-east-1",
        "source_image_id": "ami-abc",
        "name": "copied",
        "description": "patched",
        "encrypted": True,
        "kms_key_id": "alias/aws/ebs",
        "copy_image_tags": True,
        "tags": {"Name": "copied", "Env": "prod"},
    }
    result = ami_copy.build_copy_params(params, "copied")
    assert result["Encrypted"] is True
    assert result["KmsKeyId"] == "alias/aws/ebs"
    assert result["CopyImageTags"] is True
    assert result["TagSpecifications"][0]["ResourceType"] == "image"
    tags = result["TagSpecifications"][0]["Tags"]
    tag_pairs = {tag["Key"]: tag["Value"] for tag in tags}
    assert tag_pairs == {"Name": "copied", "Env": "prod"}


def test_find_existing_image_returns_first_match() -> None:
    """Existing AMI lookup returns the first filtered image."""
    ec2 = MagicMock()
    ec2.describe_images.return_value = {
        "Images": [
            {"ImageId": "ami-existing"},
            {"ImageId": "ami-other"},
        ],
    }
    found = ami_copy.find_existing_image(ec2, {"Name": "copied"})
    assert found == {"ImageId": "ami-existing"}
    filters = ec2.describe_images.call_args.kwargs["Filters"]
    assert {"Name": "tag:Name", "Values": ["copied"]} in filters
    assert {
        "Name": "state",
        "Values": ["available", "pending"],
    } in filters


def test_find_existing_image_returns_none_when_empty() -> None:
    """Existing AMI lookup returns None when no images match."""
    ec2 = MagicMock()
    ec2.describe_images.return_value = {"Images": []}
    assert ami_copy.find_existing_image(ec2, {"Name": "missing"}) is None


def test_wait_for_image_configures_waiter() -> None:
    """Waiter uses delay/max_attempts derived from wait_timeout."""
    waiter = MagicMock()
    ec2 = MagicMock()
    ec2.get_waiter.return_value = waiter

    ami_copy.wait_for_image(ec2, "ami-123", wait_timeout=60)

    ec2.get_waiter.assert_called_once_with("image_available")
    waiter.wait.assert_called_once_with(
        ImageIds=["ami-123"],
        WaiterConfig={"Delay": 15, "MaxAttempts": 4},
    )


def test_copy_image_skips_when_tag_equality_matches() -> None:
    """tag_equality returns existing AMI without calling copy_image."""
    module = MagicMock()
    module.check_mode = False
    module.params = {
        "tag_equality": True,
        "tags": {"Name": "copied"},
        "wait": False,
    }
    ec2 = MagicMock()
    ec2.describe_images.return_value = {
        "Images": [{"ImageId": "ami-existing"}],
    }

    def _exit_json(**kwargs: Any) -> None:
        raise SystemExit(kwargs)

    module.exit_json.side_effect = _exit_json

    with pytest.raises(SystemExit) as exc:
        ami_copy.copy_image(module, ec2)

    result = exc.value.args[0]
    assert result["changed"] is False
    assert result["image_id"] == "ami-existing"
    ec2.copy_image.assert_not_called()


def test_copy_image_creates_when_missing() -> None:
    """A new copy is started when no matching AMI exists."""
    module = MagicMock()
    module.check_mode = False
    module.params = {
        "source_region": "us-east-1",
        "source_image_id": "ami-src",
        "name": "copied",
        "description": "",
        "encrypted": False,
        "copy_image_tags": False,
        "tag_equality": False,
        "tags": {"Name": "copied"},
        "wait": False,
    }
    ec2 = MagicMock()
    ec2.copy_image.return_value = {"ImageId": "ami-new"}

    def _exit_json(**kwargs: Any) -> None:
        raise SystemExit(kwargs)

    module.exit_json.side_effect = _exit_json

    with pytest.raises(SystemExit) as exc:
        ami_copy.copy_image(module, ec2)

    result = exc.value.args[0]
    assert result["changed"] is True
    assert result["image_id"] == "ami-new"
    ec2.copy_image.assert_called_once()


def test_copy_image_check_mode_reports_change() -> None:
    """Check mode reports a pending copy without calling AWS APIs."""
    module = MagicMock()
    module.check_mode = True
    module.params = {
        "tag_equality": False,
        "tags": None,
        "wait": False,
    }
    ec2 = MagicMock()

    def _exit_json(**kwargs: Any) -> None:
        raise SystemExit(kwargs)

    module.exit_json.side_effect = _exit_json

    with pytest.raises(SystemExit) as exc:
        ami_copy.copy_image(module, ec2)

    result = exc.value.args[0]
    assert result["changed"] is True
    assert result["image_id"].startswith("ami-")
    ec2.copy_image.assert_not_called()


def test_copy_image_requires_tags_for_tag_equality() -> None:
    """tag_equality without tags fails clearly."""
    module = MagicMock()
    module.check_mode = False
    module.params = {"tag_equality": True, "tags": None}
    ec2 = MagicMock()

    def _fail_json(**kwargs: Any) -> None:
        raise SystemExit(kwargs)

    module.fail_json.side_effect = _fail_json

    with pytest.raises(SystemExit) as exc:
        ami_copy.copy_image(module, ec2)

    assert "tag_equality=true requires tags" in exc.value.args[0]["msg"]
