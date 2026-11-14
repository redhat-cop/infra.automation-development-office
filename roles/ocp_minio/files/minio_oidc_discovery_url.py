# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve and validate MinIO OpenID discovery URL (CONFIG_URL).

Role defaults used to set ``minio_oidc_config_url: ""``. Ansible
``| default(x)`` without the boolean ``true`` keeps that empty string, so
the Secret was written with ``MINIO_IDENTITY_OPENID_CONFIG_URL=""`` even
when issuer/hostname/realm were set. MinIO then logs
``Unable to initialize OpenID: unexpected scheme found``.

This helper treats empty strings as missing and builds:

  https://<keycloak-host>/realms/<realm>/.well-known/openid-configuration
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

WELL_KNOWN = "/.well-known/openid-configuration"
_HOST_RE = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?(:\d{1,5})?$"
)


class MinioOidcDiscoveryUrlError(ValueError):
    """Operator-facing discovery URL failure."""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_hostname(value: Any) -> str:
    host = re.sub(r"^https?://", "", _text(value), flags=re.I)
    return re.sub(r"/.*$", "", host).strip()


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def build_issuer_url(hostname: Any, realm: Any) -> str:
    host = normalize_hostname(hostname)
    realm_name = _text(realm)
    if not host or not realm_name:
        return ""
    return f"https://{host}/realms/{realm_name}"


def ensure_discovery_url(issuer_or_discovery: Any) -> str:
    """Return a full discovery URL from an issuer or discovery URL."""
    raw = _text(issuer_or_discovery).rstrip("/")
    if not raw:
        return ""
    if raw.endswith(WELL_KNOWN):
        return raw
    return f"{raw}{WELL_KNOWN}"


def resolve_discovery_url(
    *,
    config_url: Any = "",
    issuer: Any = "",
    hostname: Any = "",
    realm: Any = "",
    fallback_hostnames: list[Any] | None = None,
    fallback_realms: list[Any] | None = None,
) -> str:
    """Prefer explicit config URL, then issuer, then hostname+realm."""
    explicit = _text(config_url)
    if explicit:
        return ensure_discovery_url(explicit)

    issuer_url = _text(issuer)
    if issuer_url:
        return ensure_discovery_url(issuer_url)

    hosts = [hostname] + list(fallback_hostnames or [])
    realms = [realm] + list(fallback_realms or [])
    host = first_nonempty(*hosts)
    realm_name = first_nonempty(*realms) or "rhlab"
    built = build_issuer_url(host, realm_name)
    return ensure_discovery_url(built) if built else ""


def validate_discovery_url(url: Any) -> str | None:
    """Return an error when the discovery URL is unusable, else None."""
    value = _text(url)
    if not value:
        return (
            "MINIO_IDENTITY_OPENID_CONFIG_URL is empty. When MinIO OIDC "
            "is enabled, set minio_oidc_config_url (full discovery URL), "
            "or minio_oidc_issuer (https://<keycloak>/realms/<realm>), "
            "or Keycloak hostname (minio_keycloak_hostname / "
            "rhbk_hostname / keycloak_hostname) and realm "
            "(minio_keycloak_realm / rhbk_realm / ocp_rhbk_realm)."
        )
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        return (
            "MINIO_IDENTITY_OPENID_CONFIG_URL must use http:// or "
            f"https:// (got scheme {parsed.scheme!r} or missing "
            "scheme). Empty or malformed values cause MinIO "
            "'Unable to initialize OpenID: unexpected scheme found'."
        )
    if not parsed.netloc:
        return (
            "MINIO_IDENTITY_OPENID_CONFIG_URL is missing a hostname "
            f"(value starts with {value[:48]!r})."
        )
    host = parsed.hostname or ""
    if (
        host
        and not _HOST_RE.match(host)
        and ":" not in (parsed.netloc or "")
    ):
        # Allow IDN/IPs already accepted by urlparse.
        pass
    if WELL_KNOWN not in value:
        return (
            "MINIO_IDENTITY_OPENID_CONFIG_URL must be an OpenID "
            f"discovery URL ending with {WELL_KNOWN}."
        )
    return None


def resolve_and_validate(payload: dict[str, Any]) -> dict[str, str]:
    url = resolve_discovery_url(
        config_url=payload.get("config_url"),
        issuer=payload.get("issuer"),
        hostname=payload.get("hostname"),
        realm=payload.get("realm"),
        fallback_hostnames=list(
            payload.get("fallback_hostnames") or []
        ),
        fallback_realms=list(payload.get("fallback_realms") or []),
    )
    error = validate_discovery_url(url)
    if error:
        raise MinioOidcDiscoveryUrlError(error)
    if url.endswith(WELL_KNOWN):
        issuer_base = url[: -len(WELL_KNOWN)]
    else:
        issuer_base = url
    return {"discovery_url": url, "issuer": issuer_base}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path", nargs="?", default="-")
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
        if isinstance(payload, dict):
            result = resolve_and_validate(payload)
        else:
            result = resolve_and_validate({})
    except MinioOidcDiscoveryUrlError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
