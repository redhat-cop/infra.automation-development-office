import sys
import json
import csv
import re
import os
from datetime import datetime, timezone
from collections import defaultdict

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

MODE = sys.argv[1]
FILTER_COMPONENT = sys.argv[2].strip().lower()
OUTDIR = sys.argv[3]
ALL_SCOPE = sys.argv[4] == "1"
RHSRE = sys.argv[5] == "1"
SHOW_SEV = sys.argv[6] == "1"
# Comma-separated cluster names. Empty = all clusters.
_raw_clusters = sys.argv[7].strip() if len(sys.argv) > 7 else ""
CLUSTER_FILTER = {
    c.strip()
    for c in _raw_clusters.split(",")
    if c.strip()
}
_input_path = sys.argv[8].strip() if len(sys.argv) > 8 else ""

# ============================================================
# COMPONENT DEFINITIONS
# ============================================================

ORDER = [
    "ACM / MCE",
    "Dev Spaces",
    "cert-manager",
    "Web Terminal",
    "GitOps",
    "Compliance",
    "Kube Descheduler",
    "Cluster Logging",
    "RHACS",
]

ALIASES = {
    "acm": "ACM / MCE",
    "acm/mce": "ACM / MCE",
    "mce": "ACM / MCE",

    "devspaces": "Dev Spaces",
    "dev-spaces": "Dev Spaces",

    "cert-manager": "cert-manager",
    "certmanager": "cert-manager",

    "web-terminal": "Web Terminal",
    "webterminal": "Web Terminal",

    "gitops": "GitOps",

    "compliance": "Compliance",

    "kube-descheduler": "Kube Descheduler",
    "descheduler": "Kube Descheduler",

    "cluster-logging": "Cluster Logging",
    "logging": "Cluster Logging",

    "rhacs": "RHACS",
    "acs": "RHACS",
}

# Strict ACM/MCE namespace ownership.
ACM_NAMESPACES = {
    "multicluster-engine",
    "open-cluster-management",
    "open-cluster-management-agent",
    "open-cluster-management-agent-addon",
    "open-cluster-management-hub",
}

# ============================================================
# HELPERS
# ============================================================


def strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)
    elif isinstance(obj, str):
        yield obj


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)

    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def first_value(obj, keys):
    if not isinstance(obj, dict):
        return ""

    for key in keys:
        v = obj.get(key)

        if isinstance(v, str) and v:
            return v

    return ""


def deployment_info(result):
    d = result.get("deployment") or {}

    namespace = ""
    deployment = ""
    cluster = ""

    if isinstance(d, dict):

        namespace = first_value(
            d,
            [
                "namespace",
                "namespaceName",
            ]
        )

        deployment = first_value(
            d,
            [
                "name",
                "deploymentName",
            ]
        )

        cluster = first_value(
            d,
            [
                "cluster",
                "clusterName",
            ]
        )

        # Look slightly deeper without doing fuzzy global matching.
        if not namespace:
            for x in walk(d):
                namespace = first_value(
                    x,
                    ["namespace", "namespaceName"]
                )
                if namespace:
                    break

        if not deployment:
            for x in walk(d):
                deployment = first_value(
                    x,
                    ["deploymentName", "name"]
                )
                if deployment:
                    break

        if not cluster:
            for x in walk(d):
                cluster = first_value(
                    x,
                    ["clusterName", "cluster"]
                )
                if cluster:
                    break

    return cluster, namespace, deployment


def image_identity(image):
    refs = []
    digests = []

    for s in strings(image):

        low = s.lower()

        if (
            "/" in s
            and (
                "registry." in low
                or "docker.io/" in low
                or "quay.io/" in low
                or "sha256:" in low
            )
        ):
            refs.append(s)

        if "sha256:" in low:
            m = re.search(r"sha256:[a-f0-9]{32,64}", low)
            if m:
                digests.append(m.group(0))

    ref = refs[0] if refs else ""

    digest = digests[0] if digests else ""

    # Fall back to common fields.
    if not ref and isinstance(image, dict):
        for key in ("name", "fullName", "image"):
            v = image.get(key)
            if isinstance(v, str):
                ref = v
                break

    if not digest and isinstance(image, dict):
        for key in ("digest", "hash", "id"):
            v = image.get(key)
            if isinstance(v, str) and "sha256:" in v:
                digest = v
                break

    return ref, digest


