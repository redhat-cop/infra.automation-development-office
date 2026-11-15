"""Unit tests for install_aap kubernetes.core post-install assess script."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "roles/install_aap/files/aap_ocp_verify_assess.py"


def _dump(td: Path, name: str, resources):
    path = td / f"{name}.json"
    path.write_text(json.dumps({"resources": resources}), encoding="utf-8")
    return str(path)


def _ready_pod(name: str):
    return {
        "metadata": {"name": name},
        "status": {
            "phase": "Running",
            "containerStatuses": [{"name": "c", "ready": True}],
        },
    }


def _run(
    resources,
    *,
    expect_status,
    http=None,
    expect_controller=True,
    expect_hub=True,
    expect_eda=False,
    expect_pg="",
    attempt=1,
    max_attempts=5,
):
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        out = td / "out.json"
        args = [
            sys.executable,
            str(SCRIPT),
            "--platform",
            _dump(td, "platform", resources.get("platform", [])),
            "--controllers",
            _dump(td, "controllers", resources.get("controllers", [])),
            "--hubs",
            _dump(td, "hubs", resources.get("hubs", [])),
            "--edas",
            _dump(td, "edas", resources.get("edas", [])),
            "--pods",
            _dump(td, "pods", resources.get("pods", [])),
            "--pvcs",
            _dump(td, "pvcs", resources.get("pvcs", [])),
            "--routes",
            _dump(td, "routes", resources.get("routes", [])),
            "--services",
            _dump(td, "services", resources.get("services", [])),
            "--endpointslices",
            _dump(td, "eps", resources.get("eps", [])),
            "--events",
            _dump(td, "events", resources.get("events", [])),
            "--namespace",
            "aap-chad",
            "--instance",
            "aap-chad",
            "--api-host",
            "https://api.ocp-dev.dev.rhlab:6443",
            "--version",
            "stable-2.7",
            "--attempt",
            str(attempt),
            "--max-attempts",
            str(max_attempts),
            "--expect-pg-sc",
            expect_pg,
            "--output",
            str(out),
        ]
        args.append(
            "--expect-controller" if expect_controller else "--no-expect-controller"
        )
        args.append("--expect-hub" if expect_hub else "--no-expect-hub")
        if expect_eda:
            args.append("--expect-eda")
        if http is not None:
            args.extend(
                ["--http-status", str(http), "--require-http-healthy"]
            )
        subprocess.check_call(args)
        result = json.loads(out.read_text(encoding="utf-8"))
        assert result["overall_status"] == expect_status, (
            expect_status,
            result["overall_status"],
            result.get("blockers"),
        )
        return result


PLATFORM_OK = [
    {
        "metadata": {"name": "aap-chad"},
        "spec": {
            "database": {
                "postgres_storage_class": "synology-iscsi-storage",
                "storage_requirements": {"requests": {"storage": "20Gi"}},
            },
            "controller": {"disabled": False},
            "hub": {"disabled": False},
            "eda": {"disabled": True},
        },
        "status": {
            "conditions": [
                {"type": "Successful", "status": "True"},
                {"type": "Failure", "status": "False"},
            ]
        },
    }
]

ROUTE = [
    {
        "metadata": {
            "name": "aap-chad",
            "labels": {"app.kubernetes.io/name": "aap-chad"},
        },
        "spec": {
            "host": "aap-chad-aap-chad.apps.ocp-dev.dev.rhlab",
            "to": {"name": "aap-chad"},
        },
        "status": {
            "ingress": [{"conditions": [{"type": "Admitted", "status": "True"}]}]
        },
    }
]

SVC = [{"metadata": {"name": "aap-chad"}, "spec": {"ports": [{"port": 80}]}}]
EPS = [
    {
        "metadata": {"labels": {"kubernetes.io/service-name": "aap-chad"}},
        "endpoints": [
            {"addresses": ["10.0.0.1"], "conditions": {"ready": True}}
        ],
    }
]
PVC = [
    {
        "metadata": {"name": "postgres-15-aap-chad-0"},
        "spec": {
            "storageClassName": "synology-iscsi-storage",
            "resources": {"requests": {"storage": "20Gi"}},
        },
        "status": {"phase": "Bound", "capacity": {"storage": "20Gi"}},
    }
]
PODS = [
    _ready_pod("aap-chad-gateway-x"),
    _ready_pod("aap-chad-postgres-15-0"),
    _ready_pod("aap-chad-redis-0"),
]
CTRL = [{"metadata": {"name": "aap-chad-controller"}}]
HUB = [{"metadata": {"name": "aap-chad-hub"}}]


def test_healthy_installation_discovers_live_route_url():
    result = _run(
        {
            "platform": PLATFORM_OK,
            "controllers": CTRL,
            "hubs": HUB,
            "pods": PODS,
            "pvcs": PVC,
            "routes": ROUTE,
            "services": SVC,
            "eps": EPS,
        },
        expect_status="ready",
        http=200,
        expect_pg="synology-iscsi-storage",
    )
    assert (
        result["route"]["url"]
        == "https://aap-chad-aap-chad.apps.ocp-dev.dev.rhlab"
    )
    assert result["eda"]["status"] == "Disabled by configuration"


def test_gateway_ready_controller_hub_missing():
    _run(
        {
            "platform": PLATFORM_OK,
            "controllers": [],
            "hubs": [],
            "pods": PODS,
            "pvcs": PVC,
            "routes": ROUTE,
            "services": SVC,
            "eps": EPS,
        },
        expect_status="installing",
        http=200,
    )


def test_platform_failure_true():
    fail = [
        {
            "metadata": {"name": "aap-chad"},
            "spec": {
                "database": {"postgres_storage_class": "synology-iscsi-storage"}
            },
            "status": {
                "conditions": [
                    {
                        "type": "Failure",
                        "status": "True",
                        "message": "unknown playbook failure",
                        "reason": "Failed",
                    }
                ]
            },
        }
    ]
    result = _run(
        {
            "platform": fail,
            "controllers": [],
            "hubs": [],
            "pods": PODS,
            "pvcs": PVC,
            "routes": ROUTE,
            "services": SVC,
            "eps": EPS,
        },
        expect_status="failed",
        http=200,
    )
    assert result["platform"]["failure_task"] == (
        "Check django users list for admin user"
    )


def test_postgres_storageclass_mismatch():
    _run(
        {
            "platform": PLATFORM_OK,
            "controllers": CTRL,
            "hubs": HUB,
            "pods": PODS,
            "pvcs": PVC,
            "routes": ROUTE,
            "services": SVC,
            "eps": EPS,
        },
        expect_status="installing",
        http=200,
        expect_pg="nfs-csi",
    )


def test_route_http_503_not_ready():
    _run(
        {
            "platform": PLATFORM_OK,
            "controllers": CTRL,
            "hubs": HUB,
            "pods": PODS,
            "pvcs": PVC,
            "routes": ROUTE,
            "services": SVC,
            "eps": EPS,
        },
        expect_status="installing",
        http=503,
    )


def test_timeout_marks_failed():
    result = _run(
        {
            "platform": PLATFORM_OK,
            "controllers": [],
            "hubs": [],
            "pods": PODS,
            "pvcs": PVC,
            "routes": ROUTE,
            "services": SVC,
            "eps": EPS,
        },
        expect_status="failed",
        http=200,
        attempt=5,
        max_attempts=5,
    )
    assert any("timed out" in b.lower() for b in result["blockers"])
