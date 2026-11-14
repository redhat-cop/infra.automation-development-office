# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression: MinIO OIDC discovery URL must not stay empty from role defaults."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[3]
    / "roles/ocp_minio/files/minio_oidc_discovery_url.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("minio_oidc_discovery_url", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load()


class TestMinioOidcDiscoveryUrl(unittest.TestCase):
    def test_empty_config_url_falls_back_to_issuer(self):
        url = mod.resolve_discovery_url(
            config_url="",
            issuer="https://keycloak.apps.ocp-dev.dev.rhlab/realms/Dev",
        )
        self.assertEqual(
            url,
            "https://keycloak.apps.ocp-dev.dev.rhlab/realms/Dev"
            "/.well-known/openid-configuration",
        )

    def test_empty_config_and_issuer_build_from_hostname_realm(self):
        url = mod.resolve_discovery_url(
            config_url="",
            issuer="",
            hostname="keycloak.apps.ocp-dev.dev.rhlab",
            realm="Dev",
        )
        self.assertEqual(
            url,
            "https://keycloak.apps.ocp-dev.dev.rhlab/realms/Dev"
            "/.well-known/openid-configuration",
        )

    def test_custom_realm(self):
        url = mod.resolve_discovery_url(
            hostname="keycloak.lab.example",
            realm="lab",
        )
        self.assertIn("/realms/lab/", url)

    def test_explicit_discovery_preserved(self):
        explicit = (
            "https://sso.example.com/realms/x/.well-known/openid-configuration"
        )
        self.assertEqual(
            mod.resolve_discovery_url(config_url=explicit, issuer="https://ignored"),
            explicit,
        )

    def test_issuer_without_well_known_appended(self):
        url = mod.resolve_discovery_url(
            config_url="",
            issuer="https://sso.example.com/realms/x/",
        )
        self.assertTrue(url.endswith("/.well-known/openid-configuration"))

    def test_validate_rejects_empty(self):
        err = mod.validate_discovery_url("")
        self.assertIsNotNone(err)
        self.assertIn("empty", err.lower())

    def test_validate_rejects_schemeless(self):
        err = mod.validate_discovery_url("keycloak.example/realms/x/.well-known/openid-configuration")
        self.assertIsNotNone(err)
        self.assertIn("http", err.lower())

    def test_cli_rejects_empty_inputs(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "-"],
            input=json.dumps({"config_url": "", "issuer": ""}),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("empty", completed.stderr.lower())

    def test_cli_builds_from_hostname(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "config_url": "",
                    "issuer": "",
                    "hostname": "keycloak.apps.ocp-dev.dev.rhlab",
                    "realm": "Dev",
                },
                handle,
            )
            path = handle.name
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), path],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["discovery_url"],
            "https://keycloak.apps.ocp-dev.dev.rhlab/realms/Dev"
            "/.well-known/openid-configuration",
        )


if __name__ == "__main__":
    unittest.main()