def classify(namespace, image_text, deployment):
    ns = (namespace or "").lower()
    text = " ".join([
        image_text or "",
        deployment or "",
    ]).lower()

    # --------------------------------------------------------
    # ACM/MCE — STRICT namespace matching only.
    # --------------------------------------------------------

    if ns in ACM_NAMESPACES:
        return "ACM / MCE"

    # --------------------------------------------------------
    # Web Terminal before Dev Spaces because Web Terminal
    # objects can live in openshift-operators.
    # --------------------------------------------------------

    if (
        ns == "openshift-terminal"
        or "web-terminal" in text
    ):
        return "Web Terminal"

    # --------------------------------------------------------
    # Dev Spaces
    # --------------------------------------------------------

    if (
        ns == "openshift-devspaces"
        or ns.endswith("-devspaces")
        or "/devspaces/" in text
        or "/devworkspace/" in text
        or "devworkspace-rhel" in text
        or "udi-rhel" in text
    ):
        return "Dev Spaces"

    # --------------------------------------------------------
    # cert-manager
    # --------------------------------------------------------

    if (
        ns in {
            "cert-manager",
            "cert-manager-operator",
        }
        or "cert-manager" in text
        or "certmanager" in text
    ):
        return "cert-manager"

    # --------------------------------------------------------
    # GitOps
    # --------------------------------------------------------

    if (
        ns == "openshift-gitops"
        or "gitops" in text
        or "argocd" in text
    ):
        return "GitOps"

    # --------------------------------------------------------
    # Compliance
    # --------------------------------------------------------

    if (
        ns == "compliance"
        or "/compliance/" in text
        or "openshift-compliance" in text
        or "openscap" in text
    ):
        return "Compliance"

    # --------------------------------------------------------
    # Kube Descheduler
    # --------------------------------------------------------

    if (
        ns in {
            "openshift-kube-descheduler-operator",
            "openshift-kube-descheduler",
        }
        or "descheduler" in text
    ):
        return "Kube Descheduler"

    # --------------------------------------------------------
    # Cluster Logging
    # --------------------------------------------------------

    if (
        ns == "openshift-logging"
        or "cluster-logging" in text
        or "logging-rhel" in text
        or "loki-operator" in text
        or "lokistack" in text
    ):
        return "Cluster Logging"

    # --------------------------------------------------------
    # RHACS
    # --------------------------------------------------------

    if (
        ns in {
            "stackrox",
            "rhacs-operator",
        }
        or "stackrox" in text
        or "/rhacs/" in text
    ):
        return "RHACS"

    return None

# ============================================================
# EXTENDED REPORT GROUPING
# ============================================================


ALL_GROUP_ORDER = [
    "ACM / MCE",
    "Dev Spaces",
    "cert-manager",
    "Web Terminal",
    "GitOps",
    "Compliance",
    "Kube Descheduler",
    "Cluster Logging",
    "RHACS",
    "Grafana",
    "Kafka",
    "Elasticsearch",
    "External Secrets",
    "Keycloak",
    "Quay",
    "AAP",
    "OpenTelemetry",
    "Pipelines",
    "Service Mesh",
    "Serverless",
    "OpenShift AI",
    "Storage",
    "Virtualization",
    "ROE",
    "OpenShift Platform",
    "Customer Apps",
    "Other",
]

RHSRE_GROUP_ORDER = [
    "Control Plane",
    "Networking / Ingress",
    "Authentication / OAuth",
    "Monitoring",
    "Machine / Nodes",
    "Storage / CSI",
    "Console / Registry",
    "OLM / Marketplace",
    "OpenShift Platform",
]

