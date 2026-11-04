#!/usr/bin/env python3
"""Collect newly published Red Hat CVEs from the Security Data API.

Independent of RHACS Panel 11 / Testdata. Writes a JSON snapshot and optionally
upserts into Grafana PostgreSQL when CVE_INTEL_DATABASE_URL is set.

Env:
  CVE_INTEL_AFTER          YYYY-MM-DD (default: today-14d UTC)
  CVE_INTEL_BEFORE         YYYY-MM-DD optional
  CVE_INTEL_PER_PAGE       default 100
  CVE_INTEL_FETCH_DETAILS  1/0 (default 1) — enrich products/advisories
  CVE_INTEL_OUT            output JSON path
  CVE_INTEL_DATABASE_URL   optional postgresql://...
  CVE_INTEL_SCHEMA_SQL     path to schema.sql (applied when DB URL set)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

BASE = "https://access.redhat.com/hydra/rest/securitydata"
UA = "ado-cve-intel/0.1 (+lab CVE Analyzer)"


def _utc_today() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_day(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("empty date")
    # Accept YYYY-MM-DD
    datetime.strptime(value[:10], "%Y-%m-%d")
    return value[:10]


def default_after_day(days: int = 14) -> str:
    return (_utc_today() - timedelta(days=days)).strftime("%Y-%m-%d")


def http_get_json(url: str, timeout: int = 60) -> Any:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return []
        return json.loads(raw.decode("utf-8"))


def list_cves(
    *,
    after: str,
    before: str | None = None,
    per_page: int = 100,
    max_pages: int = 200,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params: dict[str, str] = {
            "after": after,
            "per_page": str(per_page),
            "page": str(page),
        }
        if before:
            params["before"] = before
        url = f"{BASE}/cve.json?{urllib.parse.urlencode(params)}"
        batch = http_get_json(url)
        if not isinstance(batch, list):
            raise RuntimeError(f"unexpected list payload type: {type(batch)}")
        if not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        time.sleep(0.05)
    else:
        print(
            f"WARNING: hit max_pages={max_pages} ({len(out)} CVEs); "
            "increase CVE_INTEL_MAX_PAGES if the window is incomplete",
            file=sys.stderr,
        )
    return out


def fetch_detail(cve_id: str) -> dict[str, Any] | None:
    url = f"{BASE}/cve/{urllib.parse.quote(cve_id)}.json"
    try:
        data = http_get_json(url)
        return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def normalize_severity(value: str | None) -> str:
    v = (value or "").strip().lower()
    mapping = {
        "critical": "Critical",
        "important": "Important",
        "moderate": "Moderate",
        "medium": "Moderate",
        "low": "Low",
        "none": "None",
    }
    return mapping.get(v, (value or "").strip().title() or "Unknown")


def portal_url(cve_id: str) -> str:
    return f"https://access.redhat.com/security/cve/{cve_id.lower()}"


def extract_advisories(detail: dict[str, Any] | None, list_row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for adv in list_row.get("advisories") or []:
        if isinstance(adv, str) and adv and adv not in found:
            found.append(adv)
    if detail:
        for rel in detail.get("affected_release") or []:
            if not isinstance(rel, dict):
                continue
            adv = rel.get("advisory")
            if isinstance(adv, str) and adv and adv not in found:
                found.append(adv)
    return found


def extract_products(detail: dict[str, Any] | None) -> list[str]:
    names: list[str] = []
    if not detail:
        return names
    for bucket in ("affected_release", "package_state"):
        for row in detail.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            name = row.get("product_name")
            if isinstance(name, str) and name and name not in names:
                names.append(name)
    return names


def normalize_record(
    list_row: dict[str, Any],
    detail: dict[str, Any] | None,
    *,
    collected_at: str,
) -> dict[str, Any]:
    cve_id = (list_row.get("CVE") or list_row.get("name") or "").strip()
    if not cve_id:
        raise ValueError("list row missing CVE id")

    severity = normalize_severity(
        (detail or {}).get("threat_severity")
        or list_row.get("severity")
        or list_row.get("threat_severity")
    )
    public_date = (
        (detail or {}).get("public_date")
        or list_row.get("public_date")
        or None
    )
    cvss3 = (detail or {}).get("cvss3") if isinstance((detail or {}).get("cvss3"), dict) else {}
    bz = (detail or {}).get("bugzilla") if isinstance((detail or {}).get("bugzilla"), dict) else {}

    details_text = ""
    raw_details = (detail or {}).get("details")
    if isinstance(raw_details, list) and raw_details:
        details_text = " ".join(str(x) for x in raw_details if x)
    elif isinstance(raw_details, str):
        details_text = raw_details
    if not details_text:
        details_text = (
            list_row.get("bugzilla_description")
            or bz.get("description")
            or ""
        )

    advisories = extract_advisories(detail, list_row)
    products = extract_products(detail)

    return {
        "cve_id": cve_id,
        "threat_severity": severity,
        "public_date": public_date,
        "first_seen_at": collected_at,
        "first_collected_at": collected_at,
        "last_collected_at": collected_at,
        "bugzilla_id": str(bz.get("id") or list_row.get("bugzilla") or "") or None,
        "bugzilla_description": (
            list_row.get("bugzilla_description")
            or bz.get("description")
            or None
        ),
        "cvss3_score": _float_or_none(
            cvss3.get("cvss3_base_score")
            if cvss3
            else list_row.get("cvss3_score")
        ),
        "cvss3_vector": (
            cvss3.get("cvss3_scoring_vector")
            if cvss3
            else list_row.get("cvss3_scoring_vector")
        ),
        "cwe": (
            (detail or {}).get("cwe")
            or list_row.get("CWE")
            or None
        ),
        "statement": (detail or {}).get("statement")
        if isinstance((detail or {}).get("statement"), str)
        else None,
        "details": details_text or None,
        "resource_url": list_row.get("resource_url")
        or f"{BASE}/cve/{cve_id}.json",
        "portal_url": portal_url(cve_id),
        "advisories": advisories,
        "advisory_urls": [
            f"https://access.redhat.com/errata/{a}" for a in advisories
        ],
        "products": products,
        "package_states": (detail or {}).get("package_state") or [],
        "raw_list": list_row,
        "raw_detail": detail,
    }


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def apply_schema(conn: Any, schema_path: str) -> None:
    with open(schema_path, encoding="utf-8") as fh:
        sql = fh.read()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        # Tables may already exist and be owned by another role; upsert can proceed.
        print(f"WARNING: schema apply skipped/partial: {exc}")


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


def upsert_records(conn: Any, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    sql = """
    INSERT INTO cve_intel.rh_cve_published (
        cve_id, threat_severity, public_date, first_seen_at, first_collected_at, last_collected_at,
        bugzilla_id, bugzilla_description, cvss3_score, cvss3_vector, cwe,
        statement, details, resource_url, portal_url,
        advisories, products, package_states, raw_list, raw_detail
    ) VALUES (
        %(cve_id)s, %(threat_severity)s, %(public_date)s, %(first_seen_at)s, %(first_collected_at)s, %(last_collected_at)s,
        %(bugzilla_id)s, %(bugzilla_description)s, %(cvss3_score)s, %(cvss3_vector)s, %(cwe)s,
        %(statement)s, %(details)s, %(resource_url)s, %(portal_url)s,
        %(advisories)s::jsonb, %(products)s::jsonb, %(package_states)s::jsonb,
        %(raw_list)s::jsonb, %(raw_detail)s::jsonb
    )
    ON CONFLICT (cve_id) DO UPDATE SET
        threat_severity = EXCLUDED.threat_severity,
        public_date = COALESCE(cve_intel.rh_cve_published.public_date, EXCLUDED.public_date),
        first_seen_at = cve_intel.rh_cve_published.first_seen_at,
        first_collected_at = cve_intel.rh_cve_published.first_collected_at,
        last_collected_at = EXCLUDED.last_collected_at,
        bugzilla_id = COALESCE(EXCLUDED.bugzilla_id, cve_intel.rh_cve_published.bugzilla_id),
        bugzilla_description = COALESCE(EXCLUDED.bugzilla_description, cve_intel.rh_cve_published.bugzilla_description),
        cvss3_score = COALESCE(EXCLUDED.cvss3_score, cve_intel.rh_cve_published.cvss3_score),
        cvss3_vector = COALESCE(EXCLUDED.cvss3_vector, cve_intel.rh_cve_published.cvss3_vector),
        cwe = COALESCE(EXCLUDED.cwe, cve_intel.rh_cve_published.cwe),
        statement = COALESCE(EXCLUDED.statement, cve_intel.rh_cve_published.statement),
        details = COALESCE(EXCLUDED.details, cve_intel.rh_cve_published.details),
        resource_url = COALESCE(EXCLUDED.resource_url, cve_intel.rh_cve_published.resource_url),
        portal_url = COALESCE(EXCLUDED.portal_url, cve_intel.rh_cve_published.portal_url),
        advisories = EXCLUDED.advisories,
        products = EXCLUDED.products,
        package_states = EXCLUDED.package_states,
        raw_list = EXCLUDED.raw_list,
        raw_detail = COALESCE(EXCLUDED.raw_detail, cve_intel.rh_cve_published.raw_detail)
    """
    payload = []
    for rec in records:
        row = dict(rec)
        row["advisories"] = json.dumps(rec.get("advisories") or [])
        row["products"] = json.dumps(rec.get("products") or [])
        row["package_states"] = json.dumps(rec.get("package_states") or [])
        row["raw_list"] = json.dumps(rec.get("raw_list") or {})
        row["raw_detail"] = json.dumps(rec.get("raw_detail")) if rec.get("raw_detail") is not None else None
        payload.append(row)
    with conn.cursor() as cur:
        cur.executemany(sql, payload)
    conn.commit()
    return len(payload)


def daily_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = {}
    for rec in records:
        raw = rec.get("public_date") or ""
        day = str(raw)[:10] if raw else "unknown"
        b = buckets.setdefault(
            day,
            {"pub_day": day, "total": 0, "Critical": 0, "Important": 0, "Moderate": 0, "Low": 0},
        )
        b["total"] += 1
        sev = rec.get("threat_severity") or "Unknown"
        if sev in b:
            b[sev] += 1
    return [buckets[k] for k in sorted(buckets.keys(), reverse=True)]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    after = os.environ.get("CVE_INTEL_AFTER") or (
        _parse_day(argv[0]) if argv else default_after_day(14)
    )
    before = os.environ.get("CVE_INTEL_BEFORE") or None
    per_page = int(os.environ.get("CVE_INTEL_PER_PAGE") or "100")
    max_pages = int(os.environ.get("CVE_INTEL_MAX_PAGES") or "200")
    fetch_details = os.environ.get("CVE_INTEL_FETCH_DETAILS", "1") not in ("0", "false", "False")
    out_path = os.environ.get("CVE_INTEL_OUT") or os.path.join(
        os.environ.get("CVE_DATA_DIR") or "/tmp",
        "cve_intel_published.json",
    )
    db_url = os.environ.get("CVE_INTEL_DATABASE_URL") or ""
    schema_path = os.environ.get("CVE_INTEL_SCHEMA_SQL") or os.path.join(
        os.path.dirname(__file__), "schema.sql"
    )

    collected_at = datetime.now(timezone.utc).isoformat()
    print(f"Collecting Red Hat CVEs after={after} before={before or '-'} details={fetch_details}")
    listed = list_cves(
        after=after, before=before, per_page=per_page, max_pages=max_pages
    )
    print(f"List API returned {len(listed)} CVE(s)")

    records: list[dict[str, Any]] = []
    for i, row in enumerate(listed, 1):
        cve_id = (row.get("CVE") or "").strip()
        detail = None
        if fetch_details and cve_id:
            detail = fetch_detail(cve_id)
            if i % 25 == 0 or i == len(listed):
                print(f"  details {i}/{len(listed)}")
            time.sleep(0.03)
        records.append(normalize_record(row, detail, collected_at=collected_at))

    summary = daily_summary(records)
    payload = {
        "collected_at": collected_at,
        "after": after,
        "before": before,
        "count": len(records),
        "daily_summary": summary,
        "cves": records,
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"Wrote {out_path} ({len(records)} CVEs)")
    for day in summary[:7]:
        print(
            f"  {day['pub_day']}: total={day['total']} "
            f"C={day['Critical']} I={day['Important']} M={day['Moderate']} L={day['Low']}"
        )

    if db_url:
        try:
            import psycopg2  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "CVE_INTEL_DATABASE_URL set but psycopg2 is not installed"
            ) from exc
        conn = psycopg2.connect(db_url)
        try:
            apply_schema(conn, schema_path)
            n = upsert_records(conn, records)
            print(f"Upserted {n} row(s) into rh_cve_published")
            upsert_pipeline_status(
                conn,
                pipeline="rh_security_data",
                success_at=collected_at,
                input_count=len(listed),
                output_count=len(records),
                details={"after": after, "before": before, "fetch_details": fetch_details},
            )
            print("Updated pipeline_status rh_security_data")
        finally:
            conn.close()
    else:
        print("No CVE_INTEL_DATABASE_URL — JSON snapshot only")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
