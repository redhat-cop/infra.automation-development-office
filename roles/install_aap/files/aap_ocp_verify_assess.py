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


def _workload(plist, label, blockers):
    if not plist:
        return "Missing", False
    if any(_is_crash(p) for p in plist):
        blockers.append(f"{label} workload CrashLoopBackOff.")
        return "CrashLoopBackOff", False
    if all(_pod_ready(p) for p in plist):
        return "Ready", True
    return "Not ready", False


def _component(selected, resources, name, blockers):
    if not selected:
        return "Disabled by configuration", True
    if not resources:
        blockers.append(f"{name} CR was not created (selected).")
        return "Missing", False
    return "Ready", True


def _platform_state(platform, conditions, args, blockers, notes):
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

    return {
        "platform_name": platform_name,
        "platform_status": platform_status,
        "fail_msg": fail_msg,
        "fail_reason": fail_reason,
        "failed_task": failed_task,
        "operator_failed": operator_failed,
    }


def _postgres_storage(platform, pvcs, expect_pg_sc, blockers, notes):
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
    return {
        "postgres_pvcs": postgres_pvcs,
        "pvc_phase": pvc_phase,
        "effective_sc": effective_sc,
        "effective_size": effective_size,
        "mismatch": mismatch,
    }


def _filter_pods(pods, pattern, exclude=r"operator"):
    return [
        p
        for p in pods
        if re.search(pattern, _name(p), re.I)
        and not re.search(exclude, _name(p), re.I)
    ]


def _postgres_status(pg_pods, storage, blockers, notes):
    pg_status, pg_ok = _workload(pg_pods, "PostgreSQL", blockers)
    postgres_pvcs = storage["postgres_pvcs"]
    pvc_phase = storage["pvc_phase"]
    effective_sc = storage["effective_sc"]
    effective_size = storage["effective_size"]
    if postgres_pvcs and pvc_phase == "Bound" and pg_ok:
        pg_status = " · ".join(
            x for x in ["Ready", effective_sc or "default", effective_size or "?"] if x
        )
    elif postgres_pvcs and not pg_pods:
        pg_status = (
            f"PVC {pvc_phase or 'present'} · {effective_sc or '?'} · "
            f"{effective_size or '?'}"
        )
        notes.append("PostgreSQL PVC present; pod not ready yet.")
    return pg_status, pg_ok


def _eda_status(expect_eda, edas, blockers):
    if not expect_eda:
        eda_status, eda_ok = "Disabled by configuration", True
        if edas:
            blockers.append("EDA application CR exists but EDA was not selected.")
            eda_ok = False
            eda_status = "Present (unexpected)"
        return eda_status, eda_ok
    return _component(True, edas, "EDA", blockers)


def _find_gateway_route(routes, instance):
    route_obj = None
    for r in routes:
        name = _name(r)
        to_name = (((r.get("spec") or {}).get("to") or {}).get("name") or "")
        labels = ((r.get("metadata") or {}).get("labels") or {})
        if name == instance or to_name == instance:
            return r
        if labels.get("app.kubernetes.io/name") == instance:
            return r
    for r in routes:
        if _name(r).startswith(instance):
            return r
    for r in routes:
        to_name = (((r.get("spec") or {}).get("to") or {}).get("name") or "")
        if to_name == instance or re.search(r"gateway", _name(r), re.I):
            return r
    return route_obj


def _endpoint_ready(eps, svc_name):
    for ep in eps:
        labels = ((ep.get("metadata") or {}).get("labels") or {})
        if labels.get("kubernetes.io/service-name") != svc_name:
            continue
        for endpoint in ep.get("endpoints") or []:
            cond = endpoint.get("conditions") or {}
            if cond.get("ready") is False:
                continue
            if endpoint.get("addresses"):
                return True
    return False


def _assess_route(route_obj, svcs, eps, http_status_i, blockers, notes):
    route_name = route_host = route_url = ""
    admitted = backend_ready = route_healthy = False
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
        ready_eps = _endpoint_ready(eps, svc_name)
        backend_ready = bool(svc) and ready_eps
        if route_host and not backend_ready:
            notes.append(
                f"Route {route_name} has host {route_host} but backend endpoints "
                "are not ready."
            )

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

    return {
        "route_name": route_name,
        "route_host": route_host,
        "route_url": route_url,
        "admitted": admitted,
        "backend_ready": backend_ready,
        "route_healthy": route_healthy,
        "http_status_i": http_status_i,
    }


def _ready_blockers(
    platform,
    gw_ok,
    pg_ok,
    postgres_pvcs,
    expect_controller,
    controllers,
    expect_hub,
    hubs,
    mismatch,
    operator_failed,
    route,
):
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
    if not route["route_url"]:
        ready_blockers.append("Gateway Route not discovered")
    if route["route_url"] and not route["backend_ready"]:
        ready_blockers.append("Route backend not ready")
    if route["http_status_i"] == 503:
        ready_blockers.append("Route HTTP 503")
    return ready_blockers


