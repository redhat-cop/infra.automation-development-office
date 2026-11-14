# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a full MinIO Deployment definition with OIDC envFrom (safe patch).

JSON merge patch (kubernetes.core merge_type=merge) replaces the containers
array when a partial container is supplied. This helper deep-copies the live
Deployment and mutates only envFrom / env / annotations so image, mounts,
probes, resources, and sibling containers stay intact.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any


class MinioOidcDeploymentPatchError(ValueError):
    """Clear operator-facing failure (missing Deployment or container)."""


def _secret_ref_name(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    secret_ref = entry.get("secretRef") or entry.get("secret_ref") or {}
    if isinstance(secret_ref, dict):
        return str(secret_ref.get("name") or "").strip()
    return ""


def _env_name(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("name") or "").strip()


def ensure_secret_env_from(
    env_from: list | None,
    secret_name: str,
) -> list[dict[str, Any]]:
    """Return envFrom with secret_name present once (order preserved)."""
    items = [
        copy.deepcopy(x)
        for x in (env_from or [])
        if isinstance(x, dict)
    ]
    target = str(secret_name or "").strip()
    if not target:
        return items
    if any(_secret_ref_name(item) == target for item in items):
        return items
    items.append({"secretRef": {"name": target}})
    return items


def upsert_env_var(
    env: list | None,
    name: str,
    value: str,
) -> list[dict[str, Any]]:
    """Set or replace a single env var without dropping others."""
    items = [
        copy.deepcopy(x) for x in (env or []) if isinstance(x, dict)
    ]
    key = str(name or "").strip()
    if not key:
        return items
    for item in items:
        if _env_name(item) == key:
            item["value"] = value
            item.pop("valueFrom", None)
            return items
    items.append({"name": key, "value": value})
    return items


def build_oidc_deployment_definition(
    live_deployment: dict[str, Any],
    *,
    container_name: str = "minio",
    oidc_secret_name: str = "minio-oidc",
    redirect_url: str = "",
    annotation_key: str = "ado.infra/minio-oidc",
    annotation_value: str = "enabled",
    deployment_name: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Return a full Deployment definition from the live object."""
    if not isinstance(live_deployment, dict) or not live_deployment:
        raise MinioOidcDeploymentPatchError(
            "MinIO Deployment was not found. Deploy MinIO before "
            "Configure MinIO OIDC."
        )

    patched = copy.deepcopy(live_deployment)
    # Drop runtime-only fields that must not be re-posted.
    patched.pop("status", None)
    metadata = patched.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise MinioOidcDeploymentPatchError(
            "MinIO Deployment metadata is invalid."
        )
    for key in (
        "resourceVersion",
        "uid",
        "generation",
        "creationTimestamp",
        "managedFields",
        "selfLink",
    ):
        metadata.pop(key, None)
    if deployment_name:
        metadata["name"] = deployment_name
    if namespace:
        metadata["namespace"] = namespace

    patched["apiVersion"] = patched.get("apiVersion") or "apps/v1"
    patched["kind"] = "Deployment"

    spec = patched.setdefault("spec", {})
    if not isinstance(spec, dict):
        raise MinioOidcDeploymentPatchError(
            "MinIO Deployment spec is invalid."
        )
    template = spec.setdefault("template", {})
    if not isinstance(template, dict):
        raise MinioOidcDeploymentPatchError(
            "MinIO Deployment pod template is invalid."
        )
    tmpl_meta = template.setdefault("metadata", {})
    if not isinstance(tmpl_meta, dict):
        tmpl_meta = {}
        template["metadata"] = tmpl_meta
    annotations = tmpl_meta.setdefault("annotations", {})
    if not isinstance(annotations, dict):
        annotations = {}
        tmpl_meta["annotations"] = annotations
    if annotation_key:
        annotations[str(annotation_key)] = str(annotation_value)

    pod_spec = template.setdefault("spec", {})
    if not isinstance(pod_spec, dict):
        raise MinioOidcDeploymentPatchError(
            "MinIO Deployment pod spec is invalid."
        )
    containers = pod_spec.get("containers")
    if not isinstance(containers, list) or not containers:
        raise MinioOidcDeploymentPatchError(
            "MinIO Deployment has no containers to patch."
        )

    target = str(container_name or "minio").strip() or "minio"
    index = None
    for idx, container in enumerate(containers):
        name = (
            str(container.get("name") or "").strip()
            if isinstance(container, dict)
            else ""
        )
        if name == target:
            index = idx
            break
    if index is None:
        names = [
            str(c.get("name") or "")
            for c in containers
            if isinstance(c, dict)
        ]
        shown = ", ".join(n for n in names if n) or "none"
        raise MinioOidcDeploymentPatchError(
            f"Target container '{target}' was not found on the "
            f"MinIO Deployment (containers: {shown})."
        )

    container = containers[index]
    if not isinstance(container, dict):
        raise MinioOidcDeploymentPatchError(
            f"Target container '{target}' is not a mapping."
        )

    # Preserve image / mounts / probes / resources / ports / args.
    container["envFrom"] = ensure_secret_env_from(
        container.get("envFrom"),
        oidc_secret_name,
    )
    if redirect_url:
        container["env"] = upsert_env_var(
            container.get("env"),
            "MINIO_BROWSER_REDIRECT_URL",
            str(redirect_url),
        )

    containers[index] = container
    pod_spec["containers"] = containers
    return patched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        nargs="?",
        default="-",
        help="JSON payload path or '-' for stdin",
    )
    args = parser.parse_args(argv)
    if args.input_path == "-":
        raw = sys.stdin.read()
    else:
        raw = open(args.input_path, encoding="utf-8").read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"error": f"invalid JSON input: {exc}"}),
            file=sys.stderr,
        )
        return 2

    try:
        definition = build_oidc_deployment_definition(
            payload.get("deployment") or {},
            container_name=str(
                payload.get("container_name") or "minio"
            ),
            oidc_secret_name=str(
                payload.get("oidc_secret_name") or "minio-oidc"
            ),
            redirect_url=str(payload.get("redirect_url") or ""),
            annotation_key=str(
                payload.get("annotation_key") or "ado.infra/minio-oidc"
            ),
            annotation_value=str(
                payload.get("annotation_value") or "enabled"
            ),
            deployment_name=payload.get("deployment_name"),
            namespace=payload.get("namespace"),
        )
    except MinioOidcDeploymentPatchError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps({"definition": definition}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
