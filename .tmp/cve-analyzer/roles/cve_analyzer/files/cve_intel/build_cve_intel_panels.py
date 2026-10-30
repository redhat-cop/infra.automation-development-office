#!/usr/bin/env python3
"""Grafana panels for CVE Intelligence — Mythos-style Recent reports.

Per-day rows: DATE | TOTAL | CRITICAL | HIGH | MEDIUM | LOW | NOTE
Severity map (Red Hat → Mythos labels):
  Critical → CRITICAL, Important → HIGH, Moderate → MEDIUM, Low → LOW

Wired into Phase 0 only when ``CVE_ANALYZER_CVE_INTEL_PANELS`` is enabled.
"""

from __future__ import annotations

from typing import Any

POSTGRES_TYPE = "grafana-postgresql-datasource"
DEFAULT_POSTGRES_UID = "ado-grafana-postgres"

_ALL_VAR_SQL = "'$__all', '__ALL__', '.*', ''"
# Inclusive window (8 ≈ Mythos recent-reports screenshot).
DEFAULT_LOOKBACK_DAYS = 8


def _sql_target(uid: str, raw_sql: str, ref_id: str = "A") -> dict[str, Any]:
    return {
        "refId": ref_id,
        "datasource": {"type": POSTGRES_TYPE, "uid": uid},
        "format": "table",
        "rawSql": raw_sql,
        "rawQuery": True,
        "editorMode": "code",
    }


def _portal_link_overrides(*field_names: str) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    for name in field_names:
        overrides.append(
            {
                "matcher": {"id": "byName", "options": name},
                "properties": [
                    {
                        "id": "links",
                        "value": [
                            {
                                "title": "Red Hat CVE portal",
                                "url": "${__data.fields.Portal}",
                                "targetBlank": True,
                            }
                        ],
                    }
                ],
            }
        )
    overrides.append(
        {
            "matcher": {"id": "byName", "options": "Portal"},
            "properties": [{"id": "custom.hidden", "value": True}],
        }
    )
    return overrides


def freshness_panel(
    *,
    y: int,
    postgres_uid: str = DEFAULT_POSTGRES_UID,
    days: int = DEFAULT_LOOKBACK_DAYS,
    grid_w: int = 24,
    grid_h: int = 3,
) -> dict[str, Any]:
    sql = f"""
SELECT
  COALESCE(
    (SELECT last_success_at FROM cve_intel.pipeline_status WHERE pipeline = 'rh_security_data'),
    (SELECT MAX(last_collected_at) FROM cve_intel.rh_cve_published)
  ) AS "RH API last collected",
  (SELECT COUNT(*) FROM cve_intel.rh_cve_published
   WHERE (public_date AT TIME ZONE 'UTC')::date
     >= ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - INTERVAL '{int(days) - 1} days')
  ) AS "Published rows ({days}d)",
  (SELECT last_success_at FROM cve_intel.pipeline_status WHERE pipeline = 'rhacs_match')
    AS "RHACS match last run"
""".strip()
    return {
        "type": "table",
        "title": "CVE Intelligence — freshness",
        "description": "Collector timestamps. Zero-count days in Recent reports are real empty days.",
        "gridPos": {"h": grid_h, "w": grid_w, "x": 0, "y": y},
        "datasource": {"type": POSTGRES_TYPE, "uid": postgres_uid},
        "targets": [_sql_target(postgres_uid, sql)],
        "options": {"showHeader": True, "footer": {"show": False}},
        "fieldConfig": {"defaults": {}, "overrides": []},
    }


