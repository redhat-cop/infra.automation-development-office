# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for safe MinIO OIDC Deployment patching."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[3]
    / "roles/ocp_minio/files/minio_oidc_deployment_patch.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "minio_oidc_deployment_patch",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _sample_deployment() -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "minio",
            "namespace": "minio",
            "resourceVersion": "12345",
            "uid": "abc-def",
            "labels": {"app.kubernetes.io/name": "minio"},
            "annotations": {"keep.me": "yes"},
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "minio"}},
            "template": {
                "metadata": {
                    "labels": {"app": "minio"},
                    "annotations": {"existing.anno": "keep"},
                },
                "spec": {
                    "containers": [
                        {
                            "name": "minio",
                            "image": "quay.io/minio/minio:RELEASE.2024-01-01",
                            "imagePullPolicy": "IfNotPresent",
                            "args": ["server", "/data", "--console-address", ":9090"],
                            "ports": [
                                {"name": "api", "containerPort": 9000},
                                {"name": "console", "containerPort": 9090},
                            ],
                            "envFrom": [
                                {"secretRef": {"name": "minio-creds"}},
                                {"configMapRef": {"name": "extra-config"}},
                            ],
                            "env": [
                                {"name": "MINIO_REGION", "value": "us-east-1"},
                                {
                                    "name": "MINIO_BROWSER_REDIRECT_URL",
                                    "value": "https://old.example.com",
                                },
                            ],
                            "volumeMounts": [
                                {"name": "data", "mountPath": "/data"},
                            ],
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "1", "memory": "1Gi"},
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/minio/health/live", "port": 9000},
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/minio/health/ready",
                                    "port": 9000,
                                },
                            },
                        },
                        {
                            "name": "sidecar",
                            "image": "busybox:1.36",
                            "command": ["sleep", "3600"],
                        },
                    ],
                    "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "minio-data"}}],
                },
            },
        },
        "status": {"readyReplicas": 1},
    }


class TestMinioOidcDeploymentPatch(unittest.TestCase):
    def test_preserves_image_mounts_probes_resources_and_env(self):
        live = _sample_deployment()
        patched = mod.build_oidc_deployment_definition(
            live,
            redirect_url="https://minio-console.apps.example.com",
        )
        container = patched["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], "quay.io/minio/minio:RELEASE.2024-01-01")
        self.assertEqual(container["volumeMounts"], live["spec"]["template"]["spec"]["containers"][0]["volumeMounts"])
        self.assertEqual(container["livenessProbe"], live["spec"]["template"]["spec"]["containers"][0]["livenessProbe"])
        self.assertEqual(container["readinessProbe"], live["spec"]["template"]["spec"]["containers"][0]["readinessProbe"])
        self.assertEqual(container["resources"], live["spec"]["template"]["spec"]["containers"][0]["resources"])
        self.assertEqual(container["ports"], live["spec"]["template"]["spec"]["containers"][0]["ports"])
        env_names = [e["name"] for e in container["env"]]
        self.assertIn("MINIO_REGION", env_names)
        self.assertEqual(
            next(e["value"] for e in container["env"] if e["name"] == "MINIO_BROWSER_REDIRECT_URL"),
            "https://minio-console.apps.example.com",
        )

    def test_preserves_existing_env_from_and_adds_oidc_once(self):
        live = _sample_deployment()
        patched = mod.build_oidc_deployment_definition(live, redirect_url="https://x")
        env_from = patched["spec"]["template"]["spec"]["containers"][0]["envFrom"]
        names = []
        for item in env_from:
            if "secretRef" in item:
                names.append(item["secretRef"]["name"])
            elif "configMapRef" in item:
                names.append(item["configMapRef"]["name"])
        self.assertEqual(names.count("minio-creds"), 1)
        self.assertEqual(names.count("minio-oidc"), 1)
        self.assertEqual(names.count("extra-config"), 1)

        again = mod.build_oidc_deployment_definition(patched, redirect_url="https://x")
        again_from = again["spec"]["template"]["spec"]["containers"][0]["envFrom"]
        again_names = [
            (i.get("secretRef") or {}).get("name")
            or (i.get("configMapRef") or {}).get("name")
            for i in again_from
        ]
        self.assertEqual(again_names.count("minio-oidc"), 1)

    def test_preserves_other_containers_and_annotations(self):
        live = _sample_deployment()
        patched = mod.build_oidc_deployment_definition(live, redirect_url="https://x")
        containers = patched["spec"]["template"]["spec"]["containers"]
        self.assertEqual(len(containers), 2)
        self.assertEqual(containers[1]["name"], "sidecar")
        self.assertEqual(containers[1]["image"], "busybox:1.36")
        annotations = patched["spec"]["template"]["metadata"]["annotations"]
        self.assertEqual(annotations["existing.anno"], "keep")
        self.assertEqual(annotations["ado.infra/minio-oidc"], "enabled")
        self.assertEqual(patched["metadata"]["annotations"]["keep.me"], "yes")
        self.assertNotIn("status", patched)
        self.assertNotIn("resourceVersion", patched["metadata"])

    def test_does_not_emit_incomplete_containers_array(self):
        """Guard against the merge_type=merge failure mode."""
        live = _sample_deployment()
        patched = mod.build_oidc_deployment_definition(live, redirect_url="https://x")
        container = patched["spec"]["template"]["spec"]["containers"][0]
        required = ("image", "ports", "volumeMounts", "livenessProbe", "resources", "args")
        for key in required:
            self.assertIn(key, container, f"patched container missing {key}")
        # Must not look like a partial-only container (name + envFrom alone).
        self.assertGreater(len(container.keys()), 4)

    def test_missing_deployment_raises_clear_error(self):
        with self.assertRaises(mod.MinioOidcDeploymentPatchError) as ctx:
            mod.build_oidc_deployment_definition({})
        self.assertIn("not found", str(ctx.exception).lower())

    def test_missing_container_raises_clear_error(self):
        live = _sample_deployment()
        live["spec"]["template"]["spec"]["containers"] = [
            {"name": "other", "image": "busybox"}
        ]
        with self.assertRaises(mod.MinioOidcDeploymentPatchError) as ctx:
            mod.build_oidc_deployment_definition(live, container_name="minio")
        self.assertIn("minio", str(ctx.exception).lower())
        self.assertIn("not found", str(ctx.exception).lower())

    def test_cli_idempotent_and_errors(self):
        live = _sample_deployment()
        payload = {
            "deployment": live,
            "redirect_url": "https://console.example.com",
            "container_name": "minio",
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        first = subprocess.run(
            [sys.executable, str(SCRIPT), path],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        definition = json.loads(first.stdout)["definition"]
        second_payload = copy.deepcopy(payload)
        second_payload["deployment"] = definition
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(second_payload, handle)
            path2 = handle.name
        second = subprocess.run(
            [sys.executable, str(SCRIPT), path2],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        again = json.loads(second.stdout)["definition"]
        env_from = again["spec"]["template"]["spec"]["containers"][0]["envFrom"]
        oidc_count = sum(
            1
            for item in env_from
            if (item.get("secretRef") or {}).get("name") == "minio-oidc"
        )
        self.assertEqual(oidc_count, 1)

        bad = subprocess.run(
            [sys.executable, str(SCRIPT), "-"],
            input=json.dumps({"deployment": {}}),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(bad.returncode, 1)
        self.assertIn("not found", bad.stderr.lower())


if __name__ == "__main__":
    unittest.main()
