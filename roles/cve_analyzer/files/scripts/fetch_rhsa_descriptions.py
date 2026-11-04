#!/usr/bin/env python3
"""Fetch RHSA advisory descriptions from Red Hat CSAF data."""

import csv
import json
import os
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
OUTPUT = os.path.join(DATA_DIR, "rhsa_descriptions.json")

rows = list(csv.DictReader(open(TRIAGE_CSV)))
rhsas = sorted(set(r['RHSA_Advisory'] for r in rows if r.get('RHSA_Advisory', '').startswith('RHSA-')))
print(f"{len(rhsas)} unique RHSA advisories to fetch")

if not rhsas:
    with open(OUTPUT, 'w') as f:
        json.dump({}, f)
    print("No RHSA advisories found, skipping")
    sys.exit(0)


def rhsa_to_csaf_url(rhsa_id):
    m = re.match(r'^RHSA-(\d{4}):(\d+)$', rhsa_id)
    if not m:
        return None
    year, num = m.group(1), m.group(2)
    slug = f"rhsa-{year}_{num}"
    return f"https://access.redhat.com/security/data/csaf/v2/advisories/{year}/{slug}.json"


def fetch_rhsa(rhsa_id):
    url = rhsa_to_csaf_url(rhsa_id)
    if not url:
        return (rhsa_id, {'error': 'invalid format'})
    try:
        req = urllib.request.Request(url, headers={
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            doc = data.get('document', {})
            title = doc.get('title', '')
            notes = doc.get('notes', [])
            description = ''
            summary = ''
            for n in notes:
                cat = n.get('category', '')
                if cat == 'general':
                    description = n.get('text', '')
                elif cat == 'summary':
                    summary = n.get('text', '')
            return (rhsa_id, {
                'title': title,
                'description': description or summary,
                'summary': summary,
            })
    except urllib.error.HTTPError as e:
        return (rhsa_id, {'error': f'http_{e.code}'})
    except Exception as e:
        return (rhsa_id, {'error': str(e)[:100]})


results = {}
done = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(fetch_rhsa, rhsa): rhsa for rhsa in rhsas}
    for f in as_completed(futs):
        rhsa_id, data = f.result()
        results[rhsa_id] = data
        done += 1
        if done % 20 == 0 or done == len(rhsas):
            errs = sum(1 for v in results.values() if 'error' in v)
            print(f"  {done}/{len(rhsas)} ({errs} errors)")

ok = sum(1 for v in results.values() if 'error' not in v)
errs = sum(1 for v in results.values() if 'error' in v)
print(f"\nFetched: {ok}, Errors: {errs}")

if errs:
    for rhsa, v in list(results.items())[:5]:
        if 'error' in v:
            print(f"  {rhsa}: {v['error']}")

with open(OUTPUT, 'w') as f:
    json.dump(results, f)
print(f"Saved to {OUTPUT}")