def mythos_recent_reports_panel(
    *,
    y: int,
    postgres_uid: str = DEFAULT_POSTGRES_UID,
    days: int = DEFAULT_LOOKBACK_DAYS,
    note_limit: int = 5,
    grid_w: int = 24,
    grid_h: int = 22,
) -> dict[str, Any]:
    """Mythos-like Recent reports: one row per day with severity counts + NOTE list."""
    # generate_series so empty days still appear (like Mythos 10-27 / 10-25).
    # NOTE lists up to note_limit CVEs (Critical/Important first), then +N MORE.
    sql = f"""
WITH days AS (
  SELECT generate_series(
    ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - INTERVAL '{int(days) - 1} days')::date,
    (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date,
    INTERVAL '1 day'
  )::date AS report_day
),
ranked AS (
  SELECT
    (public_date AT TIME ZONE 'UTC')::date AS report_day,
    cve_id,
    threat_severity,
    portal_url,
    LEFT(REGEXP_REPLACE(COALESCE(bugzilla_description, details, ''), E'[\\n\\r]+', ' ', 'g'), 110)
      AS summary,
    CASE lower(threat_severity)
      WHEN 'critical' THEN 0
      WHEN 'important' THEN 1
      WHEN 'moderate' THEN 2
      WHEN 'low' THEN 3
      ELSE 4
    END AS sev_rank,
    CASE lower(threat_severity)
      WHEN 'critical' THEN '🔴'
      WHEN 'important' THEN '🟠'
      WHEN 'moderate' THEN '🟣'
      WHEN 'low' THEN '⚪'
      ELSE '•'
    END AS sev_dot,
    ROW_NUMBER() OVER (
      PARTITION BY (public_date AT TIME ZONE 'UTC')::date
      ORDER BY
        CASE lower(threat_severity)
          WHEN 'critical' THEN 0
          WHEN 'important' THEN 1
          WHEN 'moderate' THEN 2
          WHEN 'low' THEN 3
          ELSE 4
        END,
        public_date DESC,
        cve_id
    ) AS rn,
    COUNT(*) OVER (PARTITION BY (public_date AT TIME ZONE 'UTC')::date) AS day_total
  FROM cve_intel.rh_cve_published
  WHERE public_date IS NOT NULL
    AND (public_date AT TIME ZONE 'UTC')::date
        >= ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - INTERVAL '{int(days) - 1} days')
),
notes AS (
  SELECT
    report_day,
    string_agg(
      sev_dot || ' ' || cve_id || '  ' || summary,
      E'\\n'
      ORDER BY sev_rank, cve_id
    ) AS note_body,
    MAX(day_total) AS day_total
  FROM ranked
  WHERE rn <= {int(note_limit)}
  GROUP BY report_day
),
extras AS (
  SELECT report_day, MAX(day_total) - {int(note_limit)} AS more_n
  FROM ranked
  GROUP BY report_day
  HAVING MAX(day_total) > {int(note_limit)}
),
counts AS (
  SELECT
    (public_date AT TIME ZONE 'UTC')::date AS report_day,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'critical') AS critical,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'important') AS high,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'moderate') AS medium,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'low') AS low
  FROM cve_intel.rh_cve_published
  WHERE public_date IS NOT NULL
    AND (public_date AT TIME ZONE 'UTC')::date
        >= ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - INTERVAL '{int(days) - 1} days')
  GROUP BY 1
)
SELECT
  to_char(d.report_day, 'YYYY-MM-DD') AS "DATE",
  COALESCE(c.total, 0) AS "TOTAL",
  COALESCE(c.critical, 0) AS "CRITICAL",
  COALESCE(c.high, 0) AS "HIGH",
  COALESCE(c.medium, 0) AS "MEDIUM",
  COALESCE(c.low, 0) AS "LOW",
  CASE
    WHEN COALESCE(c.total, 0) = 0 THEN ''
    WHEN e.more_n IS NOT NULL AND e.more_n > 0 THEN
      COALESCE(n.note_body, '') || E'\\n+' || e.more_n::text || ' MORE'
    ELSE COALESCE(n.note_body, '')
  END AS "NOTE"
FROM days d
LEFT JOIN counts c ON c.report_day = d.report_day
LEFT JOIN notes n ON n.report_day = d.report_day
LEFT JOIN extras e ON e.report_day = d.report_day
ORDER BY d.report_day DESC
""".strip()
    # Narrow count columns so they sit close together like Mythos; NOTE gets the rest.
    count_w = 72
    return {
        "type": "table",
        "title": "Recent reports",
        "description": (
            f"Mythos-style daily view (last {days} UTC days by Red Hat public_date). "
            "HIGH = Red Hat Important, MEDIUM = Moderate. "
            "NOTE lists top CVEs (Critical/Important first) then +N MORE. "
            "Totals are full Security Data API publishes for that day — "
            "Mythos Glasswing is curated, so their counts are usually lower."
        ),
        "gridPos": {"h": grid_h, "w": grid_w, "x": 0, "y": y},
        "datasource": {"type": POSTGRES_TYPE, "uid": postgres_uid},
        "targets": [_sql_target(postgres_uid, sql)],
        "options": {
            "showHeader": True,
            "footer": {"show": False},
            "cellHeight": "lg",
        },
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "align": "center",
                    "cellOptions": {"type": "auto", "wrapText": True},
                },
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "DATE"},
                    "properties": [
                        {"id": "custom.width", "value": 118},
                        {"id": "custom.align", "value": "left"},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "TOTAL"},
                    "properties": [
                        {"id": "custom.width", "value": count_w},
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background", "mode": "basic"},
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "transparent", "value": None},
                                    {"color": "#2b2b2b", "value": 0},
                                ],
                            },
                        },
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "CRITICAL"},
                    "properties": [
                        {"id": "custom.width", "value": count_w},
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "#2b2b2b", "value": None},
                                    {"color": "semi-dark-red", "value": 1},
                                ],
                            },
                        },
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background", "mode": "basic"},
                        },
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "HIGH"},
                    "properties": [
                        {"id": "custom.width", "value": count_w},
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "#2b2b2b", "value": None},
                                    {"color": "orange", "value": 1},
                                ],
                            },
                        },
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background", "mode": "basic"},
                        },
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "MEDIUM"},
                    "properties": [
                        {"id": "custom.width", "value": count_w},
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "#2b2b2b", "value": None},
                                    {"color": "purple", "value": 1},
                                ],
                            },
                        },
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background", "mode": "basic"},
                        },
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "LOW"},
                    "properties": [
                        {"id": "custom.width", "value": count_w},
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background", "mode": "basic"},
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "#2b2b2b", "value": None},
                                    {"color": "#3a3a3a", "value": 0},
                                ],
                            },
                        },
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "NOTE"},
                    "properties": [
                        {"id": "custom.align", "value": "left"},
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "auto", "wrapText": True},
                        },
                    ],
                },
            ],
        },
    }


