"""Fetch Pyxis repository IDs and fix catalog.redhat.com URLs."""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
LATEST_JSON = os.path.join(DATA_DIR, "latest_scan_results.json")

data = json.load(open(LATEST_JSON))
fr = data['fix_results']

# Collect unique repo paths
repo_paths = set()
for v in fr.values():
    cat = v.get('catalog_url', '')
    if 'catalog.redhat.com/software/containers/' in cat and '/errata/' not in cat:
        path = cat.replace('https://catalog.redhat.com/software/containers/', '')
        repo_paths.add(path)

print(f"{len(repo_paths)} repos to look up in Pyxis")


def fetch_pyxis_id(repo_path):
    """Fetch the Pyxis _id for a repository."""
    encoded = urllib.parse.quote(repo_path, safe='')
    url = f"https://catalog.redhat.com/api/containers/v1/repositories?filter=repository=={repo_path}"
    try:
        req = urllib.request.Request(url, headers={
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read())
            items = d.get('data', [])
            if items:
                return (repo_path, items[0].get('_id', ''))
            return (repo_path, '')
    except Exception as e:
        return (repo_path, f'ERROR:{str(e)[:60]}')


pyxis_ids = {}
done = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(fetch_pyxis_id, rp): rp for rp in repo_paths}
    for f in as_completed(futs):
        rp, pid = f.result()
        pyxis_ids[rp] = pid
        done += 1
        if done % 20 == 0 or done == len(repo_paths):
            print(f"  {done}/{len(repo_paths)}")

found = sum(1 for v in pyxis_ids.values() if v and not v.startswith('ERROR'))
errors = sum(1 for v in pyxis_ids.values() if v.startswith('ERROR'))
missing = sum(1 for v in pyxis_ids.values() if not v)
print(f"\nFound: {found}, Missing: {missing}, Errors: {errors}")

if errors:
    for rp, pid in pyxis_ids.items():
        if pid.startswith('ERROR'):
            print(f"  {rp}: {pid}")

# Update all catalog URLs
updated = 0
for v in fr.values():
    cat = v.get('catalog_url', '')
    if 'catalog.redhat.com/software/containers/' in cat and '/errata/' not in cat:
        path = cat.replace('https://catalog.redhat.com/software/containers/', '')
        pid = pyxis_ids.get(path, '')
        if pid and not pid.startswith('ERROR'):
            v['catalog_url'] = f"https://catalog.redhat.com/en/software/containers/{path}/{pid}"
            updated += 1

print(f"\nUpdated {updated} catalog URLs")

# Save
with open(LATEST_JSON, 'w') as f:
    json.dump(data, f)

# Verify
sample = [(k, v) for k, v in fr.items() if 'FIXED' in v.get('status', '') and v.get('catalog_url', '')]
for k, v in sample[:3]:
    print(f"  {v['catalog_url']}")

print(f"\nSaved to {LATEST_JSON}")
