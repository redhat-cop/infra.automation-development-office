#!/usr/bin/env python3
"""Check CVEs against the CISA Known Exploited Vulnerabilities catalog."""

import csv
import json
import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
OUTPUT = os.path.join(DATA_DIR, "kev_matches.json")

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

print("Downloading CISA KEV catalog...")
req = urllib.request.Request(KEV_URL, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as resp:
    kev_data = json.loads(resp.read())

kev_lookup = {}
for v in kev_data.get('vulnerabilities', []):
    kev_lookup[v['cveID']] = {
        'dateAdded': v.get('dateAdded', ''),
        'dueDate': v.get('dueDate', ''),
        'requiredAction': v.get('requiredAction', ''),
        'vulnerabilityName': v.get('vulnerabilityName', ''),
        'ransomwareUse': v.get('knownRansomwareCampaignUse', ''),
    }

print(f"  KEV catalog: {len(kev_lookup)} entries")

rows = list(csv.DictReader(open(TRIAGE_CSV)))
cves = sorted(set(r['CVE'] for r in rows if r['CVE'].startswith('CVE-')))

matches = {}
for cve in cves:
    if cve in kev_lookup:
        matches[cve] = kev_lookup[cve]

print(f"  Matched: {len(matches)} CVEs in KEV catalog")
if matches:
    for cve, info in sorted(matches.items()):
        ransomware = " [RANSOMWARE]" if info['ransomwareUse'] == 'Known' else ""
        print(f"    {cve}: added {info['dateAdded']}, due {info['dueDate']}{ransomware}")

with open(OUTPUT, 'w') as f:
    json.dump(matches, f, indent=2)
