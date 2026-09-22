#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for ocp_absent_cleanup allowlist helpers (pure Python)."""

from __future__ import annotations


def _blocked(ns: str, blocked: list[str] | None = None) -> bool:
    blocked = [b.lower() for b in (blocked or [
        "default", "kube-system", "kube-public", "kube-node-lease", "openshift",
    ])]
    n = ns.lower().strip()
    if not n:
        return True
    if n in blocked:
        return True
    if n.startswith("kube-"):
        return True
    return False


def test_blocks_platform_namespaces():
    assert _blocked("kube-system")
    assert _blocked("default")
    assert _blocked("openshift")
    assert _blocked("kube-node-lease")
    assert _blocked("kube-public")


def test_allows_component_namespaces():
    assert not _blocked("cert-manager")
    assert not _blocked("cert-manager-operator")
    assert not _blocked("openshift-gitops")
    assert not _blocked("grafana")
    assert not _blocked("openshift-operators")


def test_blocks_empty():
    assert _blocked("")
    assert _blocked("  ")


if __name__ == "__main__":
    test_blocks_platform_namespaces()
    test_allows_component_namespaces()
    test_blocks_empty()
    print("PASS unit ocp_absent_cleanup")