# Optional/customer-installed products. Even though many are Red Hat
# products, they are NOT automatically ROSA SRE responsibility.
RHSRE_EXCLUDED_NAMESPACES = {
    "openshift-devspaces",
    "openshift-terminal",
    "openshift-gitops",
    "openshift-gitops-operator",
    "openshift-logging",
    "openshift-operators",
    "openshift-cert-manager",
    "openshift-cert-manager-operator",
    "openshift-kube-descheduler-operator",
    "compliance",
    "stackrox",
    "rhacs-operator",
    "multicluster-engine",
    "open-cluster-management",
    "advanced-cluster-management",
    "grafana",
    "keycloak",
    "quay",
    "aap",
}

RHSRE_EXCLUDED_PREFIXES = (
    "open-cluster-management",
    "ceelliott-devspaces",
)


def classify_all(namespace, image_text, deployment):
    """
    Group ALL findings into useful product buckets rather than
    printing hundreds of individual namespaces.
    """

    # Keep all of the hand-tuned existing Red Hat groups first.
    existing = classify(namespace, image_text, deployment)

    if existing:
        return existing

    ns = (namespace or "").lower()
    text = " ".join([
        namespace or "",
        image_text or "",
        deployment or "",
    ]).lower()

    if (
        ns == "grafana"
        or "/grafana/" in text
        or "grafana/grafana" in text
        or "grafana-operator" in text
    ):
        return "Grafana"

    if (
        "kafka" in ns
        or "kafka" in text
        or "strimzi" in text
    ):
        return "Kafka"

    if (
        "elastic" in ns
        or "elasticsearch" in text
        or "elastic-" in text
        or "/elastic/" in text
    ):
        return "Elasticsearch"

    if (
        "external-secret" in ns
        or "external-secret" in text
        or "external_secrets" in text
    ):
        return "External Secrets"

    if (
        "keycloak" in ns
        or "keycloak" in text
        or "rhbk" in text
    ):
        return "Keycloak"

    if (
        ns.startswith("quay")
        or "/quay/" in text
        or "quay-operator" in text
    ):
        return "Quay"

    if (
        ns.startswith("aap")
        or "automation-controller" in text
        or "automation-platform" in text
        or "ansible-automation-platform" in text
    ):
        return "AAP"

    if (
        "opentelemetry" in ns
        or "opentelemetry" in text
        or "otel-" in text
    ):
        return "OpenTelemetry"

    if (
        "pipelines" in ns
        or "tekton" in text
        or "openshift-pipelines" in text
    ):
        return "Pipelines"

    if (
        "maistra" in text
        or "servicemesh" in text
        or "service-mesh" in text
        or "istio" in text
    ):
        return "Service Mesh"

    if (
        "serverless" in ns
        or "knative" in text
        or "serverless" in text
    ):
        return "Serverless"

    if (
        "redhat-ods" in ns
        or "openshift-ai" in text
        or "rhods" in text
    ):
        return "OpenShift AI"

    if (
        "odf" in ns
        or "ocs-" in ns
        or "lvm" in text
        or "local-storage" in text
        or "odf-" in text
    ):
        return "Storage"

    if (
        "virtualization" in text
        or "kubevirt" in text
        or "cnv-" in text
    ):
        return "Virtualization"

    if (
        ns.startswith("roe-")
        or "/roe-" in text
        or "roe-" in deployment.lower()
    ):
        return "ROE"

    if ns.startswith("openshift-") or ns in {
        "kube-system",
        "kube-public",
        "kube-node-lease",
        "default",
    }:
        return "OpenShift Platform"

    # Known application/customer workload namespaces land here instead
    # of being mixed with core OpenShift.
    if ns:
        return "Customer Apps"

    return "Other"


def is_rhsre(namespace, image_text, deployment):
    """
    Approximate the ROSA managed-service / Red Hat SRE responsibility
    boundary using core OpenShift platform namespaces.

    Customer-installed optional operators are explicitly excluded.
    """

    ns = (namespace or "").lower()

    if not ns:
        return False

    if ns in RHSRE_EXCLUDED_NAMESPACES:
        return False

    if any(ns.startswith(x) for x in RHSRE_EXCLUDED_PREFIXES):
        return False

    # Core Kubernetes/OpenShift service namespaces.
    if ns == "kube-system":
        return True

    if not ns.startswith("openshift-"):
        return False

    # Additional optional/customer-controlled namespaces we do not want
    # swept into SRE ownership merely because they start with openshift-.
    optional_markers = (
        "devspaces",
        "gitops",
        "terminal",
        "logging",
        "compliance",
        "cert-manager",
        "descheduler",
        "serverless",
        "pipelines",
        "operators",
        "service-mesh",
        "maistra",
    )

    if any(x in ns for x in optional_markers):
        return False

    return True


