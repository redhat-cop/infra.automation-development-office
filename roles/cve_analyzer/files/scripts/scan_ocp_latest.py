"""
Handle OCP core images: extract {OCP_TARGET_VERSION} component digests,
scan the new ones, and update the latest_scan_results.json.
"""

from collections import Counter
import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
ROX_ENDPOINT = os.environ.get('ROX_ENDPOINT', '')
INSECURE = os.environ.get('ROX_INSECURE', '1') == '1'
WORKERS = int(os.environ.get('SCAN_WORKERS', '10'))
OCP_TARGET_VERSION = os.environ.get('OCP_TARGET_VERSION', '4.18.54')
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
LATEST_JSON = os.path.join(DATA_DIR, "latest_scan_results.json")
CURRENT_SCANS = os.path.join(DATA_DIR, "roxctl_scan_results.json")

rows = list(csv.DictReader(open(TRIAGE_CSV)))
latest_data = json.load(open(LATEST_JSON))
fix_results = latest_data['fix_results']

# Get current OCP art-dev images from triage
ocp_images = set()
ocp_base = 'quay.io/openshift-release-dev/ocp-v4.0-art-dev'
for r in rows:
    if ocp_base in r['Image_Full']:
        ocp_images.add(r['Image_Full'])
print(f"OCP core images in triage: {len(ocp_images)}")

# Get target OCP payload
print(f"Extracting {OCP_TARGET_VERSION} release payload...")
try:
    result = subprocess.run(
        ['oc', 'adm', 'release', 'info',
         f'quay.io/openshift-release-dev/ocp-release:{OCP_TARGET_VERSION}-x86_64',
         '--output', 'json'],
        capture_output=True, text=True, timeout=60,
        check=False,
    )
except FileNotFoundError:
    print("SKIP: oc CLI not available")
    sys.exit(0)
if result.returncode != 0 or not (result.stdout or "").strip():
    err = (result.stderr or result.stdout or "").strip()
    print(
        f"SKIP: oc adm release info returned no JSON for "
        f"{OCP_TARGET_VERSION}: {err[:400]}"
    )
    sys.exit(0)
payload = json.loads(result.stdout)
tags_tgt = payload.get('references', {}).get('spec', {}).get('tags', [])
# Build set of all {OCP_TARGET_VERSION} digests
digests_tgt = set()
refs_tgt = {}
for t in tags_tgt:
    img = t.get('from', {}).get('name', '')
    if ocp_base in img:
        digest = img.split('@')[1] if '@' in img else ''
        digests_tgt.add(digest)
        refs_tgt[digest] = img

print(f"  {OCP_TARGET_VERSION} component images: {len(digests_tgt)}")

# Check which current images have changed in {OCP_TARGET_VERSION}
current_digests = {}
for img in ocp_images:
    digest = img.split('@')[1] if '@' in img else ''
    current_digests[digest] = img

same = set(current_digests.keys()) & digests_tgt
changed = set(current_digests.keys()) - digests_tgt
print(f"  Same digest (no update): {len(same)}")
print(f"  Changed (updated in {OCP_TARGET_VERSION}): {len(changed)}")

# For changed images: scan the NEW {OCP_TARGET_VERSION} versions
# We need to figure out which {OCP_TARGET_VERSION} digest corresponds to which current image
# Since ocp-v4.0-art-dev uses different digests per component, we can't directly map
# Instead, scan ALL unique {OCP_TARGET_VERSION} digests and build a CVE lookup

# But that's 186 images... Let's be smarter: only scan the {OCP_TARGET_VERSION} digests
# that correspond to the current images' components.
# Actually, since we can't easily map art-dev digest -> component name,
# let's just scan all unique {OCP_TARGET_VERSION} digests (they're cached in Central)

unique_tgt_digests = list(digests_tgt)
print(f"\nScanning {len(unique_tgt_digests)} {OCP_TARGET_VERSION} images via roxctl...")


def scan_image(ref):
    try:
        env = os.environ.copy()
        env['ROX_ENDPOINT'] = ROX_ENDPOINT
        cmd = ['roxctl', 'image', 'scan', '--image', ref, '--output', 'json']
        if INSECURE:
            cmd.insert(3, '--insecure-skip-tls-verify')
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, env=env,
            check=False,
        )
        if r.returncode == 0:
            return (ref, json.loads(r.stdout).get('result', {}))
        return (ref, {'error': r.stderr[:100]})
    except Exception as e:
        return (ref, {'error': str(e)[:100]})


