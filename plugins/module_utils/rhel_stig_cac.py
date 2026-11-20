# -*- coding: utf-8 -*-

# Copyright: Contributors to the infra.automation_development_office collection
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Helpers for SCAP Security Guide (SSG) STIG content and OpenSCAP results.

The helpers use only the Python standard library so they run on the managed
host with no extra packages and no network access (disconnected-safe).

Real SSG content tags every STIG rule with a STIG ID (``RHEL-09-211010``), a
vulnerability ID (``V-258049``), a rule ID (``SV-258049r1015092_rule``), and an
SRG. This module reads those from the installed data stream so findings can be
reported in STIG terms and controls can be selected by STIG ID.
"""

from __future__ import absolute_import, division, print_function


__metaclass__ = type

import re
import xml.etree.ElementTree as ET


XCCDF_NS = "http://checklists.nist.gov/xccdf/1.2"
RULE_ID_PREFIX = "xccdf_org.ssgproject.content_rule_"
DEFAULT_PROFILE = "xccdf_org.ssgproject.content_profile_stig"
TAILORED_PROFILE = "xccdf_org.ado_profile_stig_selected"
TAILORING_ID = "xccdf_org.ado_tailoring_stig"
TAILORING_TIME = "2000-01-01T00:00:00+00:00"
FINDINGS_SCHEMA = "ado.rhel_stig_cac.findings/v1"

STIG_ID_RE = re.compile(r"^RHEL-\d{2}-\d{6}$", re.IGNORECASE)
VULN_ID_RE = re.compile(r"^V-\d{5,7}$", re.IGNORECASE)
SV_ID_RE = re.compile(r"^SV-\d+(r\d+_rule)?$", re.IGNORECASE)
SRG_ID_RE = re.compile(r"^SRG-OS-\d{6}-GPOS-\d{5}$", re.IGNORECASE)
# XCCDF result -> normalized status used in ADO reports.
STATUS_MAP = {
    "pass": "passed",
    "fixed": "passed",
    "fail": "failed",
    "error": "error",
    "unknown": "error",
    "notapplicable": "not_applicable",
    # OpenSCAP did not evaluate the rule (missing probe/platform). Keep this
    # distinct from skipped so audit/verify do not treat it as a pass.
    "notchecked": "not_evaluated",
    "informational": "skipped",
    "notselected": "not_selected",
}

SEVERITY_CAT = {"high": "CAT I", "medium": "CAT II", "low": "CAT III"}


def _q(name):
    return "{%s}%s" % (XCCDF_NS, name)


def short_rule_id(rule_id):
    """Return the SSG rule name without the XCCDF prefix."""
    rule_id = (rule_id or "").strip()
    if rule_id.startswith(RULE_ID_PREFIX):
        return rule_id[len(RULE_ID_PREFIX):]
    return rule_id


def full_rule_id(rule_id):
    """Return the full XCCDF rule ID for a short SSG rule name."""
    rule_id = (rule_id or "").strip()
    if rule_id.startswith(RULE_ID_PREFIX):
        return rule_id
    return RULE_ID_PREFIX + rule_id


def _tokens(text):
    return [token for token in re.split(r"[\s,;]+", (text or "").strip()) if token]


def _append_unique(items, value):
    if value not in items:
        items.append(value)


def _rule_record(elem):
    """Build a metadata record from an XCCDF Rule element."""
    record = {
        "title": (elem.findtext(_q("title")) or "").strip(),
        "severity": elem.get("severity", "unknown"),
        "stig_ids": [],
        "vuln_ids": [],
        "sv_ids": [],
        "srg_ids": [],
        "requires": [
            short_rule_id(req.get("idref", ""))
            for req in elem.findall(_q("requires"))
            if req.get("idref", "").startswith(RULE_ID_PREFIX)
        ],
    }
    for ref in elem.findall(_q("reference")):
        for token in _tokens(ref.text):
            if STIG_ID_RE.match(token):
                _append_unique(record["stig_ids"], token.upper())
            elif VULN_ID_RE.match(token):
                _append_unique(record["vuln_ids"], token.upper())
            elif SV_ID_RE.match(token):
                _append_unique(record["sv_ids"], token)
            elif SRG_ID_RE.match(token):
                _append_unique(record["srg_ids"], token.upper())
    return record


def load_catalog(datastream_path, profile_id=DEFAULT_PROFILE):
    """Read rule metadata and profile membership from an SSG data stream.

    :returns: dict with ``rules`` (short id -> record), ``profile_rules``
        (sorted short ids selected by the profile), ``profile_found`` and
        ``benchmark_version``.
    """
    rules = {}
    profile_rules = None
    benchmark_version = None
    rule_tag = _q("Rule")
    profile_tag = _q("Profile")
    benchmark_tag = _q("Benchmark")
    for _event, elem in ET.iterparse(datastream_path, events=("end",)):
        tag = elem.tag
        if tag == rule_tag:
            rule_id = elem.get("id", "")
            if rule_id.startswith(RULE_ID_PREFIX):
                rules[short_rule_id(rule_id)] = _rule_record(elem)
            elem.clear()
        elif tag == profile_tag:
            if elem.get("id") == profile_id and profile_rules is None:
                profile_rules = sorted(
                    short_rule_id(sel.get("idref", ""))
                    for sel in elem.findall(_q("select"))
                    if sel.get("selected") == "true" and sel.get("idref", "").startswith(RULE_ID_PREFIX)
                )
        elif tag == benchmark_tag:
            benchmark_version = (elem.findtext(_q("version")) or "").strip() or None
    return {
        "rules": rules,
        "profile_rules": profile_rules or [],
        "profile_found": profile_rules is not None,
        "benchmark_version": benchmark_version,
    }


def parse_results(results_path):
    """Parse an ``oscap xccdf eval --results`` file.

    :raises ValueError: when the file has no XCCDF TestResult element.
    """
    root = ET.parse(results_path).getroot()
    if root.tag == _q("TestResult"):
        test_result = root
    else:
        found = root.findall(".//" + _q("TestResult"))
        test_result = found[-1] if found else None
    if test_result is None:
        raise ValueError("No XCCDF TestResult element found in %s" % results_path)

    profile_node = test_result.find(_q("profile"))
    score_node = test_result.find(_q("score"))
    score = None
    score_max = None
    if score_node is not None and (score_node.text or "").strip():
        try:
            score = float(score_node.text)
            score_max = float(score_node.get("maximum", "100"))
        except ValueError:
            score = None
    meta = {
        "start_time": test_result.get("start-time"),
        "end_time": test_result.get("end-time"),
        "profile": profile_node.get("idref") if profile_node is not None else None,
        "target": (test_result.findtext(_q("target")) or "").strip() or None,
        "scap_score": score,
        "scap_score_max": score_max,
    }
    results = []
    for node in test_result.findall(_q("rule-result")):
        results.append(
            {
                "rule": short_rule_id(node.get("idref", "")),
                "result": (node.findtext(_q("result")) or "unknown").strip(),
                "severity": node.get("severity", "unknown"),
            }
        )
    return meta, results


def compile_patterns(patterns):
    """Compile protected-rule regular expressions."""
    compiled = []
    for pattern in patterns or []:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            raise ValueError("Invalid protected rule pattern %r: %s" % (pattern, exc))
    return compiled


def is_protected(rule, compiled_patterns):
    """Return True when a short rule ID matches any protected pattern."""
    return any(pattern.search(rule) for pattern in compiled_patterns)


def build_index(catalog):
    """Map lowercase control identifiers to the SSG rules they select."""
    index = {}

    def add(key, rule):
        key = (key or "").strip().lower()
        if key:
            index.setdefault(key, [])
            if rule not in index[key]:
                index[key].append(rule)

    for rule, record in catalog["rules"].items():
        add(rule, rule)
        for key in record["stig_ids"] + record["vuln_ids"] + record["sv_ids"]:
            add(key, rule)
            if SV_ID_RE.match(key):
                add(re.sub(r"r\d+_rule$", "", key, flags=re.IGNORECASE), rule)
    return index


def resolve_controls(catalog, controls):
    """Resolve STIG IDs, V-IDs, SV-IDs, or SSG rule names to SSG rules.

    XCCDF drops a selected rule when a rule it ``requires`` is not selected, so
    the required rules are added to the selection. ``dependencies`` lists them
    so a caller can show (and protect-check) what was pulled in.

    :returns: dict with ``rules`` (sorted unique short ids, dependencies
        included), ``resolved`` (input -> rule list), ``unmatched`` (not in the
        data stream), ``not_in_profile`` (known rules the profile does not
        select) and ``dependencies`` (rule -> required rules added for it).
    """
    index = build_index(catalog)
    profile = set(catalog["profile_rules"])
    resolved = {}
    unmatched = []
    not_in_profile = []
    selected = []
    for raw in controls or []:
        control = (raw or "").strip()
        if not control:
            continue
        key = short_rule_id(control).lower()
        rules = index.get(key) or index.get(control.lower())
        if not rules:
            unmatched.append(control)
            continue
        in_profile = [rule for rule in rules if rule in profile]
        if not in_profile:
            not_in_profile.append(control)
            continue
        resolved[control] = in_profile
        for rule in in_profile:
            if rule not in selected:
                selected.append(rule)
    dependencies = {}
    queue = list(selected)
    while queue:
        rule = queue.pop(0)
        for required in (catalog["rules"].get(rule) or {}).get("requires", []):
            if required not in profile:
                continue
            if required not in selected:
                selected.append(required)
                queue.append(required)
            if required != rule and required not in dependencies.setdefault(rule, []):
                dependencies[rule].append(required)
    return {
        "rules": sorted(selected),
        "resolved": resolved,
        "unmatched": unmatched,
        "not_in_profile": not_in_profile,
        "dependencies": dependencies,
    }


def rule_label(catalog, rule):
    """Return ``STIG-ID (rule)`` when the STIG ID is known, else the rule."""
    record = catalog["rules"].get(rule) or {}
    stig = record.get("stig_ids") or []
    return "%s (%s)" % (stig[0], rule) if stig else rule


def build_tailoring(datastream_path, base_profile, base_profile_rules, selected_rules, profile_id=TAILORED_PROFILE):
    """Return XCCDF tailoring XML selecting only ``selected_rules``.

    Every other rule the base profile selects is deselected, so
    ``oscap xccdf eval --remediate`` can touch nothing else. The output has no
    run-dependent value, so reruns with the same inputs are byte-identical
    (idempotent).
    """
    ET.register_namespace("xccdf-1.2", XCCDF_NS)
    root = ET.Element(_q("Tailoring"), {"id": TAILORING_ID})
    ET.SubElement(root, _q("benchmark"), {"href": datastream_path})
    # The XCCDF schema requires ``time``. A fixed value keeps reruns identical.
    version = ET.SubElement(root, _q("version"), {"time": TAILORING_TIME})
    version.text = "1"
    profile = ET.SubElement(root, _q("Profile"), {"id": profile_id, "extends": base_profile})
    title = ET.SubElement(profile, _q("title"), {"override": "true"})
    title.text = "ADO selected STIG controls"
    description = ET.SubElement(profile, _q("description"), {"override": "true"})
    description.text = "Generated by infra.automation_development_office. Only the selected controls are active."
    keep = set(selected_rules)
    for rule in sorted(set(base_profile_rules) - keep):
        ET.SubElement(profile, _q("select"), {"idref": full_rule_id(rule), "selected": "false"})
    return "<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(root, encoding="unicode") + "\n"


def build_findings(catalog, results, selected_rules=None, compiled_patterns=None, include_not_selected=False):
    """Join OpenSCAP rule results with STIG metadata.

    When ``selected_rules`` is given, every selected rule must appear in the
    output. A selected rule OpenSCAP reported as ``notselected`` (or did not
    report at all) gets status ``not_evaluated`` so it can never be mistaken
    for a pass or silently ignored.

    :returns: tuple ``(findings, not_selected_count)`` sorted by STIG ID.
    """
    selected = set(selected_rules or [])
    rules = catalog["rules"] if catalog else {}
    findings = []
    not_selected = 0
    items = list(results)
    reported = {item["rule"] for item in items}
    for rule in sorted(selected - reported):
        items.append({"rule": rule, "result": "missing", "severity": "unknown"})
    for item in items:
        rule = item["rule"]
        if selected and rule not in selected:
            continue
        status = STATUS_MAP.get(item["result"], "error")
        if item["result"] == "missing":
            status = "not_evaluated"
        elif status == "not_selected":
            if selected:
                status = "not_evaluated"
            else:
                not_selected += 1
                if not include_not_selected:
                    continue
        record = rules.get(rule) or {}
        severity = record.get("severity") or item.get("severity") or "unknown"
        findings.append(
            {
                "rule": rule,
                "stig_id": (record.get("stig_ids") or [None])[0],
                "stig_ids": record.get("stig_ids", []),
                "vuln_id": (record.get("vuln_ids") or [None])[0],
                "sv_id": (record.get("sv_ids") or [None])[0],
                "srg_ids": record.get("srg_ids", []),
                "severity": severity,
                "category": SEVERITY_CAT.get(severity, "unknown"),
                "title": record.get("title", ""),
                "result": item["result"],
                "status": status,
                "remediated": item["result"] == "fixed",
                "protected": is_protected(rule, compiled_patterns) if compiled_patterns else False,
            }
        )
    findings.sort(key=lambda f: (f["stig_id"] or "~", f["rule"]))
    return findings, not_selected


def summarize(findings, not_selected, meta=None):
    """Return counts used by reports, job artifacts, and pass/fail gates."""
    counts = {"passed": 0, "failed": 0, "error": 0, "not_applicable": 0, "skipped": 0, "not_evaluated": 0}
    failed_by_category = {"CAT I": 0, "CAT II": 0, "CAT III": 0}
    fixed = 0
    for finding in findings:
        status = finding["status"]
        if status in counts:
            counts[status] += 1
        if finding["remediated"]:
            fixed += 1
        if status == "failed" and finding["category"] in failed_by_category:
            failed_by_category[finding["category"]] += 1
    assessed = counts["passed"] + counts["failed"] + counts["error"]
    summary = {
        "total": len(findings),
        "passed": counts["passed"],
        "failed": counts["failed"],
        "error": counts["error"],
        "not_applicable": counts["not_applicable"],
        "skipped": counts["skipped"],
        "not_evaluated": counts["not_evaluated"],
        "fixed": fixed,
        "not_selected": not_selected,
        "failed_by_category": failed_by_category,
        "compliance_percent": round(100.0 * counts["passed"] / assessed, 2) if assessed else None,
    }
    if meta:
        summary["scap_score"] = meta.get("scap_score")
    return summary


def failures(findings):
    """Return compact records for failed, errored, and not-evaluated controls."""
    return [
        {
            "stig_id": f["stig_id"],
            "vuln_id": f["vuln_id"],
            "rule": f["rule"],
            "category": f["category"],
            "status": f["status"],
            "title": f["title"],
        }
        for f in findings
        if f["status"] in ("failed", "error", "not_evaluated")
    ]
