#!/usr/bin/env python3
"""Create a MinIO/S3 bucket with stdlib only (no mc, no boto3)."""
from __future__ import annotations

import hashlib
import hmac
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str) -> bytes:
    k_date = _sign(f"AWS4{secret}".encode("utf-8"), datestamp)
    k_region = hmac.new(k_date, region.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
    return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()


def _request(
    method: str,
    endpoint: str,
    bucket: str,
    access: str,
    secret: str,
    region: str,
) -> tuple[int, bytes]:
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    scheme = parsed.scheme or "http"
    path = f"/{bucket}"
    payload = b""
    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload).hexdigest()
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amzdate}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = (
        f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    scope = f"{datestamp}/{region}/s3/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amzdate}\n{scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )
    signature = hmac.new(
        _signing_key(secret, datestamp, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Host": host,
        "X-Amz-Date": amzdate,
        "X-Amz-Content-Sha256": payload_hash,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }
    url = f"{scheme}://{host}{path}"
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, method=method, headers=headers, data=payload or None)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def main() -> int:
    access = os.environ["MINIO_ROOT_USER"]
    secret = os.environ["MINIO_ROOT_PASSWORD"]
    endpoint = os.environ["S3_ENDPOINT"].rstrip("/")
    bucket = os.environ["S3_BUCKET"].strip()
    region = os.environ.get("S3_REGION", "us-east-1")
    if not bucket:
        print("S3_BUCKET is empty", file=sys.stderr)
        return 1
    code, _body = _request("HEAD", endpoint, bucket, access, secret, region)
    if code in (200, 204):
        print(f"bucket {bucket} exists")
        return 0
    code, body = _request("PUT", endpoint, bucket, access, secret, region)
    if code in (200, 201, 204, 409):
        print(f"bucket {bucket} ready ({code})")
        return 0
    print(f"failed to ensure bucket {bucket}: HTTP {code} {body!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
