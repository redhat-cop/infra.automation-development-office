"""
For each unique base image:
1. Use skopeo to find the latest tag/digest
2. Scan it with roxctl
3. Compare against current CVEs to determine which are fixed
4. Build catalog.redhat.com links
5. Save results for the report builder
"""

from collections import Counter
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
ROX_ENDPOINT = os.environ.get('ROX_ENDPOINT', '')
INSECURE = os.environ.get('ROX_INSECURE', '1') == '1'
WORKERS = int(os.environ.get('SCAN_WORKERS', '10'))
AUTH_FILE = os.environ.get('REGISTRY_AUTH_FILE', '')
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
SCAN_JSON = os.path.join(DATA_DIR, "roxctl_scan_results.json")
OUTPUT = os.path.join(DATA_DIR, "latest_scan_results.json")

rows = list(csv.DictReader(open(TRIAGE_CSV)))
current_scans = json.load(open(SCAN_JSON))

# Build map: base_image -> [(current_digest_ref, cve, component, version), ...]
# scan_base_map translates internal registry refs to public equivalents for skopeo/roxctl
base_map = defaultdict(lambda: {'digests': set(), 'cves': []})
scan_base_map = {}
for r in rows:
    img = r['Image_Full']
    scan_img = r.get('Scan_Image', '') or img
    if '@sha256:' in img:
        base = img.split('@sha256:')[0]
    else:
        base = img.rsplit(':', 1)[0]
    if '@sha256:' in scan_img:
        scan_base = scan_img.split('@sha256:')[0]
    else:
        scan_base = scan_img.rsplit(':', 1)[0]
    base_map[base]['digests'].add(img)
    base_map[base]['cves'].append({
        'cve': r['CVE'],
        'component': r.get('Affected_Components', ''),
        'version': r.get('Component_Versions', ''),
        'image_full': img,
    })
    if base not in scan_base_map:
        scan_base_map[base] = scan_base

print(f"{len(base_map)} unique base images to check")


def _version_key(tag):
    """Sort key that compares version segments numerically."""
    t = re.sub(r'^v', '', tag)
    parts = re.split(r'[.\-]', t)
    result = []
    for p in parts:
        try:
            result.append((0, int(p)))
        except ValueError:
            result.append((1, p))
    return result

# ── Step 1: Find latest tag for each base image ──


def get_latest_tag(base_image):
    """Use skopeo to find the latest numeric tag and its digest."""
    try:
        cmd = ['skopeo', 'list-tags', f'docker://{base_image}']
        if AUTH_FILE:
            cmd += ['--authfile', AUTH_FILE]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return (base_image, None, None, f'skopeo error: {result.stderr[:100]}')

        tags = json.loads(result.stdout).get('Tags', [])
        # Filter for pure numeric tags (Red Hat build IDs)
        numeric = [t for t in tags if re.match(r'^\d+$', t)]
        # Also check for semver-like tags (v1.2.3, 1.2.3-4)
        semver = [t for t in tags if re.match(r'^v?\d+\.\d+', t)
                  and not t.endswith('.sig') and not t.endswith('.att')
                  and '-source' not in t]

        latest_tag = None
        if numeric:
            latest_tag = sorted(numeric, key=int)[-1]
        elif semver:
            latest_tag = sorted(semver, key=_version_key)[-1]
        else:
            return (base_image, None, None, 'no usable tags found')

        # Get digest — use --raw to handle multi-arch manifests
        icmd = ['skopeo', 'inspect', '--raw', f'docker://{base_image}:{latest_tag}']
        if AUTH_FILE:
            icmd += ['--authfile', AUTH_FILE]
        inspect = subprocess.run(
            icmd, capture_output=True, text=True, timeout=30,
            check=False,
        )
        if inspect.returncode != 0:
            return (base_image, latest_tag, None, f'inspect error: {inspect.stderr[:100]}')

        manifest = json.loads(inspect.stdout)
        mt = manifest.get('mediaType', '')

        if 'manifest.list' in mt or 'index' in mt:
            # Multi-arch: extract amd64 digest
            manifests = manifest.get('manifests', [])
            amd64 = [m for m in manifests
                     if m.get('platform', {}).get('architecture') == 'amd64']
            if amd64:
                digest = amd64[0]['digest']
            else:
                return (base_image, latest_tag, None, 'no amd64 in manifest list')
        else:
            # Single manifest: compute digest from the raw bytes
            import hashlib
            raw_bytes = inspect.stdout.encode('utf-8')
            digest = 'sha256:' + hashlib.sha256(raw_bytes).hexdigest()

        return (base_image, latest_tag, digest, None)

    except Exception as e:
        return (base_image, None, None, str(e)[:100])


print("\nFinding latest tags via skopeo...")
tag_results = {}
done = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(get_latest_tag, scan_base_map.get(base, base)): base for base in base_map}
    for f in as_completed(futs):
        base = futs[f]
        _base, tag, digest, err = f.result()
        tag_results[base] = {'tag': tag, 'digest': digest, 'error': err}
        done += 1
        if done % 20 == 0 or done == len(base_map):
            errs = sum(1 for v in tag_results.values() if v['error'])
            print(f"  {done}/{len(base_map)} ({errs} errors)")