def classify_rhsre(namespace, image_text, deployment):
    ns = (namespace or "").lower()
    text = " ".join([
        namespace or "",
        image_text or "",
        deployment or "",
    ]).lower()

    if any(x in ns for x in (
        "kube-apiserver",
        "kube-controller-manager",
        "kube-scheduler",
        "etcd",
        "controller-manager",
        "apiserver",
    )):
        return "Control Plane"

    if any(x in ns for x in (
        "network",
        "ingress",
        "dns",
        "multus",
    )) or any(x in text for x in (
        "ovn-kubernetes",
        "router",
    )):
        return "Networking / Ingress"

    if any(x in ns for x in (
        "authentication",
        "oauth",
    )):
        return "Authentication / OAuth"

    if "monitoring" in ns or "monitoring" in text:
        return "Monitoring"

    if any(x in ns for x in (
        "machine-api",
        "machine-config",
        "cluster-node-tuning",
        "cluster-machine-approver",
    )):
        return "Machine / Nodes"

    if any(x in ns for x in (
        "cluster-storage",
        "cluster-csi",
        "csi-driver",
    )):
        return "Storage / CSI"

    if any(x in ns for x in (
        "console",
        "image-registry",
    )):
        return "Console / Registry"

    if any(x in ns for x in (
        "operator-lifecycle-manager",
        "marketplace",
    )):
        return "OLM / Marketplace"

    return "OpenShift Platform"


def severity_name(v):
    s = str(v.get("severity") or "").upper()

    if "CRITICAL" in s:
        return "Critical"

    if "IMPORTANT" in s or s == "HIGH":
        return "Important"

    if "MODERATE" in s or s == "MEDIUM":
        return "Moderate"

    if "LOW" in s:
        return "Low"

    return "Unknown"


def high_enough(v):
    return severity_name(v) in {
        "Critical",
        "Important",
    }


def vulnerability_sources(v):
    result = set()

    metrics = v.get("cvssMetrics") or []

    if isinstance(metrics, list):
        for m in metrics:
            if not isinstance(m, dict):
                continue

            src = str(m.get("source") or "").strip()

            if src:
                result.add(src)

    if not result:
        result.add("NO_CVSS_SOURCE")

    return result


def redhat_source(v):
    link = str(v.get("link") or "").lower()

    return (
        "access.redhat.com/security/cve/" in link
        or "access.redhat.com/errata/" in link
    )


def parse_time(value):
    if not value:
        return None

    try:
        value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def age_days(v):
    # Use system occurrence first because that represents how long
    # ACS has known about the finding in the environment.
    ts = (
        v.get("firstSystemOccurrence")
        or v.get("firstImageOccurrence")
        or v.get("publishedOn")
    )

    dt = parse_time(ts)

    if not dt:
        return None

    now = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return (now - dt).total_seconds() / 86400.0


def scrub(text):
    if text is None:
        return ""

    text = str(text)

    # Most-specific first.
    text = re.sub(
        r"(?i)cjis\.fbi\.gov",
        "customer.example.com",
        text
    )

    text = re.sub(
        r"(?i)fbi\.gov",
        "customer.example.com",
        text
    )

    text = re.sub(
        r"(?i)ncic",
        "customer",
        text
    )

    # Scrub standalone agency-marker tokens that appear in registry paths,
    # internal image names, etc.
    text = re.sub(
        r"(?i)(?<![a-z0-9])fbi(?![a-z0-9])",
        "customer",
        text
    )

    text = re.sub(
        r"(?i)(?<![a-z0-9])gov(?![a-z0-9])",
        "example",
        text
    )

    return text


