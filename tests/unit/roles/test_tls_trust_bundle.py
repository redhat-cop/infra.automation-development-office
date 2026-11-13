# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for TLS trust-bundle filter helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load():
    path = ROOT / "plugins" / "filter" / "tls_trust_bundle.py"
    spec = importlib.util.spec_from_file_location("tls_trust_bundle_filter", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


F = _load()

LEAF = """-----BEGIN CERTIFICATE-----
LEAFDATA
-----END CERTIFICATE-----"""

INTERMEDIATE = """-----BEGIN CERTIFICATE-----
INTERMEDIATEDATA
-----END CERTIFICATE-----"""

ROOT_CERT = """-----BEGIN CERTIFICATE-----
ROOTDATA
-----END CERTIFICATE-----"""

OTHER_CA = """-----BEGIN CERTIFICATE-----
OTHERCADATA
-----END CERTIFICATE-----"""


def test_split_pem_certificates():
    chain = f"{LEAF}\n{INTERMEDIATE}\n{ROOT_CERT}\n"
    certs = F.split_pem_certificates(chain)
    assert len(certs) == 3
    assert "LEAFDATA" in certs[0]
    assert "ROOTDATA" in certs[2]


def test_idm_acme_style_secret_prefers_ca_crt():
    bundle = F.trust_bundle_from_tls_secret(ca_crt=ROOT_CERT, tls_crt=f"{LEAF}\n{INTERMEDIATE}")
    assert "ROOTDATA" in bundle
    assert "LEAFDATA" not in bundle


def test_chain_without_ca_crt_drops_leaf():
    bundle = F.trust_bundle_from_tls_secret(ca_crt="", tls_crt=f"{LEAF}\n{INTERMEDIATE}\n{ROOT_CERT}")
    assert "LEAFDATA" not in bundle
    assert "INTERMEDIATEDATA" in bundle
    assert "ROOTDATA" in bundle


def test_leaf_only_tls_crt_is_not_a_trust_anchor():
    bundle = F.trust_bundle_from_tls_secret(ca_crt="", tls_crt=LEAF)
    assert bundle == ""


def test_public_style_empty_inputs_yield_empty_bundle():
    assert F.trust_bundle_from_tls_secret("", "") == ""
    assert F.first_pem_trust_bundle("", None, "not a cert") == ""


def test_custom_ca_bundle_selected_from_candidates():
    bundle = F.first_pem_trust_bundle("", "garbage", OTHER_CA, ROOT_CERT)
    assert "OTHERCADATA" in bundle
    assert F.pem_looks_like_certificate(bundle) is True


def test_missing_ca_chain_is_detectable():
    assert F.pem_looks_like_certificate("not a certificate") is False
    assert F.pem_looks_like_certificate("") is False
    assert F.trust_bundle_from_tls_secret(tls_crt=LEAF) == ""


def test_filter_module_registers_names():
    names = F.FilterModule().filters()
    assert "tls_trust_bundle_from_secret" in names
    assert "tls_first_pem_trust_bundle" in names
    assert "tls_pem_looks_like_certificate" in names
