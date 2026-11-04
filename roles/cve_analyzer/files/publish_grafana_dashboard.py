#!/usr/bin/env python3
"""POST a Grafana dashboard JSON file to /api/dashboards/db.

Avoids Ansible uri+no_log swallowing the real HTTP error. Auth via env:
  GRAFANA_URL, GRAFANA_USER, GRAFANA_PASSWORD
  optional GRAFANA_FOLDER_UID, GRAFANA_VALIDATE_CERTS=true|false

Writes a password-free result file next to the dashboard JSON:
  <dashboard>.publish-result.txt

Stable dashboard identity:
  - ``uid`` is required (from JSON, ``--uid``, or GRAFANA_DASHBOARD_UID).
  - Empty UID is refused so Grafana cannot auto-assign a random id.
  - ``overwrite: true`` updates the existing board for that UID.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Grafana dashboard UIDs: alphanumeric, dash, underscore; max 40 chars.
_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def write_result(path: Path, text: str) -> None:
    path.write_text(text + "\n")
    print(text)


def resolve_uid(dashboard: dict, uid_override: str) -> str:
    """Return the UID that will be published; raise ValueError if invalid."""
    uid = (uid_override or str(dashboard.get("uid") or "")).strip()
    if not uid:
        raise ValueError(
            "dashboard uid is required; refusing publish so Grafana cannot "
            "auto-assign a random UID"
        )
    if not _UID_RE.fullmatch(uid):
        raise ValueError(
            f"dashboard uid {uid!r} is invalid "
            "(expected [A-Za-z0-9_-]{1,40})"
        )
    return uid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dashboard_json")
    ap.add_argument("--message", default="Updated by cve-analyzer")
    ap.add_argument(
        "--uid",
        default="",
        help="Override dashboard.uid before publish (alias overwrite).",
    )
    ap.add_argument(
        "--title",
        default="",
        help="Override dashboard.title before publish.",
    )
    args = ap.parse_args()

    dash_path = Path(args.dashboard_json)
    result_path = Path(str(dash_path) + ".publish-result.txt")

    base = (os.environ.get("GRAFANA_URL") or "").rstrip("/")
    user = os.environ.get("GRAFANA_USER") or "admin"
    password = os.environ.get("GRAFANA_PASSWORD") or ""
    folder_uid = (os.environ.get("GRAFANA_FOLDER_UID") or "").strip()
    verify = (os.environ.get("GRAFANA_VALIDATE_CERTS") or "false").lower() in (
        "1",
        "true",
        "yes",
    )
    uid_override = (args.uid or os.environ.get("GRAFANA_DASHBOARD_UID") or "").strip()
    title_override = (args.title or os.environ.get("GRAFANA_DASHBOARD_TITLE") or "").strip()

    if not base:
        write_result(result_path, "ERROR: GRAFANA_URL is required")
        return 2
    if not password:
        write_result(result_path, "ERROR: GRAFANA_PASSWORD is required")
        return 2

    dashboard = json.loads(dash_path.read_text())
    dashboard.pop("id", None)
    dashboard["id"] = None
    dashboard["version"] = 1
    try:
        uid = resolve_uid(dashboard, uid_override)
    except ValueError as exc:
        write_result(result_path, f"ERROR: {exc}")
        return 2
    dashboard["uid"] = uid
    if title_override:
        dashboard["title"] = title_override
    if not str(dashboard.get("title") or "").strip():
        write_result(
            result_path,
            "ERROR: dashboard title is required after overrides",
        )
        return 2

    payload = {
        "dashboard": dashboard,
        "overwrite": True,
        "message": args.message,
    }
    if folder_uid:
        payload["folderUid"] = folder_uid

    body = json.dumps(payload).encode("utf-8")
    write_result(
        result_path,
        f"POST {base}/api/dashboards/db bytes={len(body)} "
        f"uid={dashboard.get('uid')} title={dashboard.get('title')!r}",
    )

    req = urllib.request.Request(
        f"{base}/api/dashboards/db",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")

    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    # Bounded HTTP timeout (Phase 1a). Default 120s matches prior hard-code.
    # Override via GRAFANA_HTTP_TIMEOUT (seconds). Does not change auth/payload.
    try:
        http_timeout = float(os.environ.get("GRAFANA_HTTP_TIMEOUT") or "120")
    except ValueError:
        http_timeout = 120.0

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=http_timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            write_result(result_path, f"HTTP {resp.status} {raw[:1000]}")
            if resp.status != 200:
                return 1
            # Confirm Grafana kept our stable UID (do not accept a random uid).
            try:
                body_json = json.loads(raw)
            except json.JSONDecodeError:
                return 0
            returned = str(body_json.get("uid") or "").strip()
            if returned and returned != uid:
                write_result(
                    result_path,
                    f"ERROR: Grafana returned uid={returned!r}, "
                    f"expected {uid!r}",
                )
                return 1
            return 0
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        write_result(result_path, f"HTTP {e.code} {raw[:2000]}")
        return 1
    except Exception as e:
        write_result(result_path, f"REQUEST_ERROR {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