def component_filter_matches(component):
    if not FILTER_COMPONENT:
        return True

    wanted = ALIASES.get(
        FILTER_COMPONENT,
        FILTER_COMPONENT
    )

    return component.lower() == wanted.lower()

# ============================================================
# FINDING EXTRACTION
# ============================================================


def component_objects(image):
    """
    RHACS image scan records contain component dictionaries with
    a 'vulns' array.

    Yield each such component exactly once.
    """

    stack = [image]
    seen_ids = set()

    while stack:
        obj = stack.pop()

        if isinstance(obj, dict):

            oid = id(obj)

            if oid in seen_ids:
                continue

            seen_ids.add(oid)

            vulns = obj.get("vulns")

            if isinstance(vulns, list):
                if any(
                    isinstance(x, dict)
                    and isinstance(x.get("cve"), str)
                    for x in vulns
                ):
                    yield obj

            for key, value in obj.items():

                # Don't recurse into vuln arrays from a component
                # we have already identified.
                if key == "vulns":
                    continue

                if isinstance(value, (dict, list)):
                    stack.append(value)

        elif isinstance(obj, list):
            stack.extend(obj)


def findings_from_record(result):
    live_pods = int(result.get("livePods") or 0)

    cluster, namespace, deployment = deployment_info(result)

    images = result.get("images") or []

    if not isinstance(images, list):
        return

    for image in images:

        image_ref, image_digest = image_identity(image)

        image_text = " ".join(strings(image))

        if RHSRE:
            if not is_rhsre(namespace, image_text, deployment):
                continue

            component_group = classify_rhsre(
                namespace,
                image_text,
                deployment
            )

        elif ALL_SCOPE:
            component_group = classify_all(
                namespace,
                image_text,
                deployment
            )

        else:
            component_group = classify(
                namespace,
                image_text,
                deployment
            )

            if not component_group:
                continue

        if not component_filter_matches(component_group):
            continue

        for comp in component_objects(image):

            comp_name = str(comp.get("name") or "")
            comp_version = str(comp.get("version") or "")
            comp_source = str(comp.get("source") or "")
            location = str(comp.get("location") or "")

            vulns = comp.get("vulns") or []

            for vuln in vulns:

                if not isinstance(vuln, dict):
                    continue

                cve = str(vuln.get("cve") or "")

                if not cve:
                    continue

                yield {
                    "livePods": live_pods,
                    "cluster": cluster,
                    "namespace": namespace,
                    "deployment": deployment,
                    "group": component_group,

                    "image": image_ref,
                    "imageDigest": image_digest,

                    "component": comp_name,
                    "componentVersion": comp_version,
                    "componentSource": comp_source,
                    "location": location,

                    "cve": cve,
                    "severity": severity_name(vuln),
                    "cvss": vuln.get("cvss"),
                    "fixedBy": vuln.get("fixedBy") or "",
                    "state": vuln.get("state") or "",
                    "suppressed": vuln.get("suppressed"),
                    "publishedOn": vuln.get("publishedOn") or "",
                    "firstSystemOccurrence": vuln.get("firstSystemOccurrence") or "",
                    "firstImageOccurrence": vuln.get("firstImageOccurrence") or "",
                    "fixAvailableTimestamp": vuln.get("fixAvailableTimestamp") or "",
                    "link": vuln.get("link") or "",
                    "advisory": vuln.get("advisory"),
                    "sources": sorted(vulnerability_sources(vuln)),
                    "redhat": redhat_source(vuln),
                    "ageDays": age_days(vuln),

                    # Preserve the complete vulnerability/component objects
                    # in the flattened CSV so useful fields are not discarded.
                    "rawVulnerability": vuln,
                    "rawComponent": comp,
                }

# ============================================================
# REPORT STATE
# ============================================================


counts = defaultdict(int)
unique = defaultdict(set)
critical_counts = defaultdict(int)
high_counts = defaultdict(int)

age15 = defaultdict(int)
age30 = defaultdict(int)
age90 = defaultdict(int)

seen = set()

api_records = 0
live_records = 0
inactive_records = 0

csv_writer = None
csv_file = None
csv_path = None

