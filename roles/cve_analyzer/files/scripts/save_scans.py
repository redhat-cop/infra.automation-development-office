"""Save roxctl scan results to JSON for the report builder."""
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
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, "roxctl_scan_results.json")
ROX_TOKEN = os.environ.get('ROX_API_TOKEN', '')

if not ROX_ENDPOINT or ROX_ENDPOINT in (':443', '://'):
    print(f"WARNING: ROX_ENDPOINT looks invalid ({ROX_ENDPOINT!r}); scans will fail")
if not ROX_TOKEN:
    print("WARNING: ROX_API_TOKEN unset — roxctl scans will be SCAN_UNAVAILABLE")
else:
    print(f"ROX_ENDPOINT={ROX_ENDPOINT} token_len={len(ROX_TOKEN)}")

scan_map = {}
for row in csv.DictReader(open(TRIAGE_CSV)):
    img = row['Image_Full']
    if img not in scan_map:
        scan_map[img] = row.get('Scan_Image', '') or img
unique_images = sorted(scan_map.keys())
print(f"{len(unique_images)} images to scan")


def scan_image(image_ref):
    try:
        env = os.environ.copy()
        env['ROX_ENDPOINT'] = ROX_ENDPOINT
        cmd = ['roxctl', 'image', 'scan', '--image', image_ref, '--output', 'json']
        if INSECURE:
            cmd.insert(3, '--insecure-skip-tls-verify')
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=60, env=env,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return (image_ref, data.get('result', {}))
        return (image_ref, {'error': result.stderr[:200]})
    except Exception as e:
        return (image_ref, {'error': str(e)[:200]})


results = {}
done = 0
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(scan_image, scan_map[img]): img for img in unique_images}
    for f in as_completed(futs):
        img = futs[f]
        _img, data = f.result()
        results[img] = data
        done += 1
        if done % 50 == 0 or done == len(unique_images):
            errs = sum(1 for v in results.values() if 'error' in v)
            print(f"  {done}/{len(unique_images)} ({errs} errors)")

with open(OUTPUT_JSON, 'w') as f:
    json.dump(results, f)

size = os.path.getsize(OUTPUT_JSON) / 1024 / 1024
print(f"\nSaved to {OUTPUT_JSON} ({size:.1f} MB)")
