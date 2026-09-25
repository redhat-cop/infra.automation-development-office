"""Build an OpenShift-compatible htpasswd map from a JSON job file or stdin."""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import sys


def _hash_with_stdlib_crypt(password: str) -> str | None:
    """Use stdlib crypt when present (removed in Python 3.13)."""
    try:
        import crypt
    except ImportError:
        return None
    hashed = crypt.crypt(password, crypt.METHOD_BLOWFISH)
    if not hashed:
        raise RuntimeError("crypt.crypt returned empty hash")
    return hashed


def _hash_with_libcrypt(password: str, rounds: int = 12) -> str:
    """Call libxcrypt via ctypes — no bcrypt Python package required.

    Contoller / Ansible EE images typically ship libxcrypt even when the
    Python ``crypt`` module and ``bcrypt`` package are absent (Python 3.13+).
    """
    lib = None
    candidates = []
    found = ctypes.util.find_library("crypt")
    if found:
        candidates.append(found)
    candidates.extend(("libcrypt.so.2", "libcrypt.so.1", "libcrypt.so"))
    last_error: OSError | None = None
    for candidate in candidates:
        try:
            lib = ctypes.CDLL(candidate, use_errno=True)
            break
        except OSError as exc:
            last_error = exc
    if lib is None:
        raise RuntimeError(
            "libcrypt is not available for bcrypt htpasswd hashing"
        ) from last_error
    if not hasattr(lib, "crypt_gensalt") or not hasattr(lib, "crypt"):
        raise RuntimeError(
            "libcrypt lacks crypt_gensalt/crypt (need libxcrypt with bcrypt)"
        )

    lib.crypt_gensalt.argtypes = [
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    lib.crypt_gensalt.restype = ctypes.c_char_p
    lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.crypt.restype = ctypes.c_char_p

    salt = lib.crypt_gensalt(b"$2b$", rounds, None, 0)
    if not salt:
        raise RuntimeError("libcrypt crypt_gensalt failed")
    hashed = lib.crypt(password.encode("utf-8"), salt)
    if not hashed:
        raise RuntimeError("libcrypt crypt failed")
    return hashed.decode("ascii")


def hash_password(password: str) -> str:
    """Return an OpenShift htpasswd bcrypt hash ($2y$...).

    Prefer system libcrypt (stdlib ``crypt`` or ctypes) so Contoller EEs do
    not need a ``bcrypt`` Python package. Optional ``bcrypt`` is used only if
    already installed.
    """
    hashed = _hash_with_stdlib_crypt(password)
    if hashed is None:
        try:
            hashed = _hash_with_libcrypt(password)
        except RuntimeError:
            try:
                import bcrypt
            except ImportError as exc:
                raise RuntimeError(
                    "Cannot hash htpasswd passwords: need libxcrypt "
                    "(system crypt) or an installed bcrypt Python package"
                ) from exc
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
    try:
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
            print(
                "Failed to hash htpasswd users: " + ", ".join(missing),
                file=sys.stderr,
            )
            return 1
        if not requested and action in ("add", "replace"):
            print(
                "No htpasswd users with name+password were provided to hash",
                file=sys.stderr,
            )
            return 1
        # Usernames only on stderr for operator logs (no hashes/passwords).
        print("Hashed htpasswd users: " + ", ".join(requested), file=sys.stderr)
        payload = {
            "map": out,
            "users": sorted(out.keys()),
            "requested": requested,
            "htpasswd": "\n".join(
                f"{name}:{out[name]}" for name in sorted(out.keys())
            ),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"hash_htpasswd_users.py failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
