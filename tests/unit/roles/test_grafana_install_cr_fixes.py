"""Original Bug 6: Grafana install CR tasks keep the Controller-EE-safe constructs.

``.index('grafana')`` is a list method (the EE has no Jinja ``| index`` filter).
Nested ``default({})`` keeps empty CR paths from failing. ``from_yaml`` keeps
readiness-probe timeout/failure values as integers so the CRD does not 422.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESOURCES = ROOT / "roles/grafana_install/tasks/ensure-grafana-resources.yml"
MAIN = ROOT / "roles/grafana_install/tasks/main.yml"
OIDC = ROOT / "roles/grafana_install/tasks/configure-grafana-oidc.yml"


def test_container_index_uses_list_index_not_jinja_filter() -> None:
    text = RESOURCES.read_text(encoding="utf-8")
    assert ").index('grafana')" in text
    assert "List method .index(), not the missing Jinja | index filter" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "| index" not in stripped
        assert "|index" not in stripped


def test_nested_jinja_defaults_on_cr_container_path() -> None:
    text = RESOURCES.read_text(encoding="utf-8")
    assert ").deployment | default({})" in text
    assert ").spec | default({})" in text
    assert ").template | default({})" in text
    assert ").containers | default([])" in text
    assert "Nested default({}) chain" in text


def test_readiness_probe_values_are_integers_via_from_yaml() -> None:
    text = RESOURCES.read_text(encoding="utf-8")
    assert "grafana_install_container_readiness_yaml | from_yaml" in text
    assert "timeoutSeconds: {{ grafana_install_readiness_timeout_seconds | int }}" in text
    assert "failureThreshold: {{ grafana_install_readiness_failure_threshold | int }}" in text
    assert 'readinessProbe: "{{ grafana_install_container_readiness }}"' in text
    assert "from_yaml keeps timeoutSeconds / failureThreshold as ints" in text


def test_oidc_enabled_uses_nested_default() -> None:
    main = MAIN.read_text(encoding="utf-8")
    oidc = OIDC.read_text(encoding="utf-8")
    needle = "(oidc | default({})).enabled | default(false) | bool"
    assert needle in main
    assert needle in oidc
