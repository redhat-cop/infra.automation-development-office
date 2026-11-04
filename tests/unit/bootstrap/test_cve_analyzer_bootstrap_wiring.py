"""Static checks: CVE Analyzer bootstrap seeds, JT map, workflow, defaults."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
PLAYBOOK = (
    REPO
    / "roles/bootstrap_generate_playbook_repo/files/playbooks/cve_analyzer"
    / "ado-cve-analyzer-bootstrap.yml"
)
PLAYBOOK_DEFAULTS = (
    REPO / "roles/bootstrap_generate_playbook_repo/defaults/main.yml"
)
JT_DIR = REPO / "roles/bootstrap_controller/files/job_templates"
WF = (
    REPO
    / "roles/bootstrap_controller/files/workflows"
    / "ado-cve-analyzer-workflow-bootstrap.wf.yml"
)
GENERATE = REPO / "roles/bootstrap_controller/tasks/generate_aap_configs.yml"
DEFAULTS = (
    REPO / "roles/bootstrap_resolve_component/files/components_defaults.yml"
)
VARS_J2 = (
    REPO / "roles/bootstrap_generate_env_vars/templates/component_vars.yml.j2"
)
VAULT_J2 = (
    REPO / "roles/bootstrap_generate_env_vars/templates/component_vault.yml.j2"
)
OPENSHIFT_WF = (
    REPO
    / "roles/bootstrap_controller/files/workflows"
    / "ado-openshift-workflow-bootstrap.wf.yml"
)
ACS_REPORT_WF = (
    REPO
    / "roles/bootstrap_controller/files/workflows"
    / "ado-acs-report-workflow-bootstrap.wf.yml"
)

# Filename slug → role action value set in JT extra_vars.
EXPECTED_JT_ACTIONS = (
    ("full", "full"),
    ("enrichment", "enrichment"),
    ("fetch-export", "fetch_export"),
    ("publish-rhacs-posture", "publish_rhacs_posture"),
    ("publish-metrics", "publish_metrics"),
    ("repair-posture-metrics", "repair_posture_metrics"),
    ("publish-grafana", "publish_grafana"),
    ("cve-intel", "cve_intel"),
)


def test_thin_playbook_invokes_collection_role() -> None:
    text = PLAYBOOK.read_text()
    assert "infra.automation_development_office.cve_analyzer" in text
    assert "component: cve_analyzer" in text
    assert "vault_openshift.yml" in text
    # Action comes from JT extra_vars — playbook must not hard-code a default.
    assert "cve_analyzer_action:" not in text


def test_component_map_and_generated_playbook_entry() -> None:
    data = yaml.safe_load(PLAYBOOK_DEFAULTS.read_text())
    assert data["bootstrap_generate_playbook_repo_component_map"][
        "cve_analyzer"
    ] == ["cve_analyzer"]
    # Not auto-bundled into every OpenShift stack selection.
    assert "cve_analyzer" not in data[
        "bootstrap_generate_playbook_repo_component_map"
    ]["openshift"]
    apps = {
        item["app"]
        for item in data["bootstrap_generate_playbook_repo_generated_playbooks"]
    }
    assert "cve_analyzer" in apps
    dests = {
        item["dest"]
        for item in data["bootstrap_generate_playbook_repo_generated_playbooks"]
        if item.get("app") == "cve_analyzer"
    }
    assert dests == {
        "playbooks/cve_analyzer/ado-cve-analyzer-bootstrap.yml"
    }


def test_job_templates_cover_supported_actions() -> None:
    found = []
    for slug, action in EXPECTED_JT_ACTIONS:
        path = JT_DIR / f"ado-cve-analyzer-{slug}-bootstrap.jt.yml"
        assert path.is_file(), path.name
        data = yaml.safe_load(path.read_text())
        tmpl = data["controller_templates"][0]
        assert tmpl["playbook"] == (
            "playbooks/cve_analyzer/ado-cve-analyzer-bootstrap.yml"
        )
        assert tmpl["extra_vars"]["cve_analyzer_action"] == action
        # Shared Contoller primitives — not lab-hardcoded names.
        assert tmpl["organization"] == (
            "{{ bootstrap_controller_organization }}"
        )
        assert tmpl["inventory"] == (
            "{{ bootstrap_controller_inventory_name }}"
        )
        assert tmpl["project"] == "{{ bootstrap_controller_project_name }}"
        assert tmpl["execution_environment"] == (
            "{{ bootstrap_controller_execution_environment_name }}"
        )
        assert tmpl["credentials"] == ["{{ bootstrap_controller_creds }}"]
        assert "ADO | cve_analyzer" in path.read_text()
        found.append((slug, action))
    assert found == list(EXPECTED_JT_ACTIONS)


def test_jt_map_registers_cve_analyzer() -> None:
    text = GENERATE.read_text()
    assert "cve_analyzer:" in text
    for slug, _action in EXPECTED_JT_ACTIONS:
        assert f"ado-cve-analyzer-{slug}-bootstrap.jt.yml" in text


def test_repair_jt_not_in_workflow() -> None:
    wf_text = WF.read_text()
    assert "Repair Posture Metrics" not in wf_text
    assert "repair_posture_metrics" not in wf_text


def test_optional_dedicated_workflow_not_in_acs_or_openshift() -> None:
    wf = yaml.safe_load(WF.read_text())
    nodes = wf["controller_workflow_job_templates"][0][
        "simplified_workflow_nodes"
    ]
    ids = [n["identifier"] for n in nodes]
    assert ids == [
        "CVE Analyzer Fetch Export",
        "CVE Analyzer Publish RHACS Posture",
        "CVE Analyzer Publish Namespace Metrics",
    ]
    templates = [n["unified_job_template"] for n in nodes]
    assert templates == [
        "ADO | CVE Analyzer | Fetch Export",
        "ADO | CVE Analyzer | Publish RHACS Posture",
        "ADO | CVE Analyzer | Publish Namespace Metrics",
    ]
    gen = GENERATE.read_text()
    assert "ado-cve-analyzer-workflow-bootstrap.wf.yml" in gen
    assert "'cve_analyzer' in bootstrap_controller_effective_components" in gen
    assert (
        "'cve_analyzer' not in bootstrap_controller_effective_components" in gen
    )
    # Must not couple into ACS report or OpenShift deploy workflows.
    assert "CVE Analyzer" not in OPENSHIFT_WF.read_text()
    assert "CVE Analyzer" not in ACS_REPORT_WF.read_text()


def test_components_defaults_and_env_templates() -> None:
    defaults = yaml.safe_load(DEFAULTS.read_text())
    cve = defaults["components_defaults"]["cve_analyzer"]
    assert cve["cve_analyzer_vuln_dashboard_uid"] == "ado-rhacs-vuln-posture"
    assert cve["cve_analyzer_vuln_dashboard_title"] == (
        "RHACS Vulnerability Posture (ADO)"
    )
    assert cve["cve_analyzer_dashboard_uid"] == "ado-rhacs-cve-triage"
    assert cve["cve_analyzer_phase0_feature_uids"] == []
    assert cve["cve_analyzer_cve_intel_panels"] is False
    vars_j2 = VARS_J2.read_text()
    vault_j2 = VAULT_J2.read_text()
    assert "component_name == 'cve_analyzer'" in vars_j2
    assert "cve_analyzer_phase0_feature_uids" in vars_j2
    assert "cve_analyzer_vuln_dashboard_title" in vars_j2
    assert "cve_analyzer_dashboard_uid" in vars_j2
    assert "cve_analyzer_clusters" in vars_j2
    assert "component_name == 'cve_analyzer'" in vault_j2
    assert "acs_api_token" in vault_j2
    assert "grafana_admin_password" in vault_j2
    # Secrets must not appear in plaintext vars template.
    assert "acs_api_token" not in vars_j2
    assert "grafana_admin_password" not in vars_j2


def test_acs_report_left_untouched() -> None:
    gen = GENERATE.read_text()
    assert "ado-acs-report-workflow-bootstrap.wf.yml" in gen
    assert "acs_report:" in gen
    assert (JT_DIR / "ado-acs-report-bootstrap.jt.yml").is_file()
