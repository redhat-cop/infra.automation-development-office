"""Guard ec2_ami_copy inline AWS docs against amazon.aws argument_spec drift.

Runtime still uses AnsibleAWSModule / aws_argument_spec from amazon.aws >= 8.
DOCUMENTATION was inlined so Hub ansible-doc does not need amazon.aws fragments.
This test freezes the option keys, aliases, and defaults we document so they
stay aligned with amazon.aws 8.x ``aws_argument_spec()``.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
MODULE = ROOT / "plugins" / "modules" / "ec2_ami_copy.py"

# Mirror of amazon.aws >= 8.0 ``aws_argument_spec()`` / common MODULES fragment.
# Update deliberately when bumping the amazon.aws dependency.
EXPECTED_AWS_OPTIONS = {
    "access_key": {
        "aliases": ["aws_access_key_id", "aws_access_key"],
    },
    "secret_key": {
        "aliases": ["aws_secret_access_key", "aws_secret_key"],
    },
    "session_token": {
        "aliases": ["aws_session_token"],
    },
    "profile": {
        "aliases": ["aws_profile"],
    },
    "region": {
        "aliases": ["aws_region"],
    },
    "endpoint_url": {
        "aliases": ["aws_endpoint_url"],
    },
    "aws_ca_bundle": {
        "type": "path",
    },
    "validate_certs": {
        "type": "bool",
        "default": True,
    },
    "aws_config": {
        "type": "dict",
    },
    "debug_botocore_endpoint_logs": {
        "type": "bool",
        "default": False,
    },
}

EXPECTED_ENV_MENTIONS = {
    "access_key": ("AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY"),
    "secret_key": ("AWS_SECRET_ACCESS_KEY", "AWS_SECRET_KEY"),
    "session_token": ("AWS_SESSION_TOKEN",),
    "profile": ("AWS_PROFILE", "AWS_DEFAULT_PROFILE"),
    "region": ("AWS_REGION", "AWS_DEFAULT_REGION"),
    "endpoint_url": ("AWS_URL",),
    "aws_ca_bundle": ("AWS_CA_BUNDLE",),
    "debug_botocore_endpoint_logs": ("ANSIBLE_DEBUG_BOTOCORE_LOGS",),
}


def _load_documentation() -> dict:
    source = MODULE.read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DOCUMENTATION":
                    raw = ast.literal_eval(node.value)
                    doc = yaml.safe_load(raw)
                    assert isinstance(doc, dict)
                    return doc
    raise AssertionError("DOCUMENTATION assignment not found")


@pytest.fixture(scope="module")
def documentation() -> dict:
    return _load_documentation()


def test_ec2_ami_copy_docs_are_self_contained(documentation: dict) -> None:
    assert "extends_documentation_fragment" not in documentation
    text = MODULE.read_text(encoding="utf-8")
    assert "amazon.aws.common.modules" not in text
    assert "amazon.aws.region.modules" not in text
    assert "amazon.aws.boto3" not in text


def test_ec2_ami_copy_aws_options_match_amazon_aws_argspec(documentation: dict) -> None:
    options = documentation.get("options") or {}
    for name, expected in EXPECTED_AWS_OPTIONS.items():
        assert name in options, f"missing documented AWS option {name}"
        opt = options[name]
        if "aliases" in expected:
            assert sorted(opt.get("aliases") or []) == sorted(expected["aliases"])
        if "type" in expected:
            assert opt.get("type") == expected["type"]
        if "default" in expected:
            assert opt.get("default") == expected["default"]


def _desc_blob(option: dict) -> str:
    desc = option.get("description")
    if isinstance(desc, list):
        return " ".join(str(part) for part in desc)
    return str(desc or "")


def test_ec2_ami_copy_docs_mention_env_fallbacks(documentation: dict) -> None:
    options = documentation.get("options") or {}
    for name, envs in EXPECTED_ENV_MENTIONS.items():
        blob = _desc_blob(options[name])
        for env_name in envs:
            assert env_name in blob, f"{name} docs missing {env_name}"


def test_ec2_ami_copy_docs_state_profile_mutual_exclusion(documentation: dict) -> None:
    options = documentation.get("options") or {}
    for name in ("access_key", "secret_key", "session_token", "profile"):
        blob = _desc_blob(options[name]).lower()
        assert "mutually exclusive" in blob
