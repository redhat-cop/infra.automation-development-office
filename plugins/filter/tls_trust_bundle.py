# SPDX-License-Identifier: GPL-3.0-or-later
"""Build CA trust PEMs from Kubernetes TLS secrets and PEM chains.

TLS verification needs *issuer* certificates (CA / intermediates), not the
leaf server certificate alone. cert-manager Secrets often include ``ca.crt``
and/or a multi-cert ``tls.crt`` chain; this filter prefers the CA material
and never treats a lone leaf as a trust anchor.
"""

from __future__ import annotations

import re

_CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


def split_pem_certificates(pem_text):
    """Return a list of PEM certificate strings (headers included)."""
    text = str(pem_text or "")
    return [match.group(0).strip() for match in _CERT_RE.finditer(text)]


def _normalize_pem_bundle(pem_text):
    certs = split_pem_certificates(pem_text)
    if not certs:
        return ""
    return "\n".join(certs) + "\n"


def trust_bundle_from_tls_secret(ca_crt="", tls_crt=""):
    """Build a CA trust PEM from Secret ``ca.crt`` / ``tls.crt`` fields.

    Preference order:
    1. ``ca.crt`` when it contains one or more PEM certificates
    2. Intermediate/root certs from ``tls.crt`` (leaf / first cert dropped)
    3. Empty string when only a leaf is present (cannot verify that leaf
       against itself via a standard trust store)
    """
    ca_bundle = _normalize_pem_bundle(ca_crt)
    if ca_bundle:
        return ca_bundle

    chain = split_pem_certificates(tls_crt)
    if len(chain) >= 2:
        return "\n".join(chain[1:]) + "\n"
    return ""


def first_pem_trust_bundle(*candidates):
    """Return the first candidate that contains at least one PEM certificate."""
    for candidate in candidates:
        bundle = _normalize_pem_bundle(candidate)
        if bundle:
            return bundle
    return ""


def pem_looks_like_certificate(pem_text):
    """True when the text contains a PEM certificate block."""
    return bool(split_pem_certificates(pem_text))


class FilterModule:
    """Ansible filters for TLS trust-bundle construction."""

    def filters(self):
        return {
            "tls_split_pem_certificates": split_pem_certificates,
            "tls_trust_bundle_from_secret": trust_bundle_from_tls_secret,
            "tls_first_pem_trust_bundle": first_pem_trust_bundle,
            "tls_pem_looks_like_certificate": pem_looks_like_certificate,
        }
