# SPDX-License-Identifier: GPL-3.0-or-later
"""Self-service guard for the OpenShift Virtualization VM job template.

``ADO | Create VM - Self Service`` and the existing Advanced template run the same
playbook and the same ``ocp_virtualization`` role. In self-service mode the
playbook calls these filters on the values the role is about to use, so an
out-of-policy value fails the job whether it came from the survey, an extra
variable or anywhere else. Hiding a field in the survey is not the control.

The quota check is read-only and only proves a necessary condition: it never
says a VM will fit, only that it clearly does not.
"""

from __future__ import annotations

import re

_DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

_BINARY = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4, "Pi": 1024**5, "Ei": 1024**6}
_DECIMAL = {"k": 1000, "K": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4, "P": 1000**5, "E": 1000**6}
_QUANTITY = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]*)\s*$")

# ResourceQuota keys that bound guest memory, and keys that bound one VM or its disk.
_MEMORY_KEYS = ("requests.memory", "limits.memory", "memory")
_STORAGE_KEY = "requests.storage"
_PVC_KEY = "persistentvolumeclaims"
_VM_COUNT_KEY = "count/virtualmachines.kubevirt.io"


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def quantity_bytes(value):
    """Kubernetes quantity (``8Gi``, ``100M``, ``4096``) as a number, or ``None``."""
    match = _QUANTITY.match(_text(value))
    if not match:
        return None
    number, suffix = float(match.group(1)), match.group(2)
    if suffix == "":
        return number
    if suffix in _BINARY:
        return number * _BINARY[suffix]
    if suffix in _DECIMAL:
        return number * _DECIMAL[suffix]
    if suffix == "m":
        return number / 1000
    return None


def _by(items, key, wanted):
    for item in items or []:
        if isinstance(item, dict) and _text(item.get(key)) == _text(wanted):
            return item
    return {}


def self_service_violations(effective, policy):
    """Reasons the values the role would use are outside the approved policy.

    ``effective`` holds the final role-facing values plus ``size`` (the survey
    label). An empty list means the launch is allowed.
    """
    effective = effective if isinstance(effective, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    defaults = policy.get("defaults") if isinstance(policy.get("defaults"), dict) else {}
    images = policy.get("images") or []
    sizes = policy.get("sizes") or []
    namespaces = [_text(item) for item in policy.get("namespaces") or []]

    if not policy.get("enabled") or not images or not sizes or not namespaces:
        return [
            "The self-service policy is not configured. Enable it in the Preflight OpenShift Virt VM "
            "form (approved images, sizes and projects) and run Bootstrap again."
        ]

    problems = []
    name = _text(effective.get("vm_name"))
    if not name or len(name) > 63 or not _DNS_LABEL.match(name):
        problems.append(
            "VM name must be lowercase letters, numbers and hyphens, start and end with a letter or "
            "number, and be at most 63 characters."
        )

    namespace = _text(effective.get("vm_namespace"))
    if namespace not in namespaces:
        problems.append(f"Project '{namespace}' is not approved. Approved: {', '.join(namespaces)}.")

    image = _by(images, "id", effective.get("source_name"))
    if not image:
        problems.append(
            f"Operating system image '{_text(effective.get('source_name'))}' is not approved. "
            f"Approved: {', '.join(_text(i.get('id')) for i in images if isinstance(i, dict))}."
        )
    elif _text(effective.get("preference")) != _text(image.get("preference")):
        problems.append(
            f"Preference must be '{_text(image.get('preference'))}' for image '{_text(image.get('id'))}'."
        )
    if _text(effective.get("source_kind")) not in ("", "DataSource"):
        problems.append("Boot source must be a DataSource.")
    if _text(effective.get("source_namespace")) != _text(defaults.get("source_namespace")):
        problems.append("Boot image namespace does not match the approved default.")

    size = _by(sizes, "label", effective.get("size"))
    expected_type = _text(size.get("instance_type"))
    if not size or not expected_type:
        problems.append(
            f"Size '{_text(effective.get('size'))}' is not approved. "
            f"Approved: {', '.join(_text(s.get('label')) for s in sizes if isinstance(s, dict))}."
        )
    elif _text(effective.get("instance_type")) != expected_type:
        problems.append(
            f"Instance type must be '{expected_type}' for size '{_text(size.get('label'))}'. "
            "Custom CPU and memory is only available in the Advanced template."
        )

    for key, label in (
        ("storage_class", "Storage class"),
        ("network_mode", "Network mode"),
        ("multus_network_name", "Network attachment"),
        ("root_disk_size", "Root disk size"),
    ):
        if _text(effective.get(key)) != _text(defaults.get(key)):
            problems.append(f"{label} does not match the approved default.")

    # Login: approved user and key only. No passwords, no root SSH, hostname is the VM name.
    if _text(effective.get("cloud_user")) != _text(defaults.get("cloud_user") or "cloud-user"):
        problems.append("Login user does not match the approved default.")
    if _text(effective.get("ssh_public_key")) != _text(defaults.get("ssh_public_key")):
        problems.append("SSH public key does not match the approved default.")
    if _text(effective.get("cloud_user_password")) or _text(effective.get("root_password")):
        problems.append("Passwords cannot be set from Self Service. Use the Advanced template.")
    if str(effective.get("enable_root_ssh")).strip().lower() in ("1", "true", "yes", "on"):
        problems.append("Root SSH cannot be enabled from Self Service. Use the Advanced template.")
    if _text(effective.get("hostname")) != name:
        problems.append("Guest hostname must match the VM name.")

    if _text(effective.get("vm_state") or "present") != "present":
        problems.append("Self Service can only create VMs. Removal is not available from this template.")
    return problems


def _remaining(hard, used, key):
    limit = quantity_bytes((hard or {}).get(key))
    if limit is None:
        return None
    return limit - (quantity_bytes((used or {}).get(key)) or 0)


def quota_shortfalls(quotas, memory, disk):
    """Namespace quota limits a new VM clearly cannot fit under (read-only check).

    CPU is not checked: how many vCPUs a VM requests depends on the cluster's
    overcommit setting, so a safe comparison is not possible here.
    """
    guest = quantity_bytes(memory)
    root = quantity_bytes(disk)
    problems = []
    for quota in quotas or []:
        if not isinstance(quota, dict):
            continue
        quota_name = _text((quota.get("metadata") or {}).get("name")) or "quota"
        status = quota.get("status") or {}
        hard = status.get("hard") or (quota.get("spec") or {}).get("hard") or {}
        used = status.get("used") or {}
        for key in _MEMORY_KEYS:
            left = _remaining(hard, used, key)
            if left is not None and guest is not None and guest > left:
                problems.append(
                    f"Quota '{quota_name}' leaves {int(max(left, 0) // 1024**2)}Mi of {key}; "
                    f"this size needs at least {_text(memory)}."
                )
        left = _remaining(hard, used, _STORAGE_KEY)
        if left is not None and root is not None and root > left:
            problems.append(
                f"Quota '{quota_name}' leaves {int(max(left, 0) // 1024**3)}Gi of {_STORAGE_KEY}; "
                f"the root disk needs {_text(disk)}."
            )
        for key in (_PVC_KEY, _VM_COUNT_KEY):
            left = _remaining(hard, used, key)
            if left is not None and left < 1:
                problems.append(f"Quota '{quota_name}' has no room left for {key}.")
    return problems


class FilterModule:
    """Ansible filters for the self-service VM guard."""

    def filters(self):
        return {
            "ocp_virt_self_service_violations": self_service_violations,
            "ocp_virt_quota_shortfalls": quota_shortfalls,
        }
