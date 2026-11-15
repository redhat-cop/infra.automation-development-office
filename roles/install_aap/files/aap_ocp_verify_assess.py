#!/usr/bin/env python3
"""Assess AAP OpenShift install from kubernetes.core.k8s_info JSON dumps (no oc/kubectl)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _load(path: str):
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resources(blob):
    if isinstance(blob, dict):
        return blob.get("resources") or []
    return []


def _name(obj):
    return ((obj or {}).get("metadata") or {}).get("name") or ""


def _cond_map(obj):
    out = {}
    for c in ((obj or {}).get("status") or {}).get("conditions") or []:
        if c.get("type"):
            out[c["type"]] = {
                "status": c.get("status"),
                "reason": c.get("reason") or "",
                "message": (c.get("message") or "")[:500],
            }
    return out


def _pod_ready(pod):
    status = pod.get("status") or {}
    if (status.get("phase") or "") != "Running":
        return False
    for cs in status.get("containerStatuses") or []:
        if cs.get("ready") is True:
            continue
        waiting = ((cs.get("state") or {}).get("waiting") or {})
        if "CrashLoop" in str(waiting.get("reason") or ""):
            return False
        if cs.get("ready") is not True:
            return False
    return True


def _is_crash(pod):
    for cs in (pod.get("status") or {}).get("containerStatuses") or []:
        waiting = ((cs.get("state") or {}).get("waiting") or {})
        if "CrashLoop" in str(waiting.get("reason") or ""):
            return True
    return False


def assess(args):
    platform_blob = _load(args.platform)
    platforms = _resources(platform_blob)
    platform = platforms[0] if platforms else None
    controllers = _resources(_load(args.controllers))
    hubs = _resources(_load(args.hubs))
    edas = _resources(_load(args.edas))
    pods = _resources(_load(args.pods))
    pvcs = _resources(_load(args.pvcs))
    routes = _resources(_load(args.routes))
    svcs = _resources(_load(args.services))
    eps = _resources(_load(args.endpointslices))
    events = _resources(_load(args.events))

    blockers = []
    notes = []
    expect_controller = args.expect_controller
    expect_hub = args.expect_hub
    expect_eda = args.expect_eda
    expect_pg_sc = (args.expect_pg_sc or "").strip()
    attempt = args.attempt
    max_attempts = args.max_attempts
    http_status_i = args.http_status

    conditions = _cond_map(platform) if platform else {}
    failure = conditions.get("Failure") or {}
    successful = conditions.get("Successful") or {}
    running = conditions.get("Running") or {}
    fail_msg = failure.get("message") or ""
    fail_reason = failure.get("reason") or ""
    failed_task = ""
    operator_failed = str(failure.get("status") or "").lower() == "true"
    if operator_failed:
        blockers.append(
            "Platform CR Failure=True" + (f": {fail_msg}" if fail_msg else "")
        )
        if re.search(r"unknown playbook failure", fail_msg, re.I):
            failed_task = "Check django users list for admin user"
            notes.append(
                "Operator reported unknown playbook failure (often no_log). "
                "Likely failed task: Check django users list for admin user."
            )

    platform_name = _name(platform) if platform else args.instance
    if not platform:
        platform_status = "Missing"
        blockers.append("No AnsibleAutomationPlatform CR in the namespace.")
    elif operator_failed:
        platform_status = "Failed"
    elif str(successful.get("status") or "").lower() == "true":
        platform_status = "Reconciled"
    elif str(running.get("status") or "").lower() == "true":
        platform_status = "Reconciling"
    else:
        platform_status = "Present"

    spec = (platform or {}).get("spec") or {}
    db_spec = spec.get("database") if isinstance(spec.get("database"), dict) else {}
    pg_sc = str(db_spec.get("postgres_storage_class") or "").strip()
    pg_size_spec = ""
    try:
        pg_size_spec = (
            ((db_spec.get("storage_requirements") or {}).get("requests") or {}).get(
                "storage"
            )
            or ""
        )
    except Exception:
        pg_size_spec = ""
    if platform and not db_spec:
        notes.append(
            "Platform CR has no spec.database — StorageClass override may not have applied."
        )

    postgres_pvcs = [p for p in pvcs if re.search(r"postgres", _name(p), re.I)]
    pvc_sc = pvc_size = pvc_phase = ""
    if postgres_pvcs:
        pvc = postgres_pvcs[0]
        pvc_sc = str((pvc.get("spec") or {}).get("storageClassName") or "")
        pvc_size = str(
            (((pvc.get("status") or {}).get("capacity") or {}).get("storage"))
            or (
                (
                    ((pvc.get("spec") or {}).get("resources") or {}).get("requests")
                    or {}
                ).get("storage")
            )
            or ""
        )
        pvc_phase = str((pvc.get("status") or {}).get("phase") or "")

    effective_sc = pvc_sc or pg_sc
    effective_size = pvc_size or pg_size_spec
    mismatch = bool(expect_pg_sc and effective_sc and expect_pg_sc != effective_sc)
    if mismatch:
        blockers.append(
            f"PostgreSQL StorageClass mismatch: expected {expect_pg_sc}, found {effective_sc}."
        )

    def workload(plist, label):
        if not plist:
            return "Missing", False
        if any(_is_crash(p) for p in plist):
            blockers.append(f"{label} workload CrashLoopBackOff.")
            return "CrashLoopBackOff", False
        if all(_pod_ready(p) for p in plist):
            return "Ready", True
        return "Not ready", False

    pg_pods = [
        p
        for p in pods
        if re.search(r"postgres", _name(p), re.I)
        and not re.search(r"operator", _name(p), re.I)
    ]
    redis_pods = [
        p
        for p in pods
        if re.search(r"redis", _name(p), re.I)
        and not re.search(r"operator", _name(p), re.I)
    ]
    gw_pods = [
        p
        for p in pods
        if re.search(r"gateway", _name(p), re.I)
        and not re.search(r"operator|controller-manager", _name(p), re.I)
    ]

    pg_status, pg_ok = workload(pg_pods, "PostgreSQL")
    if postgres_pvcs and pvc_phase == "Bound" and pg_ok:
        pg_status = " · ".join(
            x for x in ["Ready", effective_sc or "default", effective_size or "?"] if x
        )
    elif postgres_pvcs and not pg_pods:
        pg_status = (
            f"PVC {pvc_phase or 'present'} · {effective_sc or '?'} · {effective_size or '?'}"
        )
        notes.append("PostgreSQL PVC present; pod not ready yet.")

    redis_status, redis_ok = workload(redis_pods, "Redis")
    gw_status, gw_ok = workload(gw_pods, "Gateway")

    def component(selected, resources, name):
        if not selected:
            return "Disabled by configuration", True
        if not resources:
            blockers.append(f"{name} CR was not created (selected).")
            return "Missing", False
        return "Ready", True

    ctrl_status, ctrl_ok = component(
        expect_controller, controllers, "AutomationController"
    )
    hub_status, hub_ok = component(expect_hub, hubs, "AutomationHub")
    if not expect_eda:
        eda_status, eda_ok = "Disabled by configuration", True
        if edas:
            blockers.append("EDA application CR exists but EDA was not selected.")
            eda_ok = False
            eda_status = "Present (unexpected)"
    else:
        eda_status, eda_ok = component(True, edas, "EDA")

    # Live Route only — never construct hostname patterns.
    route_obj = None
    instance = args.instance
    for r in routes:
        name = _name(r)
        to_name = (((r.get("spec") or {}).get("to") or {}).get("name") or "")
        labels = ((r.get("metadata") or {}).get("labels") or {})
        if name == instance or to_name == instance:
            route_obj = r
            break
        if labels.get("app.kubernetes.io/name") == instance:
            route_obj = r
            break
    if not route_obj:
        for r in routes:
            if _name(r).startswith(instance):
                route_obj = r
                break
    if not route_obj:
        for r in routes:
            to_name = (((r.get("spec") or {}).get("to") or {}).get("name") or "")
            if to_name == instance or re.search(r"gateway", _name(r), re.I):
                route_obj = r
                break

    route_name = route_host = route_url = ""
    admitted = backend_ready = False
    if route_obj:
        route_name = _name(route_obj)
        route_host = str(((route_obj.get("spec") or {}).get("host") or "")).strip()
        ingress = ((route_obj.get("status") or {}).get("ingress") or [])
        if ingress:
            admitted = any(
                c.get("type") == "Admitted"
                and str(c.get("status") or "").lower() == "true"
                for c in (ingress[0].get("conditions") or [])
            )
        if route_host:
            route_url = f"https://{route_host}"
        svc_name = (((route_obj.get("spec") or {}).get("to") or {}).get("name") or "")
        svc = next((s for s in svcs if _name(s) == svc_name), None)
        ready_eps = False
        for ep in eps:
            labels = ((ep.get("metadata") or {}).get("labels") or {})
            if labels.get("kubernetes.io/service-name") != svc_name:
                continue
            for endpoint in ep.get("endpoints") or []:
                cond = endpoint.get("conditions") or {}
                if cond.get("ready") is False:
                    continue
                if endpoint.get("addresses"):
                    ready_eps = True
                    break
        backend_ready = bool(svc) and ready_eps
        if route_host and not backend_ready:
            notes.append(
                f"Route {route_name} has host {route_host} but backend endpoints are not ready."
            )

    route_healthy = False
    if http_status_i is not None:
        if http_status_i == 503:
            blockers.append(
                "Gateway route returned HTTP 503 "
                "(URL available is not a healthy application)."
            )
        elif http_status_i in (200, 201, 301, 302, 303, 307, 308, 401, 403):
            route_healthy = True
            notes.append(f"Gateway HTTPS probe returned HTTP {http_status_i}.")
        else:
            notes.append(f"Gateway HTTPS probe returned HTTP {http_status_i}.")

    ready_blockers = []
    if not platform:
        ready_blockers.append("Platform CR missing")
    if not gw_ok:
        ready_blockers.append("Gateway not ready")
    if not pg_ok and not postgres_pvcs:
        ready_blockers.append("PostgreSQL not ready")
    if expect_controller and not controllers:
        ready_blockers.append("Controller CR missing")
    if expect_hub and not hubs:
        ready_blockers.append("Hub CR missing")
    if mismatch:
        ready_blockers.append("PostgreSQL StorageClass mismatch")
    if operator_failed:
        ready_blockers.append("Platform Failure=True")
    if not route_url:
        ready_blockers.append("Gateway Route not discovered")
    if route_url and not backend_ready:
        ready_blockers.append("Route backend not ready")
    if http_status_i == 503:
        ready_blockers.append("Route HTTP 503")

    if not ready_blockers and (
        route_healthy or http_status_i is None or not args.require_http_healthy
    ):
        # When probe not required/ skipped, backend_ready + children are enough.
        if http_status_i is None and route_url and backend_ready:
            overall, terminal = "ready", True
            blockers = []
        elif route_healthy and route_url and backend_ready:
            overall, terminal = "ready", True
            blockers = []
        elif not ready_blockers and route_url and backend_ready:
            overall, terminal = "ready", True
            blockers = []
        else:
            overall, terminal = "installing", False
            blockers = list(dict.fromkeys(blockers + ready_blockers))
    elif operator_failed:
        overall, terminal = "failed", True
        blockers = list(dict.fromkeys(blockers + ready_blockers))
    elif attempt >= max_attempts:
        overall = "failed"
        terminal = True
        blockers = list(dict.fromkeys(blockers + ready_blockers))
        blockers.append(f"Verification timed out after {max_attempts} attempts.")
    else:
        overall, terminal = "installing", False
        blockers = list(dict.fromkeys(blockers + ready_blockers))

    interesting_events = []
    for ev in sorted(
        events,
        key=lambda e: (
            e.get("lastTimestamp")
            or (e.get("metadata") or {}).get("creationTimestamp")
            or ""
        ),
        reverse=True,
    )[:8]:
        etype = ev.get("type") or ""
        if etype not in ("Warning", "Error"):
            continue
        inv = ev.get("involvedObject") or {}
        interesting_events.append(
            {
                "type": etype,
                "reason": ev.get("reason") or "",
                "message": (ev.get("message") or "")[:240],
                "involved": f"{inv.get('kind') or ''}/{inv.get('name') or ''}",
            }
        )

    return {
        "schema_version": 1,
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_status": overall,
        "cluster": {
            "api_host": args.api_host,
            "namespace": args.namespace,
            "deployment_version": args.version,
            "instance_name": instance,
        },
        "platform": {
            "name": platform_name,
            "status": platform_status,
            "conditions": [{"type": k, **v} for k, v in conditions.items()],
            "failure_task": failed_task,
            "failure_message": fail_msg,
            "failure_reason": fail_reason,
        },
        "postgresql": {
            "status": pg_status,
            "storage_class": effective_sc,
            "pvc_size": effective_size,
            "expected_storage_class": expect_pg_sc,
            "mismatch": mismatch,
            "ready": pg_ok,
        },
        "redis": {"status": redis_status, "ready": redis_ok},
        "gateway": {"status": gw_status, "ready": gw_ok},
        "controller": {
            "status": ctrl_status,
            "selected": expect_controller,
            "ready": ctrl_ok,
            "count": len(controllers),
        },
        "hub": {
            "status": hub_status,
            "selected": expect_hub,
            "ready": hub_ok,
            "count": len(hubs),
        },
        "eda": {
            "status": eda_status,
            "selected": expect_eda,
            "ready": eda_ok,
            "count": len(edas),
        },
        "route": {
            "name": route_name,
            "host": route_host,
            "url": route_url,
            "admitted": admitted,
            "backend_ready": backend_ready,
            "http_status": http_status_i,
            "healthy": bool(route_healthy),
        },
        "events": interesting_events,
        "blockers": blockers,
        "notes": notes,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "terminal": terminal,
        "engine": "kubernetes.core",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default="")
    parser.add_argument("--controllers", default="")
    parser.add_argument("--hubs", default="")
    parser.add_argument("--edas", default="")
    parser.add_argument("--pods", default="")
    parser.add_argument("--pvcs", default="")
    parser.add_argument("--routes", default="")
    parser.add_argument("--services", default="")
    parser.add_argument("--endpointslices", default="")
    parser.add_argument("--events", default="")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--api-host", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--expect-controller", action="store_true")
    parser.add_argument("--expect-hub", action="store_true")
    parser.add_argument("--expect-eda", action="store_true")
    parser.add_argument("--no-expect-controller", action="store_true")
    parser.add_argument("--no-expect-hub", action="store_true")
    parser.add_argument("--expect-pg-sc", default="")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=60)
    parser.add_argument("--http-status", type=int, default=None)
    parser.add_argument("--require-http-healthy", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.no_expect_controller:
        args.expect_controller = False
    if args.no_expect_hub:
        args.expect_hub = False
    result = assess(args)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overall_status": result["overall_status"], "terminal": result["terminal"], "url": result["route"].get("url")}))
    return 0 if result["overall_status"] != "verification_unavailable" else 2


if __name__ == "__main__":
    sys.exit(main())
