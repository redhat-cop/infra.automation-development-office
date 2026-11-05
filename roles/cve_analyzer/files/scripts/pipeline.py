"""
Pipeline orchestrator: runs all enrichment steps in order for a given data directory.

Usage: python3 pipeline.py DATA_DIR
  DATA_DIR must contain raw.csv (the RHACS export).
  All intermediate and final outputs are written to DATA_DIR.
  Progress is written to DATA_DIR/status.json.
"""

import json
import os
import subprocess
import sys
import time

if len(sys.argv) < 2:
    print("Usage: pipeline.py DATA_DIR")
    sys.exit(1)

DATA_DIR = sys.argv[1]
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(DATA_DIR, "status.json")

STEPS = [
    ("Preparing triage report", "prepare_triage.py"),
    ("Scanning images with roxctl", "save_scans.py"),
    ("Fetching Red Hat CVSS scores", "fetch_rh_scores.py"),
    ("Scanning latest image versions", "scan_latest.py"),
    ("Scanning OCP core images", "scan_ocp_latest.py"),
    ("Fixing catalog URLs", "fix_catalog_urls.py"),
    ("Fixing manifest digests", "fix_manifest_digests.py"),
    ("Fetching RHSA descriptions", "fetch_rhsa_descriptions.py"),
    ("Checking CISA KEV catalog", "fetch_kev.py"),
    ("Building HTML report", "build_report_v2.py"),
]


def update_status(step_idx, step_name, state, error=None):
    status = {
        "current_step": step_idx,
        "total_steps": len(STEPS),
        "step_name": step_name,
        "state": state,
        "error": error,
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f)


def run_step(idx, name, script):
    script_path = os.path.join(SCRIPTS_DIR, script)
    if not os.path.exists(script_path):
        print(f"  SKIP: {script} not found")
        return True

    print(f"\n{'=' * 60}")
    print(f"Step {idx + 1}/{len(STEPS)}: {name}")
    print(f"{'=' * 60}")
    update_status(idx + 1, name, "running")

    env = os.environ.copy()
    env['CVE_DATA_DIR'] = DATA_DIR

    result = subprocess.run(
        [sys.executable, script_path, DATA_DIR],
        env=env, timeout=1800,
        check=False,
    )

    if result.returncode != 0:
        update_status(idx + 1, name, "error", f"Exit code {result.returncode}")
        return False
    return True


print(f"Pipeline starting: {DATA_DIR}")
print(f"Raw CSV: {os.path.join(DATA_DIR, 'raw.csv')}")

if not os.path.exists(os.path.join(DATA_DIR, 'raw.csv')):
    print("ERROR: raw.csv not found in DATA_DIR")
    update_status(0, "Initialization", "error", "raw.csv not found")
    sys.exit(1)

update_status(0, "Initializing", "running")

for idx, (name, script) in enumerate(STEPS):
    ok = run_step(idx, name, script)
    if not ok:
        print(f"\nPipeline FAILED at step {idx + 1}: {name}")
        sys.exit(1)

update_status(len(STEPS), "Complete", "complete")
print(f"\n{'=' * 60}")
print("Pipeline COMPLETE")
print(f"Report: {os.path.join(DATA_DIR, 'report.html')}")
print(f"{'=' * 60}")
