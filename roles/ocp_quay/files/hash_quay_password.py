#!/usr/bin/env python3
"""Print a bcrypt hash for QUAY_ADMIN_PASSWORD (stdlib extras: bcrypt or passlib)."""
from __future__ import annotations

import os
import sys


def main() -> int:
    password = os.environ.get("QUAY_ADMIN_PASSWORD", "")
    if not password:
        print("QUAY_ADMIN_PASSWORD is empty", file=sys.stderr)
        return 1
    try:
        import bcrypt

        print(bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode())
        return 0
    except ImportError:
        pass
    try:
        from passlib.hash import bcrypt as passlib_bcrypt

        print(passlib_bcrypt.using(rounds=12).hash(password))
        return 0
    except ImportError:
        print("need bcrypt or passlib to hash the Quay admin password", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
