"""Unit tests for the rhel_stig_cac module utility and helper modules."""

from __future__ import absolute_import, division, print_function


__metaclass__ = type

import importlib.util
import json
import sys
import types
import xml.etree.ElementTree as ET

from pathlib import Path

import pytest


pytest.importorskip("ansible.module_utils.testing")
from ansible.module_utils.testing import patch_module_args  # noqa: E402


ROOT = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).parent / "fixtures" / "rhel_stig_cac"
DS = FIXTURES / "ds-mini.xml"
RESULTS = FIXTURES / "results-mini.xml"
PKG = "ansible_collections.infra.automation_development_office.plugins"
DEFAULT_PATTERNS = [
    "fips",
    "sshd",
    "pam_",
    r"^sudo_",
    "firewalld",
]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stub_package(name):
    package = types.ModuleType(name)
    package.__path__ = []
    sys.modules[name] = package
    return package


for _name in (
    "ansible_collections",
    "ansible_collections.infra",
    "ansible_collections.infra.automation_development_office",
    PKG,
    PKG + ".module_utils",
):
    _stub_package(_name)
stig = _load(PKG + ".module_utils.rhel_stig_cac", ROOT / "plugins/module_utils/rhel_stig_cac.py")
setattr(sys.modules[PKG + ".module_utils"], "rhel_stig_cac", stig)
resolve_module = _load("rhel_stig_cac_resolve", ROOT / "plugins/modules/rhel_stig_cac_resolve.py")
report_module = _load("rhel_stig_cac_report", ROOT / "plugins/modules/rhel_stig_cac_report.py")


@pytest.fixture(name="catalog")
def catalog_fixture():
    return stig.load_catalog(str(DS))


def _run(module, capsys, **args):
    """Run a module main() and return (exit_code, parsed_json)."""
    with patch_module_args(args):
        with pytest.raises(SystemExit) as exit_info:
            module.main()
    return exit_info.value.code, json.loads(capsys.readouterr().out)


# --- catalog ---------------------------------------------------------------


def test_catalog_reads_profile_and_stig_metadata(catalog):
    assert catalog["profile_found"]
    assert catalog["benchmark_version"] == "0.1.82"
    # Deselected rules and value selects are not part of the profile rules.
    assert catalog["profile_rules"] == [
        "accounts_password_pam_minlen",
        "package_sudo_installed",
        "service_auditd_enabled",
        "sshd_set_idle_timeout",
        "sshd_set_keepalive",
    ]
    record = catalog["rules"]["sshd_set_idle_timeout"]
    assert record["stig_ids"] == ["RHEL-09-255100"]
    assert record["vuln_ids"] == ["V-257996"]
    assert record["sv_ids"] == ["SV-257996r1134915_rule"]
    assert record["srg_ids"] == ["SRG-OS-000126-GPOS-00066"]
    assert record["requires"] == ["sshd_set_keepalive"]
    assert record["severity"] == "medium"


def test_catalog_unknown_profile_reports_not_found():
    catalog = stig.load_catalog(str(DS), "xccdf_org.ssgproject.content_profile_missing")
    assert catalog["profile_found"] is False
    assert catalog["profile_rules"] == []


# --- control resolution ----------------------------------------------------


@pytest.mark.parametrize(
    "control",
    [
        "RHEL-09-432010",
        "rhel-09-432010",
        "V-258083",
        "SV-258083r1045334_rule",
        "SV-258083",
        "package_sudo_installed",
        "xccdf_org.ssgproject.content_rule_package_sudo_installed",
    ],
)
def test_resolve_accepts_every_control_format(catalog, control):
    resolution = stig.resolve_controls(catalog, [control])
    assert resolution["rules"] == ["package_sudo_installed"]
    assert resolution["unmatched"] == []


def test_resolve_separates_unmatched_and_not_in_profile(catalog):
    resolution = stig.resolve_controls(
        catalog,
        ["RHEL-09-999999", "audit_rules_login_events", "RHEL-09-432010"],
    )
    assert resolution["rules"] == ["package_sudo_installed"]
    assert resolution["unmatched"] == ["RHEL-09-999999"]
    assert resolution["not_in_profile"] == ["audit_rules_login_events"]


