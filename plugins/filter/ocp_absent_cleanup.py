# SPDX-License-Identifier: GPL-3.0-or-later
"""Namespace-deletion guards for ocp_namespace and ocp_absent_cleanup.

Ordinary namespace deletion must not select ClusterServiceVersions, copied
OLM CSVs, or workloads. Callers opt in with explicit authorize flags. The
built-in platform denylist always applies; extra names passed by a role are
additive and cannot shrink it.
"""

from __future__ import annotations

import re

_NS_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

# Control-plane and shared platform namespaces. Component namespaces such as
# openshift-gitops, cert-manager, and grafana are intentionally absent.
CONTROL_PLANE_NAMESPACES = frozenset(
    {
        "default",
        "kube-node-lease",
        "kube-public",
        "kube-system",
        "openshift",
        "openshift-apiserver",
        "openshift-authentication",
        "openshift-cloud-credential-operator",
        "openshift-cluster-csi-drivers",
        "openshift-cluster-machine-approver",
        "openshift-cluster-node-tuning-operator",
        "openshift-cluster-samples-operator",
        "openshift-cluster-storage-operator",
        "openshift-cluster-version",
        "openshift-config",
        "openshift-config-managed",
        "openshift-console",
        "openshift-controller-manager",
        "openshift-dns",
        "openshift-etcd",
        "openshift-host-network",
        "openshift-image-registry",
        "openshift-infra",
        "openshift-ingress",
        "openshift-ingress-canary",
        "openshift-insights",
        "openshift-kube-apiserver",
        "openshift-kube-controller-manager",
        "openshift-kube-scheduler",
        "openshift-kube-storage-version-migrator",
        "openshift-machine-api",
        "openshift-machine-config-operator",
        "openshift-marketplace",
        "openshift-monitoring",
        "openshift-multus",
        "openshift-network-diagnostics",
        "openshift-network-operator",
        "openshift-node",
        "openshift-oauth-apiserver",
        "openshift-operator-lifecycle-manager",
        "openshift-ovn-kubernetes",
        "openshift-route-controller-manager",
        "openshift-service-ca",
        "openshift-user-workload-monitoring",
    }
)

# Deleting this namespace removes every all-namespaces operator. Matched CSV
# cleanup inside it is still allowed; namespace deletion is not.
SHARED_OPERATORS_NAMESPACE = "openshift-operators"

DEFAULT_PREFIXES = ("kube-",)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _name(value) -> str:
    return str(value or "").strip()


def namespace_name_valid(name) -> bool:
    """True when name is one DNS-1123 label and contains no list or wildcard."""
    text = "" if name is None else str(name)
    if text != text.strip():
        return False
    if not text or len(text) > 63:
        return False
    return _NS_RE.fullmatch(text) is not None


def _prefixes(extra) -> tuple:
    found = list(DEFAULT_PREFIXES)
    for item in extra or []:
        text = _name(item).lower()
        if text and text not in found:
            found.append(text)
    return tuple(found)


def _hard_blocked(name, extra_blocked=None, extra_prefixes=None) -> bool:
    text = _name(name).lower()
    if not text:
        return True
    blocked = set(CONTROL_PLANE_NAMESPACES)
    for item in extra_blocked or []:
        extra = _name(item).lower()
        if extra:
            blocked.add(extra)
    if text in blocked:
        return True
    return any(text.startswith(prefix) for prefix in _prefixes(extra_prefixes))


def namespace_delete_blocked(name, extra_blocked=None, extra_prefixes=None) -> bool:
    """True when ocp_namespace must refuse to delete this namespace."""
    if not namespace_name_valid(name):
        return True
    if _hard_blocked(name, extra_blocked, extra_prefixes):
        return True
    return _name(name).lower() == SHARED_OPERATORS_NAMESPACE


def _guard_value(guard, key, default=False):
    if not isinstance(guard, dict):
        return default
    return guard.get(key, default)


def cleanup_refused(name, guard=None) -> bool:
    """True when ocp_absent_cleanup must not touch this namespace.

    ``guard`` keys: mode, sweep_olm, csv_name_match,
    authorize_unfiltered_csv_delete, delete_copied_csvs, sweep_workloads,
    authorize_unfiltered_workloads, extra_blocked, extra_prefixes.
    """
    guard = guard or {}
    extra_blocked = _guard_value(guard, "extra_blocked", [])
    extra_prefixes = _guard_value(guard, "extra_prefixes", [])
    if _hard_blocked(name, extra_blocked, extra_prefixes):
        return True
    if _name(name).lower() != SHARED_OPERATORS_NAMESPACE:
        return False
    mode = _name(_guard_value(guard, "mode", "cleanup")) or "cleanup"
    if mode == "check":
        return False
    if _as_bool(_guard_value(guard, "sweep_workloads", False)):
        return True
    if _as_bool(_guard_value(guard, "authorize_unfiltered_workloads", False)):
        return True
    if _as_bool(_guard_value(guard, "authorize_unfiltered_csv_delete", False)):
        return True
    if _as_bool(_guard_value(guard, "delete_copied_csvs", False)):
        return True
    if _as_bool(_guard_value(guard, "sweep_olm", False)) and not _name(
        _guard_value(guard, "csv_name_match", "")
    ):
        return True
    return False


