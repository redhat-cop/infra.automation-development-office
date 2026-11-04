#!/usr/bin/env python3
"""Replace amd64 digests with manifest list digests in latest_ref for display."""

import json
import os
import subprocess
import sys
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
AUTH_FILE = os.environ.get('REGISTRY_AUTH_FILE', '')
LATEST_JSON = os.path.join(DATA_DIR, "latest_scan_results.json")

data = json.load(open(LATEST_JSON))
fr = data['fix_results']
tag_info = data.get('tag_info', {})
sbm = data.get('scan_base_map', {})

# Collect unique base images that have a tag and digest
bases = {}
for base, info in tag_info.items():
    if info.get('tag') and info.get('digest') and not info.get('error'):
        bases[base] = info['tag']

print(f"{len(bases)} base images to fetch manifest list digests")

def get_manifest_list_digest(base, tag):
    """Fetch the manifest list and compute its digest."""
    try:
        cmd = ['skopeo', 'inspect', '--raw', f'docker://{base}:{tag}']
        if AUTH_FILE:
            cmd += ['--authfile', AUTH_FILE]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return (base, None, f'error: {result.stderr[:80]}')

        raw = result.stdout
        manifest = json.loads(raw)
        mt = manifest.get('mediaType', '')

        if 'manifest.list' in mt or 'index' in mt:
            ml_digest = 'sha256:' + hashlib.sha256(raw.encode()).hexdigest()
            return (base, ml_digest, None)
        else:
            return (base, None, 'single-arch')
    except Exception as e:
        return (base, None, str(e)[:80])

done = 0
ml_digests = {}
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(get_manifest_list_digest, sbm.get(b, b), t): b for b, t in bases.items()}
    for f in as_completed(futs):
        base = futs[f]
        _, digest, err = f.result()
        ml_digests[base] = (digest, err)
        done += 1
        if done % 20 == 0 or done == len(bases):
            print(f"  {done}/{len(bases)}")

found = sum(1 for d, e in ml_digests.values() if d)
single = sum(1 for d, e in ml_digests.values() if e == 'single-arch')
errors = sum(1 for d, e in ml_digests.values() if e and e != 'single-arch')
print(f"\nMulti-arch: {found}, Single-arch: {single}, Errors: {errors}")

if errors:
    for base, (d, e) in ml_digests.items():
        if e and e != 'single-arch':
            print(f"  {base}: {e}")

# Build scan-base-keyed lookup for ml_digests
ml_by_scan_base = {}
for base, val in ml_digests.items():
    sb = sbm.get(base, base)
    ml_by_scan_base[sb] = val
    if sb != base:
        ml_by_scan_base[base] = val

# Update fix_results: replace amd64 digest with manifest list digest in latest_ref
updated = 0
for key, v in fr.items():
    ref = v.get('latest_ref', '')
    if not ref or '@' not in ref:
        continue
    base = ref.split('@')[0]
    ml = ml_by_scan_base.get(base, (None, None))
    if ml[0]:
        v['latest_ref'] = f"{base}@{ml[0]}"
        updated += 1

print(f"\nUpdated {updated} latest_ref entries to use manifest list digests")

# Save
with open(LATEST_JSON, 'w') as f:
    json.dump(data, f)

# Verify the specific example
for k, v in fr.items():
    if 'devworkspace-rhel9-operator' in k and 'GHSA-hrxh' in k:
        print(f"\nVerify: {v['latest_ref']}")
        break

print(f"Saved to {LATEST_JSON}")
