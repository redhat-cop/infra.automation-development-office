#!/usr/bin/env python3
"""Build an OpenShift-compatible htpasswd map from a JSON job file or stdin."""
from __future__ import annotations

import json
import sys


def hash_password(password: str) -> str:
    try:
        import bcrypt
    except ImportError:
        bcrypt = None
    if bcrypt is None:
        import crypt

        hashed = crypt.crypt(password, crypt.METHOD_BLOWFISH)
        if not hashed:
            raise RuntimeError("crypt.crypt returned empty hash (install bcrypt)")
    else:
        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12, prefix=b"2b"),
        ).decode("ascii")
    if hashed.startswith("$2b$"):
        return "$2y$" + hashed[4:]
    return hashed


def load_job(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: hash_htpasswd_users.py <job.json|->", file=sys.stderr)
        return 2
    job = load_job(sys.argv[1])
    users = job.get("users") or []
    action = str(job.get("action") or "add").lower()
    base = job.get("base") or {}
    if not isinstance(base, dict):
        base = {}
    out = {} if action == "replace" else dict(base)
    requested = []
    for user in users:
        if not isinstance(user, dict):
            continue
        name = str(user.get("name") or "").strip()
        password = str(user.get("password") or "").strip()
        if not name or not password:
            continue
        requested.append(name)
        out[name] = hash_password(password)
    missing = [name for name in requested if name not in out]
    if missing:
        print("Failed to hash htpasswd users: " + ", ".join(missing), file=sys.stderr)
        return 1
    if not requested and action in ("add", "replace"):
        print("No htpasswd users with name+password were provided to hash", file=sys.stderr)
        return 1
    # Usernames only on stderr for operator logs (no hashes/passwords).
    print("Hashed htpasswd users: " + ", ".join(requested), file=sys.stderr)
    payload = {
        "map": out,
        "users": sorted(out.keys()),
        "requested": requested,
        "htpasswd": "\n".join(f"{name}:{out[name]}" for name in sorted(out.keys())),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