scan_tgt = {}
done = 0
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(scan_image, f"{ocp_base}@{d}"): d for d in unique_tgt_digests}
    for f in as_completed(futs):
        ref, result = f.result()
        digest = ref.split('@')[1]
        scan_tgt[digest] = result
        done += 1
        if done % 40 == 0 or done == len(unique_tgt_digests):
            errs = sum(1 for v in scan_tgt.values() if 'error' in v)
            print(f"  {done}/{len(unique_tgt_digests)} ({errs} errors)")

ok = sum(1 for v in scan_tgt.values() if 'error' not in v)
print(f"  Scanned OK: {ok}")

if ok == 0:
    print("WARNING: All roxctl scans failed — cannot determine fix status for OCP images")
    print("  Check that the RHACS API token has Image write permissions")

# Build CVE lookup for ALL {OCP_TARGET_VERSION} images combined
all_tgt_cves = set()
for digest, result in scan_tgt.items():
    if 'error' in result:
        continue
    for v in result.get('vulnerabilities', []):
        all_tgt_cves.add(v.get('cveId', ''))
print(f"  Total unique CVEs across {OCP_TARGET_VERSION}: {len(all_tgt_cves)}")

# Now scan the CURRENT ocp images to get their CVEs
print("\nLoading current OCP scan results...")
current_scans = json.load(open(CURRENT_SCANS))

# For each triage record with OCP core images, determine fix status
ocp_records = [(i, r) for i, r in enumerate(rows) if ocp_base in r['Image_Full']]
print(f"OCP triage records: {len(ocp_records)}")

fixed = 0
still_vuln = 0
unavail = 0

scans_available = ok > 0
ocp_minor = '.'.join(OCP_TARGET_VERSION.split('.')[:2])
ocp_release_ref = f'quay.io/openshift-release-dev/ocp-release:{OCP_TARGET_VERSION}-x86_64'
ocp_notes_url = f'https://docs.openshift.com/container-platform/{ocp_minor}/release_notes/ocp-{ocp_minor.replace(".", "-")}-release-notes.html'

for _, r in ocp_records:
    img = r['Image_Full']
    cve = r['CVE']
    key = f"{img}|||{cve}"
    current_digest = img.split('@')[1] if '@' in img else ''

    if not scans_available:
        fix_results[key] = {
            'status': 'SCAN_UNAVAILABLE',
            'latest_ref': ocp_release_ref,
            'latest_tag': OCP_TARGET_VERSION,
            'catalog_url': ocp_notes_url,
        }
        unavail += 1
    elif current_digest in digests_tgt:
        fix_results[key] = {
            'status': 'STILL_VULNERABLE',
            'latest_ref': img,
            'latest_tag': f'{OCP_TARGET_VERSION} (same digest)',
            'catalog_url': '',
        }
        still_vuln += 1
    elif cve in all_tgt_cves:
        fix_results[key] = {
            'status': 'STILL_VULNERABLE',
            'latest_ref': ocp_release_ref,
            'latest_tag': OCP_TARGET_VERSION,
            'catalog_url': ocp_notes_url,
        }
        still_vuln += 1
    else:
        fix_results[key] = {
            'status': 'FIXED_IN_LATEST',
            'latest_ref': ocp_release_ref,
            'latest_tag': OCP_TARGET_VERSION,
            'catalog_url': ocp_notes_url,
        }
        fixed += 1

print(f"\nOCP results: FIXED={fixed}, STILL_VULNERABLE={still_vuln}, SCAN_UNAVAILABLE={unavail}")

# Also handle ocp-release image
ocp_release_records = [(i, r) for i, r in enumerate(rows)
                       if 'ocp-release' in r['Image_Full'] and ocp_base not in r['Image_Full']]
for _, r in ocp_release_records:
    key = f"{r['Image_Full']}|||{r['CVE']}"
    fix_results[key] = {
        'status': 'STILL_VULNERABLE',
        'latest_ref': ocp_release_ref,
        'latest_tag': OCP_TARGET_VERSION,
        'catalog_url': ocp_notes_url,
    }

# Save updated results
latest_data['fix_results'] = fix_results
with open(LATEST_JSON, 'w') as f:
    json.dump(latest_data, f)

# Final stats
statuses = Counter(v['status'] for v in fix_results.values())
print(f"\nFinal results across {len(fix_results)} records:")
for s, c in statuses.most_common():
    print(f"  {s}: {c}")
print(f"\nSaved to {LATEST_JSON}")