def mythos_day_details_panel(
    *,
    y: int,
    postgres_uid: str = DEFAULT_POSTGRES_UID,
    days: int = DEFAULT_LOOKBACK_DAYS,
    grid_w: int = 24,
    grid_h: int = 12,
) -> dict[str, Any]:
    """Clickable CVE rows for the same window (drill into portal)."""
    sql = f"""
SELECT
  to_char((public_date AT TIME ZONE 'UTC')::date, 'YYYY-MM-DD') AS "DATE",
  CASE lower(threat_severity)
    WHEN 'critical' THEN 'CRITICAL'
    WHEN 'important' THEN 'HIGH'
    WHEN 'moderate' THEN 'MEDIUM'
    WHEN 'low' THEN 'LOW'
    ELSE upper(threat_severity)
  END AS "SEVERITY",
  cve_id AS "CVE",
  LEFT(REGEXP_REPLACE(COALESCE(bugzilla_description, details, ''), E'[\\n\\r]+', ' ', 'g'), 160)
    AS "SUMMARY",
  portal_url AS "Portal"
FROM cve_intel.rh_cve_published
WHERE public_date IS NOT NULL
  AND (public_date AT TIME ZONE 'UTC')::date
      >= ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - INTERVAL '{int(days) - 1} days')
ORDER BY
  (public_date AT TIME ZONE 'UTC')::date DESC,
  CASE lower(threat_severity)
    WHEN 'critical' THEN 0
    WHEN 'important' THEN 1
    WHEN 'moderate' THEN 2
    WHEN 'low' THEN 3
    ELSE 4
  END,
  cve_id
LIMIT 500
""".strip()
    return {
        "type": "table",
        "title": "CVE details (click CVE → Red Hat portal)",
        "description": (
            f"Same {days}-day window as Recent reports. Click a CVE ID for the portal page."
        ),
        "gridPos": {"h": grid_h, "w": grid_w, "x": 0, "y": y},
        "datasource": {"type": POSTGRES_TYPE, "uid": postgres_uid},
        "targets": [_sql_target(postgres_uid, sql)],
        "options": {
            "showHeader": True,
            "footer": {"show": False},
            "cellHeight": "md",
        },
        "fieldConfig": {
            "defaults": {},
            "overrides": _portal_link_overrides("CVE"),
        },
    }


