"""Regression: NFS CSI bootstrap must not self-reference role vars in templates."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "roles" / "bootstrap_controller" / "tasks" / "install_nfs_csi.yml"
DEFAULTS = ROOT / "roles" / "ocp_nfs_storage" / "defaults" / "main.yml"
ROLE_TASKS = ROOT / "roles" / "ocp_nfs_storage" / "tasks" / "main.yml"


def test_install_nfs_csi_exists():
    assert INSTALL.is_file()


def test_no_recursive_include_role_templates():
    text = INSTALL.read_text(encoding="utf-8")
    # Antipattern that caused: recursive loop detected in template string
    # nfs_test_namespace — role var defaulting to itself in include_role vars.
    include_vars = text.split("ansible.builtin.include_role:", 1)[-1]
    assert "default(ocp_nfs_storage_test_namespace" not in include_vars
    assert "default(ocp_nfs_storage_test_pvc_name" not in include_vars
    assert "default(ocp_nfs_storage_test_pvc_size" not in include_vars
    assert "default(nfs_test_namespace" not in include_vars
    # Role vars must be set from resolved bootstrap_controller_* facts only.
    assert 'ocp_nfs_storage_test_namespace: "{{ bootstrap_controller_nfs_csi_test_namespace }}"' in text
    assert 'ocp_nfs_storage_test_pvc_name: "{{ bootstrap_controller_nfs_csi_test_pvc_name }}"' in text
    assert "bootstrap_controller_nfs_csi_test_namespace:" in text
    assert "ado-nfs-csi-test" in text
    assert "ado-nfs-csi-test-pvc" in text


def test_defaults_use_dedicated_claim():
    defaults = DEFAULTS.read_text(encoding="utf-8")
    assert "ocp_nfs_storage_test_namespace: ado-nfs-csi-test" in defaults
    assert "ocp_nfs_storage_test_pvc_name: ado-nfs-csi-test-pvc" in defaults
    for line in defaults.splitlines():
        if line.strip().startswith("ocp_nfs_storage_test_pvc_name:"):
            assert "ado-nfs-csi-test-pvc" in line
            assert "synology-nfs-pvc" not in line
            break
    else:
        raise AssertionError("ocp_nfs_storage_test_pvc_name missing from defaults")


def test_role_reports_independent_results_and_bound_wait():
    tasks = ROLE_TASKS.read_text(encoding="utf-8")
    assert "NFS CSI | Wait for test PVC Bound" in tasks
    assert "ocp_nfs_storage_result:" in tasks
    assert "NFS CSI | Print validation summary" in tasks
    assert "NFS CSI | Fail Bootstrap when required NFS validation failed" in tasks
    defaults = DEFAULTS.read_text(encoding="utf-8")
    assert "synology-nfs-pvc" in defaults  # docs/defaults still warn about lab claim


def test_no_self_default_assignment_pattern():
    """Catch `name: "{{ … | default(name) }}"` style recursion in install file."""
    text = INSTALL.read_text(encoding="utf-8")
    # Match include_role var lines that default a role var to itself.
    for match in re.finditer(
        r"^(\s+)(ocp_nfs_storage_\w+|nfs_test_\w+):\s*\"\{\{[^\"\n]*default\(\2",
        text,
        flags=re.MULTILINE,
    ):
        raise AssertionError(f"self-default assignment found: {match.group(0).strip()}")
