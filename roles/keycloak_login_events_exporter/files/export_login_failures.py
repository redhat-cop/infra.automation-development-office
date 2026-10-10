#!/usr/bin/env python3
"""Expose Keycloak user LOGIN / LOGIN_ERROR events as Prometheus metrics.

Native keycloak_user_events_total does NOT include username. This exporter polls
the realm user-event store (GET /admin/realms/{realm}/events) and publishes
gauges for the recent window. It does not keep persistent counters.

Env:
  KEYCLOAK_URL          e.g. https://keycloak.apps.example.com
  KEYCLOAK_ADMIN_USER   admin
  KEYCLOAK_ADMIN_PASSWORD
  KEYCLOAK_REALMS       comma list (default: rhlab)
  KEYCLOAK_TOKEN_REALM  realm for admin-cli token (default: master)
  POLL_SECONDS          default 60
  EVENTS_MAX            default 500
  LISTEN_PORT           default 8080
"""
from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Tuple


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


BASE = env("KEYCLOAK_URL").rstrip("/")
ADMIN_USER = env("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASSWORD = env("KEYCLOAK_ADMIN_PASSWORD")
TOKEN_REALM = env("KEYCLOAK_TOKEN_REALM", "master")
REALMS = [r.strip() for r in env("KEYCLOAK_REALMS", "rhlab").split(",") if r.strip()]
POLL_SECONDS = max(15, int(env("POLL_SECONDS", "60") or "60"))
EVENTS_MAX = max(50, int(env("EVENTS_MAX", "500") or "500"))
LISTEN_PORT = int(env("LISTEN_PORT", "8080") or "8080")
VERIFY = env("KEYCLOAK_VERIFY_TLS", "false").lower() in ("1", "true", "yes")

_lock = threading.Lock()
_metrics = "# HELP keycloak_login_events_exporter_up Exporter scrape loop healthy\n# TYPE keycloak_login_events_exporter_up gauge\nkeycloak_login_events_exporter_up 0\n"
_token = ""
_token_exp = 0.0


def ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not VERIFY:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_json(method: str, url: str, headers: dict | None = None, body: bytes | None = None) -> Any:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, context=ssl_ctx(), timeout=60) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def get_token() -> str:
    global _token, _token_exp
    now = time.time()
    if _token and now < (_token_exp - 30):
        return _token
    data = urllib.parse.urlencode(
        {
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
            "grant_type": "password",
        }
    ).encode()
    tok = http_json(
        "POST",
        f"{BASE}/realms/{TOKEN_REALM}/protocol/openid-connect/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=data,
    )
    _token = tok["access_token"]
    _token_exp = now + float(tok.get("expires_in") or 60)
    return _token