def test_resolve_adds_required_rules(catalog):
    """XCCDF drops a rule whose requirement is not selected."""
    resolution = stig.resolve_controls(catalog, ["V-257996"])
    assert resolution["rules"] == ["sshd_set_idle_timeout", "sshd_set_keepalive"]
    assert resolution["dependencies"]["sshd_set_idle_timeout"] == ["sshd_set_keepalive"]


def test_resolve_ignores_blank_controls(catalog):
    assert stig.resolve_controls(catalog, ["", "  ", None])["rules"] == []


# --- protected controls ----------------------------------------------------


def test_protected_pattern_matching():
    compiled = stig.compile_patterns(DEFAULT_PATTERNS)
    assert stig.is_protected("sshd_set_idle_timeout", compiled)
    assert stig.is_protected("accounts_password_pam_minlen", compiled)
    assert not stig.is_protected("package_sudo_installed", compiled)
    assert not stig.is_protected("service_auditd_enabled", compiled)


def test_invalid_protected_pattern_is_reported():
    with pytest.raises(ValueError, match="Invalid protected rule pattern"):
        stig.compile_patterns(["("])


# --- tailoring -------------------------------------------------------------


def test_tailoring_deselects_everything_not_selected(catalog):
    xml = stig.build_tailoring(
        str(DS),
        stig.DEFAULT_PROFILE,
        catalog["profile_rules"],
        ["package_sudo_installed"],
    )
    root = ET.fromstring(xml)
    ns = "{%s}" % stig.XCCDF_NS
    profile = root.find(ns + "Profile")
    assert profile.get("extends") == stig.DEFAULT_PROFILE
    assert profile.get("id") == stig.TAILORED_PROFILE
    deselected = sorted(
        select.get("idref").replace(stig.RULE_ID_PREFIX, "")
        for select in profile.findall(ns + "select")
        if select.get("selected") == "false"
    )
    assert deselected == [
        "accounts_password_pam_minlen",
        "service_auditd_enabled",
        "sshd_set_idle_timeout",
        "sshd_set_keepalive",
    ]
    assert "package_sudo_installed" not in xml.split("<xccdf-1.2:select")[0]
    # The schema requires version/@time.
    assert root.find(ns + "version").get("time")


def test_tailoring_is_byte_identical_on_rerun(catalog):
    args = (str(DS), stig.DEFAULT_PROFILE, catalog["profile_rules"], ["service_auditd_enabled"])
    assert stig.build_tailoring(*args) == stig.build_tailoring(*args)


# --- results and findings --------------------------------------------------


def test_parse_results_reads_every_rule_result():
    meta, results = stig.parse_results(str(RESULTS))
    assert meta["target"] == "host1.example.test"
    assert meta["scap_score"] == 66.5
    assert meta["profile"] == stig.DEFAULT_PROFILE
    assert {item["rule"]: item["result"] for item in results} == {
        "sshd_set_idle_timeout": "pass",
        "sshd_set_keepalive": "fail",
        "package_sudo_installed": "fixed",
        "accounts_password_pam_minlen": "error",
        "service_auditd_enabled": "notselected",
        "audit_rules_login_events": "notapplicable",
    }


