#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the infra.automation_development_office collection
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Turn OpenSCAP results into structured STIG findings."""

from __future__ import absolute_import, division, print_function


__metaclass__ = type


DOCUMENTATION = r"""
---
module: rhel_stig_cac_report
version_added: 2.2.0
short_description: Build structured STIG findings from OpenSCAP results
description:
  - Parses the XCCDF results file written by C(oscap xccdf eval --results).
  - Joins each rule result with its STIG ID, vulnerability ID, rule ID, SRG,
    and CAT severity from the SCAP Security Guide data stream.
  - Writes a machine-readable findings file and returns a summary. The summary
    is what the role uses to pass or fail a run, so a failed control is never
    hidden behind a successful C(oscap) exit code.
  - When O(selected_rules) is set, every selected rule appears in the output.
    A selected rule OpenSCAP did not evaluate has status C(not_evaluated).
  - Never modifies the system other than writing O(findings_dest).
options:
  results_path:
    description:
      - XCCDF results file written by C(oscap xccdf eval --results).
    type: path
    required: true
  datastream:
    description:
      - SSG data stream used for the scan. Supplies STIG metadata.
    type: path
  profile:
    description:
      - Base profile ID in O(datastream).
    type: str
    default: xccdf_org.ssgproject.content_profile_stig
  selected_rules:
    description:
      - SSG rule names that were selected for the scan. This is the C(rules)
        value returned by M(infra.automation_development_office.rhel_stig_cac_resolve).
      - When empty, all evaluated rules are reported.
    type: list
    elements: str
    default: []
  protected_patterns:
    description:
      - Regular expressions marking a rule as protected in the findings.
    type: list
    elements: str
    default: []
  include_not_selected:
    description:
      - Include rules the profile did not select (large output).
    type: bool
    default: false
  return_findings:
    description:
      - Return the full findings list in RV(findings). The findings file always
        has them; leave this off to keep job output small.
    type: bool
    default: false
  context:
    description:
      - Free-form values copied into the findings file, such as C(mode) and C(host).
      - Must not contain secrets.
    type: dict
    default: {}
  findings_dest:
    description:
      - Where to write the findings JSON file.
    type: path
  findings_mode:
    description:
      - File mode for O(findings_dest).
    type: str
    default: "0640"
author:
  - Automation Development Office (@Automation-Development-Office)
"""

EXAMPLES = r"""
- name: Build findings from an audit
  infra.automation_development_office.rhel_stig_cac_report:
    results_path: /var/lib/ado/stig/audit-results.xml
    datastream: /usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml
    context:
      mode: audit
    findings_dest: /var/lib/ado/stig/audit-findings.json
  register: stig_report
"""

RETURN = r"""
summary:
  description: Counts, failures by CAT, and compliance percentage.
  returned: always
  type: dict
failures:
  description: Failed, errored, and not-evaluated controls.
  returned: always
  type: list
  elements: dict
findings:
  description: Every reported control with STIG metadata and status.
  returned: when O(return_findings=true)
  type: list
  elements: dict
scan:
  description: Scan metadata from the results file (profile, target, times, score).
  returned: always
  type: dict
findings_path:
  description: Path of the findings file written.
  returned: when O(findings_dest) is set
  type: str
"""

import json
import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.infra.automation_development_office.plugins.module_utils import rhel_stig_cac as stig


def _write_if_changed(module, path, content, mode):
    existing = None
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    changed = existing != content
    if changed and not module.check_mode:
        directory = os.path.dirname(path) or "."
        if not os.path.isdir(directory):
            os.makedirs(directory)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(tmp_path, int(mode, 8))
        os.replace(tmp_path, path)
    return changed


def main():
    module = AnsibleModule(
        argument_spec={
            "results_path": {"type": "path", "required": True},
            "datastream": {"type": "path"},
            "profile": {"type": "str", "default": stig.DEFAULT_PROFILE},
            "selected_rules": {"type": "list", "elements": "str", "default": []},
            "protected_patterns": {"type": "list", "elements": "str", "default": []},
            "include_not_selected": {"type": "bool", "default": False},
            "return_findings": {"type": "bool", "default": False},
            "context": {"type": "dict", "default": {}},
            "findings_dest": {"type": "path"},
            "findings_mode": {"type": "str", "default": "0640"},
        },
        supports_check_mode=True,
    )
    params = module.params
    if not os.path.isfile(params["results_path"]):
        module.fail_json(msg="OpenSCAP results file not found: %s" % params["results_path"])
    try:
        compiled = stig.compile_patterns(params["protected_patterns"])
        meta, results = stig.parse_results(params["results_path"])
        catalog = None
        if params["datastream"]:
            catalog = stig.load_catalog(params["datastream"], params["profile"])
    except ValueError as exc:
        module.fail_json(msg=str(exc))
    except Exception as exc:  # xml.etree.ElementTree.ParseError and similar
        module.fail_json(msg="Cannot parse SCAP content: %s" % exc)

    findings, not_selected = stig.build_findings(
        catalog,
        results,
        params["selected_rules"],
        compiled,
        params["include_not_selected"],
    )
    summary = stig.summarize(findings, not_selected, meta)
    document = {
        "schema": stig.FINDINGS_SCHEMA,
        "context": params["context"],
        "benchmark_version": (catalog or {}).get("benchmark_version"),
        "scan": meta,
        "summary": summary,
        "findings": findings,
    }
    result = {
        "changed": False,
        "summary": summary,
        "failures": stig.failures(findings),
        "scan": meta,
    }
    if params["return_findings"]:
        result["findings"] = findings
    if params["findings_dest"]:
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
        result["changed"] = _write_if_changed(
            module, params["findings_dest"], content, params["findings_mode"]
        )
        result["findings_path"] = params["findings_dest"]
    module.exit_json(**result)


if __name__ == "__main__":
    main()
