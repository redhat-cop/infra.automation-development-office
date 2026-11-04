#!/usr/bin/env python3
"""Build Prometheus metrics for per-namespace CVE counts from data.json.

Emits:
  cve_triage_severity_total{namespace,severity}
  cve_triage_unique_cves{namespace}

severity uses ACS labels (Critical/Important/Moderate/Low). Dev Spaces maps
Important → High in the panel query.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def row_severity(row: dict) -> str:
    sev = (row.get("severity") or row.get("rh_severity") or "").strip()
    if not sev:
        return "Unknown"
    # Normalize common ACS spellings
    u = sev.upper()
    if u in ("CRITICAL",):
        return "Critical"
    if u in ("IMPORTANT", "HIGH"):
        return "Important"
    if u in ("MODERATE", "MEDIUM"):
        return "Moderate"
    if u in ("LOW",):
        return "Low"
    return sev.title()


def row_namespaces(row: dict) -> list[str]:
    raw = row.get("namespaces") or row.get("Namespace") or ""
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    parts = [p.strip() for p in str(raw).replace(",", ";").split(";")]
    return [p for p in parts if p]


def esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def build_metrics(rows: list) -> str:
    sev_counts: Counter = Counter()
    unique: dict[str, set] = defaultdict(set)
    for row in rows:
        if not isinstance(row, dict):
            continue
        cve = str(row.get("cve") or "")
        sev = row_severity(row)
        for ns in row_namespaces(row):
            sev_counts[(ns, sev)] += 1
            if cve:
                unique[ns].add(cve)

    lines = [
        "# HELP cve_triage_severity_total CVE findings by namespace and severity (from CVE Analyzer triage)",
        "# TYPE cve_triage_severity_total gauge",
    ]
    for (ns, sev), val in sorted(sev_counts.items()):
        lines.append(
            f'cve_triage_severity_total{{namespace="{esc(ns)}",severity="{esc(sev)}"}} {val}'
        )
    lines += [
        "# HELP cve_triage_unique_cves Unique CVE IDs touching a namespace (from CVE Analyzer triage)",
        "# TYPE cve_triage_unique_cves gauge",
    ]
    for ns, cves in sorted(unique.items()):
        lines.append(f'cve_triage_unique_cves{{namespace="{esc(ns)}"}} {len(cves)}')
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_json")
    ap.add_argument("metrics_out")
    args = ap.parse_args()
    rows = json.loads(Path(args.data_json).read_text())
    if not isinstance(rows, list):
        raise SystemExit("data.json must be a list of row objects")
    Path(args.metrics_out).write_text(build_metrics(rows))
    print(f"Wrote {args.metrics_out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