def _metadata(resource) -> dict:
    if not isinstance(resource, dict):
        return {}
    meta = resource.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _in_namespace(resource, namespace) -> bool:
    meta = _metadata(resource)
    resource_ns = _name(meta.get("namespace"))
    if not resource_ns:
        return True
    return resource_ns == namespace


def is_olm_copy(resource, namespace) -> bool:
    """True for an OLM-copied CSV, not the operator's own CSV.

    OpenShift copies all-namespaces CSVs into every namespace. The copy carries
    label ``olm.copiedFrom`` and/or annotation ``olm.operatorNamespace`` pointing
    at the operator namespace. The annotation ``olm.copiedFrom`` is often unset.
    """
    meta = _metadata(resource)
    labels = meta.get("labels") or {}
    annotations = meta.get("annotations") or {}
    if not isinstance(labels, dict):
        labels = {}
    if not isinstance(annotations, dict):
        annotations = {}
    copied = _name(labels.get("olm.copiedFrom") or annotations.get("olm.copiedFrom"))
    if copied:
        return True
    owner = _name(annotations.get("olm.operatorNamespace"))
    return bool(owner) and owner != namespace


def csv_name_matches(csv_name, match) -> bool:
    """True for an exact CSV name or an OLM ``<package>.<version>`` name.

    ``cert-manager-operator`` matches ``cert-manager-operator.v1.20.1``.
    It does not match ``cert-manager-operator-extra.v1`` or a name that merely
    contains the token, such as ``openshift-gitops-operator.v1.21.1`` for
    ``operator``.
    """
    name = _name(csv_name)
    token = _name(match)
    if not name or not token:
        return False
    if name == token:
        return True
    return name.startswith(token + ".")


def select_csvs(
    csvs,
    namespace,
    csv_name_match="",
    authorize_csv_delete=False,
    authorize_unfiltered_csv_delete=False,
    delete_copied_csvs=False,
):
    """Return CSVs in ``namespace`` that this run may delete. Default is none."""
    target = _name(namespace)
    if not namespace_name_valid(target):
        return []
    if not _as_bool(authorize_csv_delete):
        return []
    match = _name(csv_name_match)
    if not match and not _as_bool(authorize_unfiltered_csv_delete):
        return []
    allow_copies = _as_bool(delete_copied_csvs)
    selected = []
    for item in csvs or []:
        meta = _metadata(item)
        csv_name = _name(meta.get("name"))
        if not csv_name or not _in_namespace(item, target):
            continue
        if match and not csv_name_matches(csv_name, match):
            continue
        if is_olm_copy(item, target) and not allow_copies:
            continue
        selected.append(item)
    return selected


def select_installplans(
    plans,
    namespace,
    csv_name_match="",
    authorize_csv_delete=False,
    authorize_unfiltered_csv_delete=False,
):
    """Return InstallPlans in ``namespace`` that this run may delete."""
    target = _name(namespace)
    if not namespace_name_valid(target):
        return []
    if not _as_bool(authorize_csv_delete):
        return []
    match = _name(csv_name_match)
    if not match and not _as_bool(authorize_unfiltered_csv_delete):
        return []
    selected = []
    for item in plans or []:
        meta = _metadata(item)
        plan_name = _name(meta.get("name"))
        if not plan_name or not _in_namespace(item, target):
            continue
        if match:
            spec = item.get("spec") if isinstance(item, dict) else {}
            if not isinstance(spec, dict):
                spec = {}
            csv_names = [str(name) for name in (spec.get("clusterServiceVersionNames") or [])]
            if not csv_names or not all(csv_name_matches(name, match) for name in csv_names):
                continue
        selected.append(item)
    return selected


def select_workloads(resources, namespace, names=None, authorize_unfiltered=False):
    """Return workloads in ``namespace`` that this run may delete.

    An empty name list deletes nothing unless ``authorize_unfiltered`` is true.
    Objects whose metadata.namespace is some other namespace are never returned.
    """
    target = _name(namespace)
    if not namespace_name_valid(target):
        return []
    allow = [_name(item) for item in (names or []) if _name(item)]
    if not allow and not _as_bool(authorize_unfiltered):
        return []
    selected = []
    for item in resources or []:
        meta = _metadata(item)
        resource_name = _name(meta.get("name"))
        if not resource_name or not _in_namespace(item, target):
            continue
        if allow and resource_name not in allow:
            continue
        selected.append(item)
    return selected


class FilterModule:
    """Ansible filters for safe namespace cleanup selection."""

    def filters(self):
        return {
            "ocp_absent_cleanup_namespace_name_valid": namespace_name_valid,
            "ocp_absent_cleanup_namespace_delete_blocked": namespace_delete_blocked,
            "ocp_absent_cleanup_cleanup_refused": cleanup_refused,
            "ocp_absent_cleanup_is_olm_copy": is_olm_copy,
            "ocp_absent_cleanup_csv_name_matches": csv_name_matches,
            "ocp_absent_cleanup_select_csvs": select_csvs,
            "ocp_absent_cleanup_select_installplans": select_installplans,
            "ocp_absent_cleanup_select_workloads": select_workloads,
        }