CSV_FIELDS = [
    "LivePods",
    "Cluster",
    "Namespace",
    "Deployment",
    "RHACSComponentGroup",

    "Image",
    "ImageDigest",

    "Component",
    "ComponentVersion",
    "ComponentSource",
    "Location",

    "CVE",
    "Severity",
    "CVSS",
    "Sources",
    "RedHatSource",

    "FixedBy",
    "Fixable",
    "State",
    "Suppressed",

    "PublishedOn",
    "FirstSystemOccurrence",
    "FirstImageOccurrence",
    "FixAvailableTimestamp",
    "AgeDays",

    "Link",
    "Advisory",

    "RawVulnerabilityJSON",
    "RawComponentJSON",
]

if MODE == "all":

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

    csv_path = os.path.join(
        OUTDIR,
        f"RHACS_Vulnerability_Report_SCRUBBED_{stamp}.csv"
    )

    csv_file = open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8"
    )

    csv_writer = csv.DictWriter(
        csv_file,
        fieldnames=CSV_FIELDS
    )

    csv_writer.writeheader()

# ============================================================
# STREAM INPUT
# ============================================================

_in_fh = open(_input_path, encoding="utf-8") if _input_path else sys.stdin
for line in _in_fh:

    line = line.strip()

    if not line:
        continue

    try:
        wrapper = json.loads(line)
    except json.JSONDecodeError:
        continue

    api_records += 1

    result = wrapper.get("result", wrapper)

    if not isinstance(result, dict):
        continue

    try:
        live = int(result.get("livePods") or 0)
    except Exception:
        live = 0

    if live > 0:
        live_records += 1
    else:
        inactive_records += 1

    for f in findings_from_record(result):

        # ----------------------------------------------------
        # --all
        # Includes all source/severity states and inactive.
        # ----------------------------------------------------

        if MODE == "all":

            fixable = bool(
                f["fixedBy"]
                or f["fixAvailableTimestamp"]
            )

            row = {
                "LivePods": f["livePods"],
                "Cluster": f["cluster"],
                "Namespace": f["namespace"],
                "Deployment": f["deployment"],
                "RHACSComponentGroup": f["group"],

                "Image": f["image"],
                "ImageDigest": f["imageDigest"],

                "Component": f["component"],
                "ComponentVersion": f["componentVersion"],
                "ComponentSource": f["componentSource"],
                "Location": f["location"],

                "CVE": f["cve"],
                "Severity": f["severity"],
                "CVSS": f["cvss"],
                "Sources": ",".join(f["sources"]),
                "RedHatSource": f["redhat"],

                "FixedBy": f["fixedBy"],
                "Fixable": fixable,
                "State": f["state"],
                "Suppressed": f["suppressed"],

                "PublishedOn": f["publishedOn"],
                "FirstSystemOccurrence": f["firstSystemOccurrence"],
                "FirstImageOccurrence": f["firstImageOccurrence"],
                "FixAvailableTimestamp": f["fixAvailableTimestamp"],
                "AgeDays": (
                    ""
                    if f["ageDays"] is None
                    else round(f["ageDays"], 2)
                ),

                "Link": f["link"],
                "Advisory": json.dumps(
                    f["advisory"],
                    separators=(",", ":")
                ),

                # Grafana drops these blobs. Writing them turned a few-minute
                # parse into ~15 minutes and a multi-GB CSV.
                "RawVulnerabilityJSON": "",
                "RawComponentJSON": "",
            }

            # Scrub every exported textual value.
            for key in list(row):
                if isinstance(row[key], str):
                    row[key] = scrub(row[key])

            csv_writer.writerow(row)

            continue

        # ----------------------------------------------------
        # TABLE REPORTS:
        # CURRENT DEPLOYED ONLY
        # ----------------------------------------------------

        if f["livePods"] <= 0:
            continue

        # Match the Critical + Important reporting we've been using.
        if f["severity"] not in {
            "Critical",
            "Important",
        }:
            continue

        # Optional cluster filter (empty CLUSTER_FILTER = all clusters).
        # Historical prod reports used: prod, prod-infra
        if CLUSTER_FILTER and f["cluster"] not in CLUSTER_FILTER:
            continue

        # Match saved RHACS report:
        # FIXABLE vulnerabilities only
        if not (
            f["fixedBy"]
            or f["fixAvailableTimestamp"]
        ):
            continue

        # Red Hat source modes.
        if MODE in {
            "rhsource",
            "age",
        } and not f["redhat"]:
            continue

        # Deduplicate repeated representations of the same finding
        # inside an RHACS workload export.
        #
        # We intentionally KEEP a finding appearing in separate
        # deployments/workloads because that represents separate
        # deployed exposure.
        key = (
            f["imageDigest"] or f["image"],
            f["component"],
            f["componentVersion"],
            f["cve"],
        )

        # Normal component reports intentionally deduplicate the same
        # vulnerable image/component/CVE across deployments.
        #
        # Expanded --all reports are meant to represent raw RHACS
        # finding occurrences, so do NOT collapse deployments there.
        if not ALL_SCOPE:
            if key in seen:
                continue
            seen.add(key)

        group = f["group"]

        counts[group] += 1
        unique[group].add(f["cve"])

        if f["severity"] == "Critical":
            critical_counts[group] += 1
        elif f["severity"] == "Important":
            high_counts[group] += 1

        if MODE == "age":

            age = f["ageDays"]

            if age is None:
                continue

            if age > 15:
                age15[group] += 1

            if age > 30:
                age30[group] += 1

            if age > 90:
                age90[group] += 1


