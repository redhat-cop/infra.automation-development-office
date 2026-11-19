#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the infra.automation_development_office collection
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Resolve STIG controls against a SCAP Security Guide data stream."""

from __future__ import absolute_import, division, print_function


__metaclass__ = type


DOCUMENTATION = r"""
---
module: rhel_stig_cac_resolve
version_added: 2.2.0
short_description: Resolve STIG controls to SCAP rules and write an OpenSCAP tailoring file
description:
  - Reads a SCAP Security Guide (SSG) data stream installed on the managed host.
  - Resolves STIG IDs (C(RHEL-09-255100)), vulnerability IDs (C(V-257996)),
    rule IDs (C(SV-257996r1134915_rule)), or SSG rule names to SSG rules that
    the STIG profile selects.
  - Adds rules that a selected rule C(requires), because XCCDF silently drops a
    rule whose requirement is not selected.
  - Reports which resolved rules match a protected-control pattern and were not
    explicitly allowed. The module never decides to proceed; the role does.
  - When O(controls) is set and O(tailoring_dest) is given, writes an XCCDF
    tailoring file that selects only the resolved rules. Running OpenSCAP with
    that file and C(--remediate) cannot touch any other control.
  - Never modifies the system other than writing O(tailoring_dest).
options:
  datastream:
    description:
      - Path to the SSG data stream on the managed host.
    type: path
    required: true
  profile:
    description:
      - XCCDF profile ID that defines the available controls.
    type: str
    default: xccdf_org.ssgproject.content_profile_stig
  controls:
    description:
      - STIG IDs, vulnerability IDs, rule IDs, or SSG rule names to select.
      - When empty, nothing is resolved and no tailoring file is written.
    type: list
    elements: str
    default: []
  protected_patterns:
    description:
      - Regular expressions matched against SSG rule names. A resolved rule
        that matches is reported in RV(blocked_protected) unless it is listed
        in O(allow_protected).
    type: list
    elements: str
    default: []
  allow_protected:
    description:
      - Controls (same formats as O(controls)) that may bypass
        O(protected_patterns).
    type: list
    elements: str
    default: []
  tailoring_dest:
    description:
      - Where to write the tailoring file. Written only when O(controls) is set.
    type: path
  tailoring_mode:
    description:
      - File mode for O(tailoring_dest).
    type: str
    default: "0640"
author:
  - Automation Development Office (@Automation-Development-Office)
"""

EXAMPLES = r"""
- name: Resolve two controls and write a tailoring file
  infra.automation_development_office.rhel_stig_cac_resolve:
    datastream: /usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml
    controls:
      - RHEL-09-255100
      - V-258083
    protected_patterns:
      - ^sshd_
    tailoring_dest: /var/lib/ado/stig/tailoring.xml
  register: stig_resolved
"""

RETURN = r"""
rules:
  description: Sorted SSG rule names selected, including required rules.
  returned: always
  type: list
  elements: str
resolved:
  description: Each input control mapped to the SSG rules it selects.
  returned: always
  type: dict
unmatched:
  description: Controls that are not in the data stream.
  returned: always
  type: list
  elements: str
not_in_profile:
  description: Controls known to the data stream that the profile does not select.
  returned: always
  type: list
  elements: str
dependencies:
  description: Rules added because another selected rule requires them.
  returned: always
  type: dict
blocked_protected:
  description: Selected rules that match a protected pattern and were not allowed.
  returned: always
  type: list
  elements: str
profile_found:
  description: Whether O(profile) exists in the data stream.
  returned: always
  type: bool
profile_rule_count:
  description: Number of rules the profile selects.
  returned: always
  type: int
benchmark_version:
  description: SSG benchmark version, for example C(0.1.82).
  returned: always
  type: str
tailoring_path:
  description: Path of the tailoring file written.
  returned: when a tailoring file was requested
  type: str
"""

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.infra.automation_development_office.plugins.module_utils import rhel_stig_cac as stig


def _write_if_changed(module, path, content, mode):
    """Write content atomically when it differs. Return True when changed."""
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
            "datastream": {"type": "path", "required": True},
            "profile": {"type": "str", "default": stig.DEFAULT_PROFILE},
            "controls": {"type": "list", "elements": "str", "default": []},
            "protected_patterns": {"type": "list", "elements": "str", "default": []},
            "allow_protected": {"type": "list", "elements": "str", "default": []},
            "tailoring_dest": {"type": "path"},
            "tailoring_mode": {"type": "str", "default": "0640"},
        },
        supports_check_mode=True,
    )
    params = module.params
    datastream = params["datastream"]
    if not os.path.isfile(datastream):
        module.fail_json(msg="SCAP data stream not found: %s" % datastream)
    try:
        compiled = stig.compile_patterns(params["protected_patterns"])
        catalog = stig.load_catalog(datastream, params["profile"])
    except (ValueError, OSError) as exc:
        module.fail_json(msg=str(exc))
    except Exception as exc:  # xml.etree.ElementTree.ParseError and similar
        module.fail_json(msg="Cannot read SCAP data stream %s: %s" % (datastream, exc))
    if not catalog["profile_found"]:
        module.fail_json(msg="Profile %s is not in %s" % (params["profile"], datastream))

    result = {
        "changed": False,
        "rules": [],
        "resolved": {},
        "unmatched": [],
        "not_in_profile": [],
        "dependencies": {},
        "blocked_protected": [],
        "profile_found": True,
        "profile_rule_count": len(catalog["profile_rules"]),
        "benchmark_version": catalog["benchmark_version"] or "",
    }
    if params["controls"]:
        resolution = stig.resolve_controls(catalog, params["controls"])
        allowed = set(stig.resolve_controls(catalog, params["allow_protected"])["rules"])
        result.update(
            {
                "rules": resolution["rules"],
                "resolved": resolution["resolved"],
                "unmatched": resolution["unmatched"],
                "not_in_profile": resolution["not_in_profile"],
                "dependencies": resolution["dependencies"],
                "blocked_protected": [
                    rule
                    for rule in resolution["rules"]
                    if stig.is_protected(rule, compiled) and rule not in allowed
                ],
            }
        )
        if params["tailoring_dest"] and resolution["rules"]:
            content = stig.build_tailoring(
                datastream,
                params["profile"],
                catalog["profile_rules"],
                resolution["rules"],
            )
            result["changed"] = _write_if_changed(
                module, params["tailoring_dest"], content, params["tailoring_mode"]
            )
            result["tailoring_path"] = params["tailoring_dest"]
    module.exit_json(**result)


if __name__ == "__main__":
    main()
