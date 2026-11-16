"""Original Bug 4: Hub namespace routing, reserved redhat, deps, unpinned reqs.

Static checks of the Hub publish manifest, dest-repo-only skip / copy-into
validated path, reserved-namespace handling, kubernetes.core and ansible.eda
availability, and unpinned generated Controller requirements.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = (
    ROOT / "roles/bootstrap_generate_playbook_repo/files/preflight_hub_collections.yml"
)
PUBLISH_ONE = ROOT / "roles/bootstrap_controller/tasks/publish_one_preflight_collection.yml"
DEFAULTS = ROOT / "roles/bootstrap_controller/defaults/main.yml"
REQUIREMENTS_J2 = (
    ROOT / "roles/bootstrap_generate_playbook_repo/templates/requirements.yml.j2"
)


def collections_by_name():
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    rows = data["collections"]
    return {row["name"]: row for row in rows}


def test_kubernetes_core_and_ansible_eda_are_on_the_manifest() -> None:
    by_name = collections_by_name()
    for name in ("kubernetes.core", "ansible.eda"):
        row = by_name[name]
        assert row["hub_publish"] is True
        assert row["controller_requirements"] is True
        assert row.get("hub_publish_repository", "validated") != "rh-certified"
        assert row["namespace"] != "redhat"


def test_redhat_collections_route_to_rh_certified_and_never_create_namespace() -> None:
    by_name = collections_by_name()
    redhat = [row for name, row in by_name.items() if name.startswith("redhat.")]
    assert redhat, "expected redhat.* collections on the Hub manifest"
    for row in redhat:
        assert row["namespace"] == "redhat"
        assert row["hub_publish_repository"] == "rh-certified"
        assert row["hub_publish"] is True
    text = MANIFEST.read_text(encoding="utf-8")
    assert "never create the reserved" in text
    assert "``redhat`` namespace" in text or "`redhat` namespace" in text


def test_reserved_namespaces_default_to_redhat() -> None:
    text = DEFAULTS.read_text(encoding="utf-8")
    assert "bootstrap_controller_hub_reserved_namespaces:\n  - redhat" in text


def test_publish_never_creates_reserved_namespace() -> None:
    text = PUBLISH_ONE.read_text(encoding="utf-8")
    assert "Reserved namespaces (redhat) are never created" in text
    assert "bootstrap_controller_hub_pub_reserved_namespace" in text
    assert "Skip reserved Hub namespace when missing" in text
    start = text.index("- name: Publish preflight collection | Ensure Hub namespace exists")
    end = text.index("- name:", start + len("- name:"))
    ensure = text[start:end]
    assert "not (bootstrap_controller_hub_pub_reserved_namespace | bool)" in ensure


def test_already_present_is_destination_repo_only() -> None:
    text = PUBLISH_ONE.read_text(encoding="utf-8")
    assert "Only the destination repo counts" in text
    decide = text[
        text.index("Decide whether already present") : text.index(
            "Decide publish vs skip"
        )
    ]
    assert "equalto" in decide
    assert "bootstrap_controller_hub_pub_dest_repo_name | default('validated')" in decide
    assert "Presence on published/rh-certified must" in text


def test_copy_into_validated_from_other_repo() -> None:
    text = PUBLISH_ONE.read_text(encoding="utf-8")
    assert "bootstrap_controller_hub_pub_via_cross_repo_copy" in text
    assert "Copy from alternate Hub repo into destination" in text
    assert "copy_collection_version/" in text
    assert "will copy/promote" in text


def test_generated_hub_requirements_are_unpinned() -> None:
    text = REQUIREMENTS_J2.read_text(encoding="utf-8")
    assert "Do not pin versions here" in text
    assert "- name: {{ item.name }}" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version:") or stripped.startswith("- version:"):
            raise AssertionError(
                f"Hub requirements template must not pin versions: {stripped}"
            )