def _decide_overall(args, ready_blockers, route, operator_failed, blockers):
    http_status_i = route["http_status_i"]
    route_url = route["route_url"]
    backend_ready = route["backend_ready"]
    route_healthy = route["route_healthy"]
    attempt = args.attempt
    max_attempts = args.max_attempts

    if not ready_blockers and (
        route_healthy or http_status_i is None or not args.require_http_healthy
    ):
        if http_status_i is None and route_url and backend_ready:
            return "ready", True, []
        if route_healthy and route_url and backend_ready:
            return "ready", True, []
        if not ready_blockers and route_url and backend_ready:
            return "ready", True, []
        return "installing", False, list(dict.fromkeys(blockers + ready_blockers))
    if operator_failed:
        return "failed", True, list(dict.fromkeys(blockers + ready_blockers))
    if attempt >= max_attempts:
        merged = list(dict.fromkeys(blockers + ready_blockers))
        merged.append(f"Verification timed out after {max_attempts} attempts.")
        return "failed", True, merged
    return "installing", False, list(dict.fromkeys(blockers + ready_blockers))


def _interesting_events(events):
    interesting = []
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
        interesting.append(
            {
                "type": etype,
                "reason": ev.get("reason") or "",
                "message": (ev.get("message") or "")[:240],
                "involved": f"{inv.get('kind') or ''}/{inv.get('name') or ''}",
            }
        )
    return interesting


def assess(args):
    platforms = _resources(_load(args.platform))
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
    conditions = _cond_map(platform) if platform else {}
    plat = _platform_state(platform, conditions, args, blockers, notes)
    storage = _postgres_storage(
        platform, pvcs, (args.expect_pg_sc or "").strip(), blockers, notes
    )

    pg_pods = _filter_pods(pods, r"postgres")
    redis_pods = _filter_pods(pods, r"redis")
    gw_pods = _filter_pods(pods, r"gateway", exclude=r"operator|controller-manager")
    pg_status, pg_ok = _postgres_status(pg_pods, storage, blockers, notes)
    redis_status, redis_ok = _workload(redis_pods, "Redis", blockers)
    gw_status, gw_ok = _workload(gw_pods, "Gateway", blockers)

    ctrl_status, ctrl_ok = _component(
        args.expect_controller, controllers, "AutomationController", blockers
    )
    hub_status, hub_ok = _component(
        args.expect_hub, hubs, "AutomationHub", blockers
    )
    eda_status, eda_ok = _eda_status(args.expect_eda, edas, blockers)

    route_obj = _find_gateway_route(routes, args.instance)
    route = _assess_route(route_obj, svcs, eps, args.http_status, blockers, notes)
    ready_blockers = _ready_blockers(
        platform,
        gw_ok,
        pg_ok,
        storage["postgres_pvcs"],
        args.expect_controller,
        controllers,
        args.expect_hub,
        hubs,
        storage["mismatch"],
        plat["operator_failed"],
        route,
    )
    overall, terminal, blockers = _decide_overall(
        args, ready_blockers, route, plat["operator_failed"], blockers
    )

    return {
        "schema_version": 1,
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_status": overall,
        "cluster": {
            "api_host": args.api_host,
            "namespace": args.namespace,
            "deployment_version": args.version,
            "instance_name": args.instance,
        },
        "platform": {
            "name": plat["platform_name"],
            "status": plat["platform_status"],
            "conditions": [{"type": k, **v} for k, v in conditions.items()],
            "failure_task": plat["failed_task"],
            "failure_message": plat["fail_msg"],
            "failure_reason": plat["fail_reason"],
        },
        "postgresql": {
            "status": pg_status,
            "storage_class": storage["effective_sc"],
            "pvc_size": storage["effective_size"],
            "expected_storage_class": (args.expect_pg_sc or "").strip(),
            "mismatch": storage["mismatch"],
            "ready": pg_ok,
        },
        "redis": {"status": redis_status, "ready": redis_ok},
        "gateway": {"status": gw_status, "ready": gw_ok},
        "controller": {
            "status": ctrl_status,
            "selected": args.expect_controller,
            "ready": ctrl_ok,
            "count": len(controllers),
        },
        "hub": {
            "status": hub_status,
            "selected": args.expect_hub,
            "ready": hub_ok,
            "count": len(hubs),
        },
        "eda": {
            "status": eda_status,
            "selected": args.expect_eda,
            "ready": eda_ok,
            "count": len(edas),
        },
        "route": {
            "name": route["route_name"],
            "host": route["route_host"],
            "url": route["route_url"],
            "admitted": route["admitted"],
            "backend_ready": route["backend_ready"],
            "http_status": route["http_status_i"],
            "healthy": bool(route["route_healthy"]),
        },
        "events": _interesting_events(events),
        "blockers": blockers,
        "notes": notes,
        "attempt": args.attempt,
        "max_attempts": args.max_attempts,
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
    print(
        json.dumps(
            {
                "overall_status": result["overall_status"],
                "terminal": result["terminal"],
                "url": result["route"].get("url"),
            }
        )
    )
    return 0 if result["overall_status"] != "verification_unavailable" else 2


if __name__ == "__main__":
    sys.exit(main())