def test_parse_results_rejects_file_without_test_result(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<Benchmark xmlns='http://checklists.nist.gov/xccdf/1.2'/>", encoding="utf-8")
    with pytest.raises(ValueError, match="No XCCDF TestResult"):
        stig.parse_results(str(bad))


def test_findings_map_statuses_and_stig_ids(catalog):
    _meta, results = stig.parse_results(str(RESULTS))
    findings, not_selected = stig.build_findings(catalog, results)
    by_rule = {finding["rule"]: finding for finding in findings}
    assert not_selected == 1
    assert "service_auditd_enabled" not in by_rule
    assert by_rule["sshd_set_idle_timeout"]["status"] == "passed"
    assert by_rule["sshd_set_keepalive"]["status"] == "failed"
    assert by_rule["package_sudo_installed"]["status"] == "passed"
    assert by_rule["package_sudo_installed"]["remediated"] is True
    assert by_rule["accounts_password_pam_minlen"]["status"] == "error"
    assert by_rule["audit_rules_login_events"]["status"] == "not_applicable"
    assert by_rule["package_sudo_installed"]["stig_id"] == "RHEL-09-432010"
    assert by_rule["package_sudo_installed"]["vuln_id"] == "V-258083"
    assert by_rule["package_sudo_installed"]["category"] == "CAT I"
    assert by_rule["sshd_set_keepalive"]["category"] == "CAT II"


def test_selected_rule_oscap_did_not_evaluate_is_not_silent(catalog):
    """A selected rule reported notselected, or missing, must surface."""
    _meta, results = stig.parse_results(str(RESULTS))
    findings, not_selected = stig.build_findings(
        catalog,
        results,
        selected_rules=["service_auditd_enabled", "package_sudo_installed", "sshd_set_idle_timeout"],
    )
    assert not_selected == 0
    by_rule = {finding["rule"]: finding for finding in findings}
    assert by_rule["service_auditd_enabled"]["status"] == "not_evaluated"
    assert by_rule["sshd_set_idle_timeout"]["status"] == "passed"
    assert len(findings) == 3

    findings, not_selected = stig.build_findings(catalog, results, selected_rules=["sshd_set_keepalive", "ghost_rule"])
    assert not_selected == 0
    by_rule = {finding["rule"]: finding for finding in findings}
    assert by_rule["ghost_rule"]["status"] == "not_evaluated"
    assert by_rule["ghost_rule"]["result"] == "missing"


def test_summary_counts_and_failures(catalog):
    meta, results = stig.parse_results(str(RESULTS))
    findings, not_selected = stig.build_findings(catalog, results)
    summary = stig.summarize(findings, not_selected, meta)
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["error"] == 1
    assert summary["not_applicable"] == 1
    assert summary["fixed"] == 1
    assert summary["failed_by_category"] == {"CAT I": 0, "CAT II": 1, "CAT III": 0}
    # 2 passed of 4 assessed (passed + failed + error).
    assert summary["compliance_percent"] == 50.0
    # Sorted by STIG ID: RHEL-09-255095 before RHEL-09-611045.
    assert [item["rule"] for item in stig.failures(findings)] == [
        "sshd_set_keepalive",
        "accounts_password_pam_minlen",
    ]


def test_unknown_oscap_result_is_an_error_not_a_pass(catalog):
    findings, not_selected = stig.build_findings(catalog, [{"rule": "sshd_set_keepalive", "result": "brand-new", "severity": "medium"}])
    assert not_selected == 0
    assert findings[0]["status"] == "error"


def test_notchecked_is_not_evaluated_not_skipped(catalog):
    """OpenSCAP notchecked must stay distinct from skipped/pass."""
    findings, _not_selected = stig.build_findings(
        catalog,
        [{"rule": "sshd_set_keepalive", "result": "notchecked", "severity": "medium"}],
    )
    assert findings[0]["status"] == "not_evaluated"
    summary = stig.summarize(findings, 0)
    assert summary["not_evaluated"] == 1
    assert summary["skipped"] == 0
    assert [item["rule"] for item in stig.failures(findings)] == ["sshd_set_keepalive"]


# --- modules ---------------------------------------------------------------


def test_resolve_module_blocks_protected_and_writes_tailoring(tmp_path, capsys):
    tailoring = tmp_path / "out" / "tailoring.xml"
    code, out = _run(
        resolve_module,
        capsys,
        datastream=str(DS),
        controls=["V-257996", "RHEL-09-432010"],
        protected_patterns=DEFAULT_PATTERNS,
        tailoring_dest=str(tailoring),
    )
    assert code == 0
    assert out["rules"] == ["package_sudo_installed", "sshd_set_idle_timeout", "sshd_set_keepalive"]
    assert out["blocked_protected"] == ["sshd_set_idle_timeout", "sshd_set_keepalive"]
    assert out["changed"] is True
    assert tailoring.is_file()
    assert oct(tailoring.stat().st_mode & 0o777) == "0o640"

    # Second run with the same inputs reports no change.
    _code, again = _run(
        resolve_module,
        capsys,
        datastream=str(DS),
        controls=["V-257996", "RHEL-09-432010"],
        protected_patterns=DEFAULT_PATTERNS,
        tailoring_dest=str(tailoring),
    )
    assert again["changed"] is False


def test_resolve_module_allow_list_clears_block(tmp_path, capsys):
    _code, out = _run(
        resolve_module,
        capsys,
        datastream=str(DS),
        controls=["V-257996"],
        protected_patterns=DEFAULT_PATTERNS,
        allow_protected=["sshd_set_idle_timeout", "sshd_set_keepalive"],
    )
    assert out["blocked_protected"] == []


def test_resolve_module_unmatched_allow_protected_fails(capsys):
    code, out = _run(
        resolve_module,
        capsys,
        datastream=str(DS),
        controls=["V-257996"],
        protected_patterns=DEFAULT_PATTERNS,
        allow_protected=["sshd_set_idle_timeout", "typo_allow_entry"],
    )
    assert code == 1
    assert "typo_allow_entry" in out["msg"]
    assert "allow_protected" in out["msg"]


def test_resolve_module_without_controls_resolves_nothing(tmp_path, capsys):
    tailoring = tmp_path / "tailoring.xml"
    _code, out = _run(resolve_module, capsys, datastream=str(DS), tailoring_dest=str(tailoring))
    assert out["rules"] == []
    assert out["profile_rule_count"] == 5
    assert not tailoring.exists()


def test_resolve_module_check_mode_writes_nothing(tmp_path, capsys):
    tailoring = tmp_path / "tailoring.xml"
    _code, out = _run(
        resolve_module,
        capsys,
        datastream=str(DS),
        controls=["RHEL-09-432010"],
        tailoring_dest=str(tailoring),
        _ansible_check_mode=True,
    )
    assert out["changed"] is True
    assert not tailoring.exists()


def test_resolve_module_missing_datastream_fails(capsys):
    code, out = _run(resolve_module, capsys, datastream="/nonexistent/ds.xml")
    assert code == 1
    assert "not found" in out["msg"]


def test_resolve_module_unknown_profile_fails(capsys):
    code, out = _run(resolve_module, capsys, datastream=str(DS), profile="xccdf_org.nope")
    assert code == 1
    assert "xccdf_org.nope" in out["msg"]


def test_resolve_module_invalid_pattern_fails(capsys):
    code, out = _run(resolve_module, capsys, datastream=str(DS), protected_patterns=["("])
    assert code == 1
    assert "Invalid protected rule pattern" in out["msg"]


def test_report_module_writes_findings_file(tmp_path, capsys):
    findings = tmp_path / "findings.json"
    code, out = _run(
        report_module,
        capsys,
        results_path=str(RESULTS),
        datastream=str(DS),
        protected_patterns=DEFAULT_PATTERNS,
        context={"mode": "audit", "host": "host1"},
        findings_dest=str(findings),
    )
    assert code == 0
    assert out["summary"]["failed"] == 1
    assert "findings" not in out
    assert [item["rule"] for item in out["failures"]] == [
        "sshd_set_keepalive",
        "accounts_password_pam_minlen",
    ]
    document = json.loads(findings.read_text(encoding="utf-8"))
    assert document["schema"] == "ado.rhel_stig_cac.findings/v1"
    assert document["context"] == {"mode": "audit", "host": "host1"}
    assert document["benchmark_version"] == "0.1.82"
    assert document["scan"]["target"] == "host1.example.test"
    keepalive = next(item for item in document["findings"] if item["rule"] == "sshd_set_keepalive")
    assert keepalive["protected"] is True
    assert keepalive["stig_id"] == "RHEL-09-255095"


def test_report_module_findings_are_deterministic(tmp_path, capsys):
    findings = tmp_path / "findings.json"
    args = {"results_path": str(RESULTS), "datastream": str(DS), "findings_dest": str(findings)}
    _code, first = _run(report_module, capsys, **args)
    _code, second = _run(report_module, capsys, **args)
    assert first["changed"] is True
    assert second["changed"] is False


def test_report_module_return_findings_option(capsys):
    _code, out = _run(report_module, capsys, results_path=str(RESULTS), datastream=str(DS), return_findings=True)
    assert len(out["findings"]) == 5


def test_report_module_selected_rules_flags_unevaluated(capsys):
    _code, out = _run(
        report_module,
        capsys,
        results_path=str(RESULTS),
        datastream=str(DS),
        selected_rules=["service_auditd_enabled"],
    )
    assert out["summary"]["not_evaluated"] == 1
    assert out["failures"][0]["status"] == "not_evaluated"


def test_report_module_missing_results_fails(capsys):
    code, out = _run(report_module, capsys, results_path="/nonexistent/results.xml")
    assert code == 1
    assert "not found" in out["msg"]


def test_report_module_garbage_results_fails(tmp_path, capsys):
    bad = tmp_path / "bad.xml"
    bad.write_text("not xml", encoding="utf-8")
    code, out = _run(report_module, capsys, results_path=str(bad))
    assert code == 1
    assert "Cannot parse" in out["msg"]
