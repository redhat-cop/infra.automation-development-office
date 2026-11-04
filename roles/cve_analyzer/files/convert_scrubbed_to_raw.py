#!/usr/bin/env python3
"""Map RHACS scrubbed CSV (acs_report mode=all) to cve-analyzer raw.csv format."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

RAW_FIELDS = [
    "CVE",
    "Image",
    "Namespace",
    "Deployment",
    "Component",
    "Component Version",
    "Cluster",
    "Severity",
    "CVSS",
    "NVDCVSS",
    "EPSS Probability Percentage",
    "CVE Fixed In",
    "Advisory Name",
    "Advisory Link",
    "Reference",
]

MAP = {
    "ComponentVersion": "Component Version",
    "FixedBy": "CVE Fixed In",
    "Advisory": "Advisory Name",
    "Link": "Reference",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("scrubbed_csv")
    p.add_argument("raw_csv")
    args = p.parse_args()
    src = Path(args.scrubbed_csv)
    dst = Path(args.raw_csv)
    rows_out = []
    with src.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out = {f: "" for f in RAW_FIELDS}
            for k, v in row.items():
                target = MAP.get(k, k)
                if target in out:
                    out[target] = v or ""
            out["Advisory Link"] = out.get("Reference", "")
            if not out.get("EPSS Probability Percentage"):
                out["EPSS Probability Percentage"] = "0"
            if not out.get("NVDCVSS"):
                out["NVDCVSS"] = "0"
            rows_out.append(out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RAW_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)
    print(f"Wrote {len(rows_out)} rows to {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
