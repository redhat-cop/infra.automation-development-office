#!/usr/bin/env python3
"""Match published Red Hat CVEs against RHACS CSV findings.

Reads:
  CVE_INTEL_PUBLISHED_JSON  — output of collect_rh_published_cves.py
  CVE_INTEL_RHACS_CSV       — scrubbed/raw RHACS CSV with a CVE column
  CVE_INTEL_MATCH_OUT       — output JSON (default beside published JSON)

Optional Postgres upsert when CVE_INTEL_DATABASE_URL is set.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


CVE_COLUMNS = ("CVE", "cve", "CVE ID", "Cve", "Vulnerability ID")
CLUSTER_COLUMNS = ("Cluster", "cluster", "Cluster name")
NS_COLUMNS = ("Namespace", "namespace", "Deployment Namespace")
SEV_COLUMNS = ("Severity", "severity", "CVSS Severity")
IMAGE_COLUMNS = ("Image", "image", "Image Name")
COMPONENT_COLUMNS = ("Component", "component", "Package Name", "Component Name")


def _pick(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
    # case-insensitive fallback
    lower = {k.lower(): v for k, v in row.items()}
    for name in names:
        v = lower.get(name.lower())
        if v and str(v).strip():
            return str(v).strip()
    return ""


def load_published(path: str) -> set[str]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    cves = data.get("cves") if isinstance(data, dict) else data
    out: set[str] = set()
    for row in cves or []:
        if isinstance(row, dict):
            cid = (row.get("cve_id") or row.get("CVE") or "").strip()
            if cid:
                out.add(cid)
        elif isinstance(row, str):
            out.add(row.strip())
    return out


def match_csv(csv_path: str, published: set[str]) -> list[dict[str, Any]]:
    matches: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cve = _pick(row, CVE_COLUMNS)
            if not cve or cve not in published:
                continue
            key = (
                cve,
                _pick(row, CLUSTER_COLUMNS),
                _pick(row, NS_COLUMNS),
                _pick(row, SEV_COLUMNS),
                _pick(row, IMAGE_COLUMNS),
                _pick(row, COMPONENT_COLUMNS),
            )
            if key in matches:
                matches[key]["finding_count"] += 1
            else:
                matches[key] = {
                    "cve_id": key[0],
                    "cluster": key[1],
                    "rhacs_namespace": key[2],
                    "severity": key[3],
                    "image": key[4],
                    "component": key[5],
                    "finding_count": 1,
                }
    return list(matches.values())


def upsert_pipeline_status(
    conn: Any,
    *,
    pipeline: str,
    success_at: str,
    input_count: int,
    output_count: int,
    details: dict[str, Any] | None = None,
) -> None:
    sql = """
    INSERT INTO cve_intel.pipeline_status (
        pipeline, last_success_at, last_input_count, last_output_count, details
    ) VALUES (
        %(pipeline)s, %(success_at)s, %(input_count)s, %(output_count)s, %(details)s::jsonb
    )
    ON CONFLICT (pipeline) DO UPDATE SET
        last_success_at = EXCLUDED.last_success_at,
        last_input_count = EXCLUDED.last_input_count,
        last_output_count = EXCLUDED.last_output_count,
        details = EXCLUDED.details
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "pipeline": pipeline,
                "success_at": success_at,
                "input_count": input_count,
                "output_count": output_count,
                "details": json.dumps(details or {}),
            },
        )
    conn.commit()


def upsert_matches(conn: Any, rows: list[dict[str, Any]], detected_at: str) -> int:
    """Idempotent upsert. finding_count is replaced (not summed) so re-runs do not duplicate."""
    if not rows:
        return 0
    sql = """
    INSERT INTO cve_intel.rh_cve_rhacs_match (
        cve_id, cluster, rhacs_namespace, severity, image, component,
        first_detected_in_rhacs, last_detected_in_rhacs, finding_count
    ) VALUES (
        %(cve_id)s, %(cluster)s, %(rhacs_namespace)s, %(severity)s, %(image)s, %(component)s,
        %(detected_at)s, %(detected_at)s, %(finding_count)s
    )
    ON CONFLICT (cve_id, cluster, rhacs_namespace, severity, image, component) DO UPDATE SET
        last_detected_in_rhacs = EXCLUDED.last_detected_in_rhacs,
        finding_count = EXCLUDED.finding_count
    """
    payload = [{**r, "detected_at": detected_at} for r in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, payload)
    conn.commit()
    return len(payload)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cve: dict[str, int] = defaultdict(int)
    by_cluster: dict[str, int] = defaultdict(int)
    for r in rows:
        by_cve[r["cve_id"]] += r["finding_count"]
        by_cluster[r["cluster"] or "(none)"] += r["finding_count"]
    return {
        "matched_cves": len(by_cve),
        "match_rows": len(rows),
        "findings": sum(r["finding_count"] for r in rows),
        "by_cve": dict(sorted(by_cve.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_cluster": dict(sorted(by_cluster.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def main() -> int:
    published_path = os.environ.get("CVE_INTEL_PUBLISHED_JSON")
    csv_path = os.environ.get("CVE_INTEL_RHACS_CSV")
    if not published_path or not csv_path:
        print(
            "Set CVE_INTEL_PUBLISHED_JSON and CVE_INTEL_RHACS_CSV",
            file=sys.stderr,
        )
        return 2
    out_path = os.environ.get("CVE_INTEL_MATCH_OUT") or os.path.join(
        os.path.dirname(published_path) or ".",
        "cve_intel_rhacs_matches.json",
    )
    published = load_published(published_path)
    print(f"Published CVE set: {len(published)}")
    rows = match_csv(csv_path, published)
    detected_at = datetime.now(timezone.utc).isoformat()
    summary = summarize(rows)
    payload = {
        "matched_at": detected_at,
        "published_json": published_path,
        "rhacs_csv": csv_path,
        "summary": summary,
        "matches": rows,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(
        f"Wrote {out_path}: {summary['matched_cves']} CVE(s), "
        f"{summary['findings']} finding(s)"
    )

    db_url = os.environ.get("CVE_INTEL_DATABASE_URL") or ""
    if db_url:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(db_url)
        try:
            n = upsert_matches(conn, rows, detected_at)
            print(f"Upserted {n} match row(s)")
            upsert_pipeline_status(
                conn,
                pipeline="rhacs_match",
                success_at=detected_at,
                input_count=len(published),
                output_count=len(rows),
                details={
                    "rhacs_csv": csv_path,
                    "matched_cves": summary["matched_cves"],
                    "findings": summary["findings"],
                },
            )
            print("Updated pipeline_status rhacs_match")
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