success = {k: v for k, v in tag_results.items() if not v['error']}
errors = {k: v for k, v in tag_results.items() if v['error']}
print(f"\n  Success: {len(success)}, Errors: {len(errors)}")
for base, info in list(errors.items())[:5]:
    print(f"    {base}: {info['error']}")

# ── Step 2: Scan latest images with roxctl ──


def scan_latest(base_image, digest):
    """Scan the latest image digest with roxctl."""
    ref = f"{base_image}@{digest}"
    try:
        env = os.environ.copy()
        env['ROX_ENDPOINT'] = ROX_ENDPOINT
        cmd = ['roxctl', 'image', 'scan', '--image', ref, '--output', 'json']
        if INSECURE:
            cmd.insert(3, '--insecure-skip-tls-verify')
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, env=env,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return (base_image, data.get('result', {}))
        return (base_image, {'error': result.stderr[:200]})
    except Exception as e:
        return (base_image, {'error': str(e)[:200]})


to_scan = {base: info for base, info in tag_results.items()
           if info['digest'] and not info['error']}
print(f"\nScanning {len(to_scan)} latest images with roxctl...")

latest_scans = {}
done = 0
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(scan_latest, scan_base_map.get(base, base), info['digest']): base
            for base, info in to_scan.items()}
    for f in as_completed(futs):
        base = futs[f]
        _base, result = f.result()
        latest_scans[base] = result
        done += 1
        if done % 20 == 0 or done == len(to_scan):
            errs = sum(1 for v in latest_scans.values() if 'error' in v)
            print(f"  {done}/{len(to_scan)} ({errs} scan errors)")

scan_ok = sum(1 for v in latest_scans.values() if 'error' not in v)
print(f"  Scanned OK: {scan_ok}")

if scan_ok == 0 and latest_scans:
    print("WARNING: All roxctl scans failed — cannot determine fix status")
    print("  Check that the RHACS API token has Image write permissions")
    sample_err = next((v['error'] for v in latest_scans.values() if 'error' in v), '')
    if sample_err:
        print(f"  Sample error: {sample_err[:200]}")

# ── Step 3: Compare current vs latest to find fixed CVEs ──
print("\nComparing current vs latest scans...")

# Build lookup: for each latest scan, what CVEs are present
latest_cve_lookup = {}  # base -> set of CVE IDs
for base, result in latest_scans.items():
    if 'error' in result:
        continue
    cves = set()
    for v in result.get('vulnerabilities', []):
        cves.add(v.get('cveId', ''))
    latest_cve_lookup[base] = cves

# For each triage record, determine if the CVE is fixed in latest
fix_results = {}  # key: (image_full, cve) -> {fixed: bool, latest_digest: str, latest_tag: str, catalog_url: str}

for base, info in base_map.items():
    tag_info = tag_results.get(base, {})
    latest_tag = tag_info.get('tag', '')
    latest_digest = tag_info.get('digest', '')
    latest_cves = latest_cve_lookup.get(base, None)

    # Build catalog URL (use scan base for public registry path)
    catalog_url = ''
    sb = scan_base_map.get(base, base)
    if 'registry.redhat.io/' in sb:
        repo_path = sb.replace('registry.redhat.io/', '')
        catalog_url = f"https://catalog.redhat.com/software/containers/{repo_path}"
    elif 'quay.io/' in sb:
        repo_path = sb.replace('quay.io/', '')
        catalog_url = f"https://quay.io/repository/{repo_path}"

    for entry in info['cves']:
        key = f"{entry['image_full']}|||{entry['cve']}"

        if latest_cves is None:
            fix_results[key] = {
                'status': 'SCAN_UNAVAILABLE',
                'latest_ref': '',
                'latest_tag': latest_tag or '',
                'catalog_url': catalog_url,
            }
        elif entry['cve'] in latest_cves:
            fix_results[key] = {
                'status': 'STILL_VULNERABLE',
                'latest_ref': f"{sb}@{latest_digest}" if latest_digest else '',
                'latest_tag': latest_tag or '',
                'catalog_url': catalog_url,
            }
        else:
            fix_results[key] = {
                'status': 'FIXED_IN_LATEST',
                'latest_ref': f"{sb}@{latest_digest}" if latest_digest else '',
                'latest_tag': latest_tag or '',
                'catalog_url': catalog_url,
            }

# Stats
statuses = Counter(v['status'] for v in fix_results.values())
print(f"\nResults across {len(fix_results)} CVE+image records:")
for status, count in statuses.most_common():
    print(f"  {status}: {count}")

# Save
with open(OUTPUT, 'w') as f:
    json.dump({
        'fix_results': fix_results,
        'tag_info': tag_results,
        'scan_base_map': scan_base_map,
    }, f)

print(f"\nSaved to {OUTPUT} ({os.path.getsize(OUTPUT) / 1024:.0f} KB)")
