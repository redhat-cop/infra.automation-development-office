"""Fetch CVSS scores from Red Hat CVE database and save to JSON."""

from collections import Counter
import csv
import json
import os
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
OUTPUT = os.path.join(DATA_DIR, "redhat_cve_scores.json")

rows = list(csv.DictReader(open(TRIAGE_CSV)))
cves = sorted(set(r['CVE'] for r in rows if r['CVE'].startswith('CVE-')))
print(f"{len(cves)} unique CVEs to fetch from Red Hat")


def fetch_rh_cve(cve_id):
    url = f"https://access.redhat.com/hydra/rest/securitydata/cve/{cve_id}.json"
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            cvss3 = data.get('cvss3', {})
            mitigation = data.get('mitigation', {})
            mit_text = mitigation.get('value', '') if isinstance(mitigation, dict) else ''
            statement = data.get('statement', '')
            return (cve_id, {
                'score': float(cvss3.get('cvss3_base_score', 0) or 0),
                'vector': cvss3.get('cvss3_scoring_vector', ''),
                'severity': data.get('threat_severity', ''),
                'status': cvss3.get('status', ''),
                'mitigation': mit_text,
                'statement': statement if isinstance(statement, str) else '',
            })
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (cve_id, {'score': 0, 'vector': '', 'severity': '', 'status': 'not_found', 'mitigation': '', 'statement': ''})
        return (cve_id, {'score': 0, 'vector': '', 'severity': '', 'status': f'http_{e.code}', 'mitigation': '', 'statement': ''})
    except Exception as e:
        return (cve_id, {'score': 0, 'vector': '', 'severity': '', 'status': f'error: {str(e)[:60]}', 'mitigation': '', 'statement': ''})


results = {}
done = 0
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(fetch_rh_cve, cve): cve for cve in cves}
    for f in as_completed(futs):
        cve_id, data = f.result()
        results[cve_id] = data
        done += 1
        if done % 40 == 0 or done == len(cves):
            print(f"  {done}/{len(cves)} fetched")

with open(OUTPUT, 'w') as f:
    json.dump(results, f, indent=2)

# Summary
scores = [v['score'] for v in results.values()]
found = sum(1 for s in scores if s > 0)
not_found = sum(1 for v in results.values() if v['status'] == 'not_found')
errors = sum(1 for v in results.values() if v['status'].startswith('error') or v['status'].startswith('http_'))
print(f"\nResults: {found} with scores, {not_found} not found, {errors} errors")
positive = [s for s in scores if s > 0]
if positive:
    print(f"Score range: {min(positive):.1f} - {max(scores):.1f}")
else:
    print("Score range: n/a (no CVE scores yet)")

# Severity breakdown from Red Hat
sevs = Counter(v['severity'] for v in results.values() if v['severity'])
print(f"Red Hat severities: {dict(sevs)}")
