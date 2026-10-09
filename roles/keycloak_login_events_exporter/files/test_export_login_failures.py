#!/usr/bin/env python3
"""Classify LOGIN vs LOGIN_ERROR the same way the exporter does."""
from __future__ import annotations

import unittest

from export_login_failures import build_metrics, is_success_login


class SuccessLoginTests(unittest.TestCase):
    def test_login_without_error_is_success(self):
        self.assertTrue(
            is_success_login({"type": "LOGIN", "details": {"username": "alice"}})
        )

    def test_login_error_type_is_not_success(self):
        self.assertFalse(
            is_success_login(
                {"type": "LOGIN_ERROR", "error": "invalid_user_credentials"}
            )
        )

    def test_login_with_error_field_is_not_success(self):
        self.assertFalse(
            is_success_login({"type": "LOGIN", "error": "expired_code"})
        )

    def test_metrics_keep_failure_labels_and_add_success_without_error(self):
        text = build_metrics(
            {
                "rhlab": [
                    {
                        "type": "LOGIN_ERROR",
                        "time": 1700000001000,
                        "clientId": "grafana-client",
                        "ipAddress": "10.0.0.2",
                        "error": "invalid_user_credentials",
                        "details": {"username": "bob"},
                    }
                ]
            },
            {
                "rhlab": [
                    {
                        "type": "LOGIN",
                        "time": 1700000002000,
                        "clientId": "grafana-client",
                        "ipAddress": "10.0.0.3",
                        "details": {"username": "alice"},
                    }
                ]
            },
        )
        self.assertIn(
            'keycloak_login_failure_events{realm="rhlab",username="bob",'
            'client_id="grafana-client",error="invalid_user_credentials",'
            'ip="10.0.0.2"} 1',
            text,
        )
        self.assertIn(
            'keycloak_login_success_events{realm="rhlab",username="alice",'
            'client_id="grafana-client",ip="10.0.0.3"} 1',
            text,
        )
        self.assertNotIn("keycloak_login_success_events{error=", text)
        self.assertIn("keycloak_login_success_last_timestamp{", text)
        self.assertIn("keycloak_login_failure_last_timestamp{", text)


if __name__ == "__main__":
    unittest.main()