if _input_path:
    _in_fh.close()

# ============================================================
# COMPANION JSON SUMMARY (table modes)
# ============================================================


def write_summary_json(visible_order):
    """Write Grafana-friendly summary next to table reports."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    generated_at = datetime.now(timezone.utc).isoformat()
    path = os.path.join(
        OUTDIR,
        f"RHACS_summary_{MODE}_{stamp}.json",
    )

    components = []
    totals = {
        "findings": 0,
        "critical": 0,
        "important": 0,
        "unique_cves": 0,
        "age_gt_15": 0,
        "age_gt_30": 0,
        "age_gt_90": 0,
    }
    all_unique = set()

    for group in visible_order:
        entry = {
            "component": group,
            "findings": int(counts[group]),
            "critical": int(critical_counts[group]),
            "important": int(high_counts[group]),
            "unique_cves": len(unique[group]),
            "age_gt_15": int(age15[group]),
            "age_gt_30": int(age30[group]),
            "age_gt_90": int(age90[group]),
        }
        components.append(entry)
        totals["findings"] += entry["findings"]
        totals["critical"] += entry["critical"]
        totals["important"] += entry["important"]
        totals["age_gt_15"] += entry["age_gt_15"]
        totals["age_gt_30"] += entry["age_gt_30"]
        totals["age_gt_90"] += entry["age_gt_90"]
        all_unique.update(unique[group])

    totals["unique_cves"] = len(all_unique)

    payload = {
        "mode": MODE,
        "generated_at": generated_at,
        "all_scope": bool(ALL_SCOPE),
        "rhsre": bool(RHSRE),
        "component_filter": FILTER_COMPONENT,
        "api_records": api_records,
        "live_records": live_records,
        "inactive_records": inactive_records,
        "components": components,
        "totals": totals,
    }

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")

    return path


# ============================================================
# OUTPUT
# ============================================================

if csv_file:
    csv_file.close()

if MODE == "all":

    print()
    print("============================================================")
    print(" RHACS SCRUBBED CSV CREATED")
    print("============================================================")
    print()
    print(f"File: {csv_path}")
    print()
    print(f"API records : {api_records}")
    print(f"Live        : {live_records}")
    print(f"Inactive    : {inactive_records}")
    print()
    print("CSV includes all severities and vulnerability sources.")
    print("No current/live filter was applied to --all.")
    print("RawComponentJSON and RawVulnerabilityJSON are left empty.")
    print("The Grafana report does not read those columns.")
    print()

    sys.exit(0)

if RHSRE:
    base_order = RHSRE_GROUP_ORDER
elif ALL_SCOPE:
    base_order = ALL_GROUP_ORDER
else:
    base_order = ORDER

# Add any groups that were discovered but are not explicitly
# listed in our preferred display order.
discovered_groups = set(counts.keys()) | set(unique.keys())

visible_order = [
    x for x in base_order
    if x in discovered_groups or not (ALL_SCOPE or RHSRE)
]

for x in sorted(discovered_groups):
    if x not in visible_order:
        visible_order.append(x)

if FILTER_COMPONENT:

    wanted = ALIASES.get(
        FILTER_COMPONENT,
        FILTER_COMPONENT
    )

    visible_order = [
        x for x in visible_order
        if x.lower() == wanted.lower()
    ]

if MODE in {
    "raw",
    "rhsource",
}:

    if RHSRE:
        scope_label = "ROSA RED HAT/SRE RESPONSIBILITY"
    elif ALL_SCOPE:
        scope_label = "ALL COMPONENTS"
    else:
        scope_label = "SELECTED COMPONENTS"

    if MODE == "raw":
        title = (
            f"RHACS — ALL SOURCES / {scope_label} / "
            "CURRENT DEPLOYED / CRITICAL + IMPORTANT"
        )
    else:
        title = (
            f"RHACS — RED HAT SOURCE ONLY / {scope_label} / "
            "CURRENT DEPLOYED / CRITICAL + IMPORTANT"
        )

    print()
    print(title)
    print()
    total = 0
    total_critical = 0
    total_high = 0
    total_unique = set()

    if SHOW_SEV:
        print(
            f'{"Component":<24}'
            f'{"Findings":>10}'
            f'{"Critical":>11}'
            f'{"High":>9}'
            f'{"Unique CVEs":>14}'
        )
        print("-" * 68)
    else:
        print(
            f'{"Component":<24}'
            f'{"Findings":>10}'
            f'{"Unique CVEs":>14}'
        )
        print("-" * 48)

    for group in visible_order:

        total += counts[group]
        total_critical += critical_counts[group]
        total_high += high_counts[group]
        total_unique.update(unique[group])

        if SHOW_SEV:
            print(
                f'{group:<24}'
                f'{counts[group]:>10}'
                f'{critical_counts[group]:>11}'
                f'{high_counts[group]:>9}'
                f'{len(unique[group]):>14}'
            )
        else:
            print(
                f'{group:<24}'
                f'{counts[group]:>10}'
                f'{len(unique[group]):>14}'
            )

    if SHOW_SEV:
        print("-" * 68)
        print(
            f'{"TOTAL":<24}'
            f'{total:>10}'
            f'{total_critical:>11}'
            f'{total_high:>9}'
            f'{len(total_unique):>14}'
        )
    else:
        print("-" * 48)
        print(
            f'{"TOTAL":<24}'
            f'{total:>10}'
            f'{len(total_unique):>14}'
        )

    print()
    print(
        f"ACS workload records: "
        f"{api_records} total / "
        f"{live_records} live / "
        f"{inactive_records} inactive"
    )

    print()
    summary_path = write_summary_json(visible_order)
    print(f"Summary JSON: {summary_path}")
    print()

elif MODE == "age":

    print()
    print(
        "RHACS — RED HAT SOURCE / CURRENT DEPLOYED "
        "/ CRITICAL + IMPORTANT"
    )

    print()

    print(
        f'{"Component":<24}'
        f'{">15 Days":>11}'
        f'{">30 Days":>11}'
        f'{">90 Days":>11}'
    )

    print("-" * 57)

    t15 = 0
    t30 = 0
    t90 = 0

    for group in visible_order:

        t15 += age15[group]
        t30 += age30[group]
        t90 += age90[group]

        print(
            f'{group:<24}'
            f'{age15[group]:>11}'
            f'{age30[group]:>11}'
            f'{age90[group]:>11}'
        )

    print("-" * 57)

    print(
        f'{"TOTAL":<24}'
        f'{t15:>11}'
        f'{t30:>11}'
        f'{t90:>11}'
    )

    print()
    summary_path = write_summary_json(visible_order)
    print(f"Summary JSON: {summary_path}")
    print()
