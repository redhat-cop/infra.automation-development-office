#!/usr/bin/env python3
"""Read running images and OLM subscriptions for the posture dashboard."""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from rhacs_report_analytics import extract_repository, extract_tag


def _list(host: str, token: str, path: str) -> list[dict]:
    context = ssl._create_unverified_context()
    items: list[dict] = []
    query = "limit=500"
    while True:
        url = f"{host.rstrip('/')}{path}?{query}"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120, context=context) as response:
            document = json.loads(response.read().decode("utf-8"))
        items.extend(item for item in (document.get("items") or []) if isinstance(item, dict))
        token_next = str((document.get("metadata") or {}).get("continue") or "")
        if not token_next:
            return items
        query = urllib.parse.urlencode({"continue": token_next, "limit": "500"})


def _images_from_pod_spec(spec: dict | None, found: dict[str, set[str]]) -> None:
    if not isinstance(spec, dict):
        return
    for key in ("containers", "initContainers", "ephemeralContainers"):
        for container in spec.get(key) or []:
            if not isinstance(container, dict):
                continue
            image = str(container.get("image") or "").strip()
            if not image:
                continue
            repository = extract_repository(image)
            host_part = repository.split("/", 1)[0] if repository else ""
            if repository and "/" in repository and "." not in host_part and ":" not in host_part:
                repository = f"docker.io/{repository}"
            tag = extract_tag(image)
            if repository and tag:
                found.setdefault(repository, set()).add(tag)


def _workload_images(host: str, token: str) -> dict[str, list[str]]:
    found: dict[str, set[str]] = {}
    workloads = (
        ("/apis/apps/v1/deployments", ("spec", "template", "spec")),
        ("/apis/apps/v1/daemonsets", ("spec", "template", "spec")),
        ("/apis/apps/v1/statefulsets", ("spec", "template", "spec")),
        ("/apis/batch/v1/cronjobs", ("spec", "jobTemplate", "spec", "template", "spec")),
    )
    for path, keys in workloads:
        try:
            items = _list(host, token, path)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: {path} {exc}", file=sys.stderr)
            continue
        for item in items:
            spec: dict | None = item
            for key in keys:
                spec = spec.get(key) if isinstance(spec, dict) else None
            _images_from_pod_spec(spec, found)
    return {repo: sorted(tags) for repo, tags in sorted(found.items())}


def _csv_project_counts(host: str, token: str) -> dict[str, int]:
    """Namespaces that have each ClusterServiceVersion. Copied operators count once per project."""
    try:
        items = _list(host, token, "/apis/operators.coreos.com/v1alpha1/clusterserviceversions")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: clusterserviceversions {exc}", file=sys.stderr)
        return {}
    counts: dict[str, int] = {}
    for item in items:
        name = str((item.get("metadata") or {}).get("name") or "")
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _subscriptions(host: str, token: str) -> list[dict]:
    try:
        items = _list(host, token, "/apis/operators.coreos.com/v1alpha1/subscriptions")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: subscriptions {exc}", file=sys.stderr)
        return []
    rows = []
    for item in items:
        meta = item.get("metadata") or {}
        spec = item.get("spec") or {}
        status = item.get("status") or {}
        installed = str(status.get("installedCSV") or "<none>")
        current = str(status.get("currentCSV") or "<none>")
        rows.append(
            {
                "operator": str(spec.get("name") or meta.get("name") or ""),
                "namespace": str(meta.get("namespace") or ""),
                "channel": str(spec.get("channel") or ""),
                "installed": installed,
                "current": current,
                "state": str(status.get("state") or ""),
            }
        )
    return rows


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: collect_cluster_posture.py IMAGES.json SUBSCRIPTIONS.json", file=sys.stderr)
        sys.exit(2)
    host = os.environ.get("K8S_AUTH_HOST", "").strip()
    token = os.environ.get("K8S_AUTH_API_KEY", "").strip()
    images_path = Path(sys.argv[1])
    subs_path = Path(sys.argv[2])
    images: dict[str, list[str]] = {}
    subscriptions: list[dict] = []
    if host and token:
        images = _workload_images(host, token)
        subscriptions = _subscriptions(host, token)
        project_counts = _csv_project_counts(host, token)
        for row in subscriptions:
            copies = project_counts.get(row["installed"]) or project_counts.get(row["current"]) or 0
            row["projects"] = copies or (1 if row.get("namespace") else 0)
    else:
        print("WARNING: OpenShift host or token missing; image and operator tables stay empty", file=sys.stderr)
    images_path.write_text(json.dumps(images), encoding="utf-8")
    subs_path.write_text(json.dumps(subscriptions), encoding="utf-8")
    print(f"images={len(images)} subscriptions={len(subscriptions)}")


if __name__ == "__main__":
    main()