def affecting_us_panel(
    *,
    y: int,
    postgres_uid: str = DEFAULT_POSTGRES_UID,
    days: int = DEFAULT_LOOKBACK_DAYS,
    grid_w: int = 24,
    grid_h: int = 8,
) -> dict[str, Any]:
    sql = f"""
SELECT
  m.cve_id AS "CVE",
  CASE lower(p.threat_severity)
    WHEN 'critical' THEN 'CRITICAL'
    WHEN 'important' THEN 'HIGH'
    WHEN 'moderate' THEN 'MEDIUM'
    WHEN 'low' THEN 'LOW'
    ELSE upper(p.threat_severity)
  END AS "SEVERITY",
  (p.public_date AT TIME ZONE 'UTC')::date AS "DATE",
  m.cluster AS "Cluster",
  m.rhacs_namespace AS "Namespace",
  m.image AS "Image",
  m.component AS "Component",
  m.finding_count AS "Findings",
  p.portal_url AS "Portal"
FROM cve_intel.rh_cve_rhacs_match m
JOIN cve_intel.rh_cve_published p ON p.cve_id = m.cve_id
WHERE p.public_date IS NOT NULL
  AND (p.public_date AT TIME ZONE 'UTC')::date
      >= ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - INTERVAL '{int(days) - 1} days')
AND (
  '${{cluster:pipe}}' IN ({_ALL_VAR_SQL})
  OR m.cluster = ANY(string_to_array('${{cluster:pipe}}', '|'))
)
AND (
  '${{namespace:pipe}}' IN ({_ALL_VAR_SQL})
  OR m.rhacs_namespace = ANY(string_to_array('${{namespace:pipe}}', '|'))
)
ORDER BY
  (p.public_date AT TIME ZONE 'UTC')::date DESC,
  CASE lower(p.threat_severity)
    WHEN 'critical' THEN 0 WHEN 'important' THEN 1
    WHEN 'moderate' THEN 2 WHEN 'low' THEN 3 ELSE 4
  END,
  m.finding_count DESC
LIMIT 300
""".strip()
    return {
        "type": "table",
        "title": f"Affecting us (RHACS) — last {days} days",
        "description": "RHACS matches for CVEs in the Recent reports window.",
        "gridPos": {"h": grid_h, "w": grid_w, "x": 0, "y": y},
        "datasource": {"type": POSTGRES_TYPE, "uid": postgres_uid},
        "targets": [_sql_target(postgres_uid, sql)],
        "options": {"showHeader": True, "footer": {"show": False}},
        "fieldConfig": {
            "defaults": {},
            "overrides": _portal_link_overrides("CVE"),
        },
    }


def intel_section_panels(
    *,
    y_start: int = 200,
    postgres_uid: str = DEFAULT_POSTGRES_UID,
    days: int = DEFAULT_LOOKBACK_DAYS,
    include_product_breakdown: bool = False,
) -> list[dict[str, Any]]:
    """Phase 0 CVE Intel UI: Mythos-style Recent reports only."""
    del include_product_breakdown
    return [
        mythos_recent_reports_panel(
            y=y_start, postgres_uid=postgres_uid, days=days, grid_h=26
        ),
    ]


if __name__ == "__main__":
    import json

    print(json.dumps(intel_section_panels(), indent=2))