def escape_label(value: str) -> str:
    return (
        (value or "unknown")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def map_error(err: str) -> str:
    e = (err or "").strip() or "unknown"
    return e


def fetch_events(realm: str, event_type: str) -> list[dict]:
    token = get_token()
    q = urllib.parse.urlencode({"type": event_type, "max": str(EVENTS_MAX)})
    url = f"{BASE}/admin/realms/{urllib.parse.quote(realm)}/events?{q}"
    events = http_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    return events if isinstance(events, list) else []


def fetch_login_errors(realm: str) -> list[dict]:
    return fetch_events(realm, "LOGIN_ERROR")


def fetch_logins(realm: str) -> list[dict]:
    return fetch_events(realm, "LOGIN")


def event_error(ev: dict) -> str:
    details = ev.get("details") or {}
    return str(ev.get("error") or details.get("error") or "").strip()


def is_success_login(ev: dict) -> bool:
    ev_type = str(ev.get("type") or "").strip().upper()
    return ev_type == "LOGIN" and not event_error(ev)


def event_identity(realm: str, ev: dict) -> Tuple[str, str, str, str]:
    details = ev.get("details") or {}
    username = (
        details.get("username")
        or details.get("user_name")
        or details.get("auth_username")
        or ev.get("userId")
        or "unknown"
    )
    client = ev.get("clientId") or details.get("client_id") or "unknown"
    ip = ev.get("ipAddress") or "unknown"
    return (realm, str(username), str(client), str(ip))


def event_key(realm: str, ev: dict) -> Tuple[str, str, str, str, str]:
    details = ev.get("details") or {}
    username = (
        details.get("username")
        or details.get("user_name")
        or details.get("auth_username")
        or ev.get("userId")
        or "unknown"
    )
    client = ev.get("clientId") or details.get("client_id") or "unknown"
    error = map_error(event_error(ev))
    ip = ev.get("ipAddress") or "unknown"
    return (realm, str(username), str(client), error, str(ip))


def _count_window(
    events_by_realm: dict[str, list[dict]],
    key_fn,
) -> tuple[Counter, Dict, list]:
    counts: Counter = Counter()
    last_ms: Dict = {}
    for realm, events in events_by_realm.items():
        for ev in events:
            key = key_fn(realm, ev)
            counts[key] += 1
            try:
                ts = int(ev.get("time") or 0)
            except (TypeError, ValueError):
                ts = 0
            if ts and ts >= last_ms.get(key, 0):
                last_ms[key] = ts
    ordered = sorted(
        counts.items(),
        key=lambda item: (-last_ms.get(item[0], 0), -item[1], item[0][1]),
    )
    return counts, last_ms, ordered


def build_metrics(
    events_by_realm: dict[str, list[dict]],
    success_by_realm: dict[str, list[dict]] | None = None,
) -> str:
    _counts, last_ms, ordered = _count_window(events_by_realm, event_key)

    lines = [
        "# HELP keycloak_login_failure_events Failed logins from Admin event store (recent window)",
        "# TYPE keycloak_login_failure_events gauge",
    ]
    for (realm, username, client, error, ip), n in ordered:
        lines.append(
            "keycloak_login_failure_events{"
            f'realm="{escape_label(realm)}",'
            f'username="{escape_label(username)}",'
            f'client_id="{escape_label(client)}",'
            f'error="{escape_label(error)}",'
            f'ip="{escape_label(ip)}"'
            f"}} {n}"
        )

    lines.extend(
        [
            "# HELP keycloak_login_failure_last_timestamp Most recent LOGIN_ERROR time (unix ms)",
            "# TYPE keycloak_login_failure_last_timestamp gauge",
        ]
    )
    for (realm, username, client, error, ip), _n in ordered:
        ts = last_ms.get((realm, username, client, error, ip), 0)
        if not ts:
            continue
        lines.append(
            "keycloak_login_failure_last_timestamp{"
            f'realm="{escape_label(realm)}",'
            f'username="{escape_label(username)}",'
            f'client_id="{escape_label(client)}",'
            f'error="{escape_label(error)}",'
            f'ip="{escape_label(ip)}"'
            f"}} {ts}"
        )

    success_by_realm = success_by_realm or {}
    _ok_counts, ok_last_ms, ok_ordered = _count_window(
        success_by_realm, event_identity
    )
    lines.extend(
        [
            "# HELP keycloak_login_success_events Successful logins from user event store (recent window)",
            "# TYPE keycloak_login_success_events gauge",
        ]
    )
    for (realm, username, client, ip), n in ok_ordered:
        lines.append(
            "keycloak_login_success_events{"
            f'realm="{escape_label(realm)}",'
            f'username="{escape_label(username)}",'
            f'client_id="{escape_label(client)}",'
            f'ip="{escape_label(ip)}"'
            f"}} {n}"
        )
    lines.extend(
        [
            "# HELP keycloak_login_success_last_timestamp Most recent LOGIN time (unix ms)",
            "# TYPE keycloak_login_success_last_timestamp gauge",
        ]
    )
    for (realm, username, client, ip), _n in ok_ordered:
        ts = ok_last_ms.get((realm, username, client, ip), 0)
        if not ts:
            continue
        lines.append(
            "keycloak_login_success_last_timestamp{"
            f'realm="{escape_label(realm)}",'
            f'username="{escape_label(username)}",'
            f'client_id="{escape_label(client)}",'
            f'ip="{escape_label(ip)}"'
            f"}} {ts}"
        )

    seen = sum(len(v) for v in events_by_realm.values()) + sum(
        len(v) for v in success_by_realm.values()
    )
    lines.extend(
        [
            "# HELP keycloak_login_events_exporter_up Exporter scrape loop healthy",
            "# TYPE keycloak_login_events_exporter_up gauge",
            "keycloak_login_events_exporter_up 1",
            "# HELP keycloak_login_events_exporter_events_seen Events loaded in last poll",
            "# TYPE keycloak_login_events_exporter_events_seen gauge",
            f"keycloak_login_events_exporter_events_seen {seen}",
        ]
    )
    return "\n".join(lines) + "\n"


def poll_loop() -> None:
    global _metrics
    while True:
        try:
            if not BASE or not ADMIN_PASSWORD:
                raise RuntimeError("KEYCLOAK_URL and KEYCLOAK_ADMIN_PASSWORD required")
            by_realm = {realm: fetch_login_errors(realm) for realm in REALMS}
            success_by_realm = {
                realm: [ev for ev in fetch_logins(realm) if is_success_login(ev)]
                for realm in REALMS
            }
            text = build_metrics(by_realm, success_by_realm)
            with _lock:
                _metrics = text
        except Exception as exc:  # noqa: BLE001 - keep loop alive
            err = escape_label(f"{type(exc).__name__}: {exc}")
            with _lock:
                _metrics = (
                    "# HELP keycloak_login_events_exporter_up Exporter scrape loop healthy\n"
                    "# TYPE keycloak_login_events_exporter_up gauge\n"
                    "keycloak_login_events_exporter_up 0\n"
                    "# HELP keycloak_login_events_exporter_error Last poll error\n"
                    "# TYPE keycloak_login_events_exporter_error gauge\n"
                    f'keycloak_login_events_exporter_error{{reason="{err}"}} 1\n'
                )
        time.sleep(POLL_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return
        with _lock:
            body = _metrics.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    threading.Thread(target=poll_loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
