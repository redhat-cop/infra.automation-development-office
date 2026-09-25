"""Multi-user htpasswd hash job covers every requested account."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[3]
    / "roles/ocp_htpasswd_admin/files/hash_htpasswd_users.py"
)


class TestHashHtpasswdUsers(unittest.TestCase):
    def _run(self, job):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(job, handle)
            path = handle.name
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), path],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            self.fail(
                f"hash script exited {completed.returncode}: {completed.stderr}"
            )
        return json.loads(completed.stdout), completed.stderr

    def test_hashes_every_requested_user_on_add(self):
        payload, stderr = self._run(
            {
                "action": "add",
                "base": {"keepme": "$2y$existing"},
                "users": [
                    {"name": "admin", "password": "pass-admin"},
                    {"name": "chaddie", "password": "pass-chaddie"},
                ],
            }
        )
        self.assertEqual(payload["requested"], ["admin", "chaddie"])
        self.assertEqual(set(payload["users"]), {"admin", "chaddie", "keepme"})
        self.assertIn("admin:", payload["htpasswd"])
        self.assertIn("chaddie:", payload["htpasswd"])
        self.assertIn("keepme:", payload["htpasswd"])
        self.assertIn("admin", stderr)
        self.assertIn("chaddie", stderr)

    def test_replace_drops_base_users(self):
        payload, _stderr = self._run(
            {
                "action": "replace",
                "base": {"old": "$2y$old"},
                "users": [{"name": "only", "password": "secret"}],
            }
        )
        self.assertEqual(payload["users"], ["only"])
        self.assertNotIn("old:", payload["htpasswd"])


if __name__ == "__main__":
    unittest.main()
