#!/usr/bin/env python3
"""
Step 0: Transform a raw RHACS CSV export into the triage CSV format.
Groups by CVE+Image, derives product lines, computes priority/action,
and generates remediation paths, triage reasoning, and POAM justifications.

Usage: python3 prepare_triage.py [DATA_DIR]
  DATA_DIR defaults to ../data relative to this script.
  Reads:  DATA_DIR/raw.csv
  Writes: DATA_DIR/triage.csv
"""

import csv
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "data")
RAW_CSV = os.path.join(DATA_DIR, "raw.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "triage.csv")

# ── Product line mapping: image namespace → product name ──
NS_PRODUCT = {
    'advanced-cluster-security': 'RHACS (StackRox)',
    'cert-manager': 'Cert-Manager',
    'compliance': 'Compliance Operator',
    'devspaces': 'Dev Spaces',
    'devworkspace': 'Dev Spaces',
    'external-secrets-operator': 'External Secrets Operator',
    'jetstack': 'Cert-Manager CSI Sidecars',
    'kube-descheduler-operator': 'Kube Descheduler',
    'multicluster-engine': 'Multicluster Engine (MCE)',
    'openshift': 'OpenShift CLI',
    'openshift-gitops-1': 'OpenShift GitOps',
    'openshift-logging': 'OpenShift Logging',
    'openshift-release-dev': 'OpenShift Core (OCP)',
    'prometheus': 'Blackbox Exporter (3rd-party)',
    'redhat': 'Operator Index',
    'rhacm2': 'RHACM (ACM)',
    'rhbk': 'Red Hat Build of Keycloak',
    'rhel8': 'RHEL8 Base Image',
    'rhel9': 'RHEL9 Base Image',
    'rhosdt': 'OpenTelemetry',
    'web-terminal': 'Web Terminal',
}

# Image-specific product overrides (short name → product)
IMG_PRODUCT = {
    'ose-aws-efs-csi-driver-container-rhel9': 'AWS EFS CSI Driver',
    'ose-aws-efs-csi-driver-rhel9-operator': 'AWS EFS CSI Driver',
    'ose-csi-external-provisioner-rhel9': 'CSI Sidecars (OCP)',
    'ose-csi-livenessprobe-rhel9': 'CSI Sidecars (OCP)',
    'ose-csi-node-driver-registrar-rhel9': 'CSI Sidecars (OCP)',
    'ose-kube-rbac-proxy': 'Kube RBAC Proxy (OCP)',
    'ose-kube-rbac-proxy-rhel9': 'Kube RBAC Proxy (OCP)',
    'ose-oauth-proxy': 'OAuth Proxy (OCP)',
}

# Namespace → remediation path template
NS_REMEDIATION = {
    'advanced-cluster-security': 'Update RHACS operator via OLM',
    'cert-manager': 'Update cert-manager operator via OLM',
    'compliance': 'Update compliance-operator via OLM',
    'devspaces': 'Update devspaces operator via OLM',
    'devworkspace': 'Update devspaces operator via OLM',
    'external-secrets-operator': 'Update external-secrets-operator via OLM',
    'jetstack': 'Update cert-manager operator via OLM',
    'kube-descheduler-operator': 'Update kube-descheduler-operator via OLM',
    'multicluster-engine': 'Update multicluster-engine operator via OLM',
    'openshift': 'Upgrade OCP cluster or update oc client image',
    'openshift-gitops-1': 'Update openshift-gitops-operator via OLM',
    'openshift-logging': 'Update cluster-logging operator via OLM',
    'openshift-release-dev': 'Upgrade OCP cluster to next available z-stream',
    'redhat': 'Update redhat-operator catalogsource',
    'rhacm2': 'Update advanced-cluster-management operator via OLM',
    'rhbk': 'Update rhbk-operator via OLM',
    'rhosdt': 'Update opentelemetry-product operator via OLM',
    'web-terminal': 'Update web-terminal operator via OLM',
}


def parse_image(image_ref):
    """Extract namespace, short name, and registry from an image reference."""
    ref = image_ref.split('@')[0] if '@' in image_ref else image_ref.rsplit(':', 1)[0]
    parts = ref.split('/')
    if len(parts) >= 3:
        registry = parts[0]
        ns = parts[1] if 'redhat-services-prod' not in parts[1] else '/'.join(parts[1:-1])
        short = parts[-1]
    elif len(parts) == 2:
        registry = parts[0]
        ns = ''
        short = parts[1]
    else:
        registry = ''
        ns = ''
        short = parts[0]
    return registry, ns, short


def get_product_line(image_ref):
    _, ns, short = parse_image(image_ref)
    if short in IMG_PRODUCT:
        return IMG_PRODUCT[short]
    if 'redhat-services-prod' in ns:
        return 'SRE Managed Services'
    return NS_PRODUCT.get(ns, ns.replace('-', ' ').title() if ns else 'Unknown')


def get_remediation(image_ref):
    _, ns, _ = parse_image(image_ref)
    if 'redhat-services-prod' in ns:
        return 'Contact SRE team / managed by Red Hat SRE'
    return NS_REMEDIATION.get(ns, f'Update {ns} operator via OLM' if ns else 'Update image')


INTERNAL_REGISTRY = 'image-registry.openshift-image-registry.svc:5000/'
PUBLIC_REGISTRIES = ['quay.io', 'registry.redhat.io']

def _skopeo_probe(candidate):
    """Check if a public image exists using skopeo without auth."""
    try:
        base = candidate.split('@')[0] if '@' in candidate else candidate.rsplit(':', 1)[0]
        env = os.environ.copy()
        env.pop('REGISTRY_AUTH_FILE', None)
        result = subprocess.run(
            ['skopeo', 'inspect', '--raw', f'docker://{base}'],
            capture_output=True, text=True, timeout=15, env=env,
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_scan_image(image_ref):
    """Translate internal registry refs to public Red Hat registry equivalents.

    Internal images like image-registry.openshift-image-registry.svc:5000/ns/img@sha256:...
    are resolved to quay.io/ns/img@sha256:... or registry.redhat.io/ns/img@sha256:...
    by probing the public registries with skopeo (without auth, so only images
    that RHACS Central can also access are discovered).
    """
    if not image_ref.startswith(INTERNAL_REGISTRY):
        return image_ref
    suffix = image_ref[len(INTERNAL_REGISTRY):]
    parts = suffix.split('/', 1)
    if len(parts) < 2:
        return image_ref
    ns = parts[0]
    img_with_tag = parts[1]
    img_name = img_with_tag.split('@')[0].split(':')[0]
    tag_or_digest = img_with_tag[len(img_name):]
    paths_to_try = [suffix]
    if ns == 'openshift':
        paths_to_try.append(f'{ns}/origin-{img_name}{tag_or_digest}')
        paths_to_try.append(f'openshift4/ose-{img_name}{tag_or_digest}')
    paths_to_try.append(img_with_tag)
    for path in paths_to_try:
        for reg in PUBLIC_REGISTRIES:
            candidate = f'{reg}/{path}'
            if _skopeo_probe(candidate):
                return candidate
    return f'{PUBLIC_REGISTRIES[0]}/{suffix}'


def compute_priority(severity, cvss, epss):
    if severity == 'CRITICAL' or (cvss >= 9.0 and epss >= 1.0):
        return 'P1-CRITICAL', 'PATCH'
    if epss >= 10.0:
        return 'P1-HIGH-EPSS', 'PATCH'
    if cvss >= 9.0 or (cvss >= 8.0 and epss >= 1.0):
        return 'P2-HIGH-IMPACT', 'PATCH'
    if epss >= 5.0:
        return 'P2-HIGH-EPSS', 'PATCH'
    if cvss >= 8.0 or (cvss >= 7.0 and epss >= 1.0):
        return 'P3-MODERATE', 'PATCH'
    if cvss >= 7.0 or (severity == 'IMPORTANT' and cvss >= 6.0):
        return 'P4-MONITOR', 'MONITOR'
    return 'P5-LOW', 'MONITOR'


def triage_reasoning(severity, cvss, epss, nvd_cvss):
    parts = []
    if severity:
        parts.append(f'{severity} severity')
    if cvss:
        parts.append(f'CVSS {cvss}')
    if nvd_cvss and nvd_cvss != '0' and nvd_cvss != str(cvss):
        parts.append(f'NVD CVSS {nvd_cvss}')
    if epss:
        parts.append(f'EPSS {epss}%')
    if not parts:
        return 'No CVSS scored yet, low EPSS (0.0%) – monitor for NVD scoring'
    return ', '.join(parts)


def poam_justification(priority, action, fixed_in, remediation, product):
    if action == 'PATCH':
        urgency = 'URGENT' if priority.startswith('P1') else 'HIGH' if priority.startswith('P2') else 'MODERATE'
        constraint = f'Constraint: {remediation}'
        fix_note = f'Fix available in {fixed_in}.' if fixed_in else 'No fix available yet — monitor upstream.'
        return f'POA&M Required ({urgency}). {constraint} — {fix_note}'
    return f'POA&M Informational. Low-risk, monitor for upstream patches. {remediation}'


def verify_osv(cve_id, component, version):
    """Check a CVE against the OSV database."""
    if not cve_id.startswith('CVE-') and not cve_id.startswith('GHSA-'):
        return '', ''
    url = f'https://osv.dev/vulnerability/{cve_id}'
    try:
        api_url = f'https://api.osv.dev/v1/vulns/{cve_id}'
        req = urllib.request.Request(api_url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            affected = data.get('affected', [])
            if not affected:
                return 'Not in OSV', ''
            ranges_str = []
            for a in affected:
                for r in a.get('ranges', []):
                    events = r.get('events', [])
                    parts = []
                    for e in events:
                        for k, v in e.items():
                            parts.append(f'{k}={v}')
                    if parts:
                        ranges_str.append(', '.join(parts))
            confirmed = 'Confirmed' if affected else 'Not confirmed'
            return confirmed, '; '.join(ranges_str[:3])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 'Not in OSV', ''
        return f'OSV error ({e.code})', ''
    except Exception:
        return 'OSV error', ''


# ── Main ──

ALLOWED_REGISTRIES = ('registry.redhat.io/', 'quay.io/', 'image-registry.openshift-image-registry.svc:5000/')

print(f"Reading raw CSV: {RAW_CSV}")
raw_rows = list(csv.DictReader(open(RAW_CSV)))
print(f"  {len(raw_rows)} raw records")

filtered = [r for r in raw_rows if r.get('Image', '').startswith(ALLOWED_REGISTRIES)]
skipped = len(raw_rows) - len(filtered)
if skipped:
    print(f"  Filtered out {skipped} records from non-Red Hat registries")
raw_rows = filtered

# Group by CVE + Image
groups = defaultdict(lambda: {
    'namespaces': set(), 'deployments': set(), 'components': set(),
    'versions': set(), 'clusters': set(), 'first_row': None
})

for r in raw_rows:
    key = (r['CVE'], r['Image'])
    g = groups[key]
    if g['first_row'] is None:
        g['first_row'] = r
    g['namespaces'].add(r['Namespace'])
    g['deployments'].add(r['Deployment'])
    g['components'].add(r['Component'])
    g['versions'].add(r['Component Version'])
    g['clusters'].add(r['Cluster'])

print(f"  {len(groups)} unique CVE+Image combinations")

# Resolve internal registry images to public equivalents
internal_images = sorted(set(
    img for _, img in groups.keys() if img.startswith(INTERNAL_REGISTRY)
))
scan_image_cache = {}
if internal_images:
    print(f"\nResolving {len(internal_images)} internal registry images to public registries...")
    for img in internal_images:
        resolved = resolve_scan_image(img)
        scan_image_cache[img] = resolved
        if resolved != img:
            print(f"  {img.split('/', 3)[-1][:60]} -> {resolved.split('/')[0]}")
        else:
            print(f"  {img.split('/', 3)[-1][:60]} -> (no public match, defaulting to registry.redhat.io)")

# Build triage rows
triage = []
for (cve, image), g in groups.items():
    r = g['first_row']
    severity = r.get('Severity', '')
    cvss = float(r.get('CVSS', '0') or '0')
    nvd_cvss = r.get('NVDCVSS', '0')
    epss = float(r.get('EPSS Probability Percentage', '0') or '0')
    fixed_in = r.get('CVE Fixed In', '')

    _, _, short = parse_image(image)
    product = get_product_line(image)
    remediation = get_remediation(image)
    scan_image = scan_image_cache.get(image, image)
    priority, action = compute_priority(severity, cvss, epss)

    triage.append({
        'Priority': priority,
        'Action': action,
        'CVE': cve,
        'Severity': severity,
        'CVSS': str(cvss) if cvss else '0',
        'NVD_CVSS': nvd_cvss,
        'EPSS_Pct': str(epss),
        'Product_Line': product,
        'Image_Short': short,
        'Image_Full': image,
        'Cluster': '; '.join(sorted(g['clusters'])),
        'Namespaces': '; '.join(sorted(g['namespaces'])),
        'Deployments': '; '.join(sorted(g['deployments'])),
        'Affected_Components': '; '.join(sorted(g['components'])),
        'Component_Versions': '; '.join(sorted(g['versions'])),
        'Fixed_In': fixed_in,
        'RHSA_Advisory': r.get('Advisory Name', ''),
        'Advisory_Link': r.get('Advisory Link', ''),
        'Reference_Link': r.get('Reference', ''),
        'Remediation_Path': remediation,
        'Triage_Reasoning': triage_reasoning(severity, cvss, epss, nvd_cvss),
        'OSV_Verification': '',
        'OSV_Affected_Range': '',
        'POAM_Justification': poam_justification(priority, action, fixed_in, remediation, product),
        'Discovered': r.get('Discovered At', ''),
        'Scan_Image': scan_image,
    })

# OSV verification. CVE_SKIP_OSV=1 leaves the columns empty.
unique_cves = sorted(set(t['CVE'] for t in triage))
osv_cache = {}
if os.environ.get('CVE_SKIP_OSV', '0') == '1':
    print(f"\nSkipping OSV verification for {len(unique_cves)} CVEs (CVE_SKIP_OSV=1)")
else:
    print(f"\nVerifying {len(unique_cves)} CVEs against OSV...")
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(verify_osv, cve, '', ''): cve for cve in unique_cves}
        for f in as_completed(futs):
            cve = futs[f]
            status, ranges = f.result()
            osv_cache[cve] = (status, ranges)
            done += 1
            if done % 40 == 0 or done == len(unique_cves):
                print(f"  {done}/{len(unique_cves)}")

for t in triage:
    osv = osv_cache.get(t['CVE'], ('', ''))
    t['OSV_Verification'] = osv[0]
    t['OSV_Affected_Range'] = osv[1]

# Sort by priority
PRI_ORDER = {'P1-CRITICAL': 0, 'P1-HIGH-EPSS': 1, 'P2-HIGH-IMPACT': 2,
             'P2-HIGH-EPSS': 3, 'P3-MODERATE': 4, 'P4-MONITOR': 5, 'P5-LOW': 6}
triage.sort(key=lambda t: (PRI_ORDER.get(t['Priority'], 99), -float(t['CVSS'] or '0')))

# Write output
fields = ['Priority', 'Action', 'CVE', 'Severity', 'CVSS', 'NVD_CVSS', 'EPSS_Pct',
          'Product_Line', 'Image_Short', 'Image_Full', 'Cluster', 'Namespaces',
          'Deployments', 'Affected_Components', 'Component_Versions', 'Fixed_In',
          'RHSA_Advisory', 'Advisory_Link', 'Reference_Link', 'Remediation_Path',
          'Triage_Reasoning', 'OSV_Verification', 'OSV_Affected_Range',
          'POAM_Justification', 'Discovered', 'Scan_Image']

with open(OUTPUT_CSV, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(triage)

from collections import Counter
pri = Counter(t['Priority'] for t in triage)
act = Counter(t['Action'] for t in triage)
print(f"\nWrote {len(triage)} records to {OUTPUT_CSV}")
print(f"  Priorities: {dict(sorted(pri.items()))}")
print(f"  Actions: {dict(act)}")
