#!/usr/bin/env python3
"""Build RHACS vulnerability Grafana dashboard from scrubbed CSV / data.json.

Uses native Grafana panels only:
  - stat panels for totals / severity
  - table panels (header sort, clickable first column, column filters) via TestData csv_content

No HTML table panels. Requires datasource uid ``ado-testdata``
(grafana-testdata-datasource); publish_rhacs_posture ensures it exists.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

# Collection version string for dashboard fingerprint tags (keep in sync with
# galaxy.yml). Same-version Hub republishes need this hash to prove Contoller
# loaded the intended builder artifact.
_COLLECTION_VERSION = "2.1.2"

from rhacs_report_analytics import (
    AGE_BUCKETS,
    FILTER_ALL,
    FINDING_AGE_BUCKETS,
    OWNERSHIP_LABELS,
    analyze_paths,
    scrubbed_pull_time,
)

TESTDATA_UID = "ado-testdata"
TESTDATA_TYPE = "grafana-testdata-datasource"
SOURCE_ALL = "All sources"
SOURCE_REDHAT = "Red Hat sources"
SOURCE_NON_REDHAT = "Non-Red Hat sources"
# Grafana ``${source:pipe}`` when both RH and NRS chips are selected (not All).
SOURCE_BOTH = f"{SOURCE_REDHAT}|{SOURCE_NON_REDHAT}"
POSTURE_METRIC = "cve_posture_findings"
POSTURE_METRIC_BY_CLUSTER = "cve_posture_findings_by_cluster"
POSTURE_METRIC_BY_NS = "cve_posture_findings_by_ns"
# Never use Prometheus label name ``namespace`` — kube scrape targets inject
# ``namespace=<pod ns>`` and rename the metric label to ``exported_namespace``.
POSTURE_NS_LABEL = "rhacs_namespace"
POSTURE_SEVERITIES = ("Total", "Critical", "Important", "Moderate", "Low")
# Severities shown on the filterable trend (Total stays a separate series).
TREND_SEVERITY_FILTER = "Critical|Important|Moderate|Low|Total"
# Phase 0 / nonprod feature boards — never the production UID.
PRODUCTION_POSTURE_UID = "ado-rhacs-vuln-posture"
# Built-in approved UIDs. Extra Stage/Preprod UIDs via
# CVE_ANALYZER_PHASE0_FEATURE_UIDS (comma-separated) or Ansible
# cve_analyzer_phase0_feature_uids → same env.
DEFAULT_PHASE0_FEATURE_UIDS = frozenset(
    {
        "ado-rhacs-vuln-posture-phase0",
        "ado-lite",
        "ado-dev",
    }
)
# Backward-compatible aliases used by older tests/docs.
PHASE1_FILTERABLE_TREND_UIDS = DEFAULT_PHASE0_FEATURE_UIDS
# Hybrid All→legacy history: full-RHACS boards only (not ado-dev by default).
DEFAULT_PHASE0_HYBRID_UIDS = frozenset(
    {
        "ado-rhacs-vuln-posture-phase0",
        "ado-lite",
    }
)
PHASE1_HYBRID_TREND_UIDS = DEFAULT_PHASE0_HYBRID_UIDS
DETAIL_PANEL_ID = 90


def _env_uid_set(var_name: str) -> frozenset[str]:
    raw = (os.environ.get(var_name) or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def builder_source_sha256() -> str:
    """SHA-256 of this builder file (proves which artifact generated a dashboard)."""
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def builder_fingerprint_tag(version: str | None = None) -> str:
    """Short tag embedded in dashboard ``tags`` for Contoller/Hub delivery audits."""
    ver = (version or _COLLECTION_VERSION).strip() or _COLLECTION_VERSION
    return f"builder-{ver}-{builder_source_sha256()[:8]}"


def phase0_feature_uids() -> frozenset[str]:
    """Approved nonprod UIDs for Phase 0 features (filterable trend, CVE Intel)."""
    return DEFAULT_PHASE0_FEATURE_UIDS | _env_uid_set("CVE_ANALYZER_PHASE0_FEATURE_UIDS")


def phase0_hybrid_uids() -> frozenset[str]:
    """UIDs allowed to use hybrid All→legacy Panel 11 history."""
    extras = _env_uid_set("CVE_ANALYZER_PHASE0_HYBRID_UIDS")
    if extras:
        return extras | _env_uid_set("CVE_ANALYZER_PHASE0_FEATURE_UIDS")
    return DEFAULT_PHASE0_HYBRID_UIDS | _env_uid_set("CVE_ANALYZER_PHASE0_FEATURE_UIDS")


def is_production_posture_uid(uid: str) -> bool:
    return str(uid or "").strip() == PRODUCTION_POSTURE_UID


def is_phase0_feature_uid(uid: str) -> bool:
    """True when UID may receive Phase 0 features; never production."""
    cleaned = str(uid or "").strip()
    if not cleaned or is_production_posture_uid(cleaned):
        return False
    return cleaned in phase0_feature_uids()


def phase1_filterable_trend(uid: str) -> bool:
    """True when both Findings-over-time panels ship (filterable + legacy).

    Production ``ado-rhacs-vuln-posture`` and approved Phase 0 feature UIDs get:

    - Panel 11: filterable by cluster / severity / namespace
    - Panel 12: legacy all-cluster reference (filter-independent)

    Also drives Cluster/Namespace ``allValue`` to ``name1|name2|…|__ALL__`` so
    additive KPI stats (Total/Critical/…) match scrubbed CSV when All is
    selected. ``allValue=__ALL__`` alone matches only Unique-CVE rollup rows
    and leaves other KPIs at zero.
    """
    cleaned = str(uid or "").strip()
    if not cleaned:
        return False
    if is_production_posture_uid(cleaned):
        return True
    return cleaned in phase0_feature_uids()


def phase1_hybrid_trend(uid: str) -> bool:
    """True when Panel 11 may use legacy history for Grafana All (Phase0/Lite)."""
    cleaned = str(uid or "").strip()
    if not cleaned or is_production_posture_uid(cleaned):
        return False
    return cleaned in phase0_hybrid_uids()
DRILL_VARIABLES = (
    "cluster",
    "namespace",
    "namespace_match",
    "finding_age",
    "component",
    "image",
    "sre",
    "age",
    "severity",
    "over30",
    "payload",
)
# Explicit All values for drill URL resets. ``$__all`` is unreliable for hide:2
# vars (payload/sre/severity/…) and leaves prior clicks stuck in Detail.
DRILL_RESET = {
    # Multi-select + includeAll: use $__all so the dropdown shows All (not a
    # literal __ALL__ value that breaks ^(…)$ matching).
    "cluster": "$__all",
    "namespace": "$__all",
    "finding_age": "$__all",
    # Textbox + hide:2 custom vars: $__all is unreliable — set All tokens.
    "namespace_match": ".*",
    "component": ".*",
    "image": ".*",
    "sre": "$__all",
    "age": ".*",
    "severity": "$__all",
    "over30": ".*",
    "payload": ".*",
}

_PANEL_ID = 0


def next_id() -> int:
    global _PANEL_ID
    _PANEL_ID += 1
    return _PANEL_ID


def ds_ref() -> dict:
    return {"type": TESTDATA_TYPE, "uid": TESTDATA_UID}


def to_csv(headers: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().rstrip("\n") + "\n"


def csv_target(csv_text: str, ref_id: str = "A") -> dict:
    # Grafana 13 TestData reads csvContent (stringInput alone returns no frames).
    return {
        "refId": ref_id,
        "datasource": ds_ref(),
        "scenarioId": "csv_content",
        "csvContent": csv_text,
        "stringInput": csv_text,
    }


# Header cards stay uncolored, same as Total and Unique CVEs.
TRANSPARENT_STAT_TITLES = frozenset({
    "Total",
    "Unique CVEs",
    "Fixable findings",
    "Critical",
    "Important",
    "Moderate",
    "Low",
})


def stat_panel(
    title: str,
    value: int,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    color: str = "blue",
    color_mode: str | None = None,
) -> dict:
    color_map = {
        "blue": "blue",
        "red": "red",
        "orange": "orange",
        "yellow": "yellow",
        # dark-yellow is gold enough for white stat text; plain yellow is too light.
        "dark-yellow": "dark-yellow",
        # dark-purple keeps white stat text; named purple is too light.
        "purple": "dark-purple",
        "gray": "text",
        "green": "green",
    }
    if color_mode is None:
        color_mode = "none" if title in TRANSPARENT_STAT_TITLES else "background"
    return {
        "id": next_id(),
        "type": "stat",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": ds_ref(),
        "targets": [csv_target(to_csv(["value"], [[int(value)]]))],
        "options": {
            "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
            "orientation": "auto",
            "textMode": "auto",
            "wideLayout": True,
            "colorMode": color_mode,
            "graphMode": "none",
            "justifyMode": "center",
            "showPercentChange": False,
        },
        "fieldConfig": {
            "defaults": {
                "unit": "none",
                "decimals": 0,
                "color": {"mode": "fixed", "fixedColor": color_map.get(color, "blue")},
                "mappings": [],
            },
            "overrides": [],
        },
        "transparent": False,
    }


_NUMERIC_HEADERS = {
    "Total",
    "Critical",
    "High",
    "Moderate",
    "Low",
    "Images",
    "Total findings",
    "Fixable findings",
    "Critical findings",
    "Unique CVEs",
    "Unique Critical",
    "Unique Important",
    "Total >30 Days",
    "Findings",
    "Important",
    "Fixable Findings",
    "Products",
    "Projects",
}
# Wide enough for a 4–5 digit count. Longer headers need room for the word plus the sort icon.
_NUMBER_WIDTH = 76
_NUMBER_WIDTHS = {
    "Projects": 110,
    "Findings": 112,
    "Critical": 112,
    "Moderate": 112,
    "Important": 112,
    "Unique CVEs": 150,
    "Fixable Findings": 156,
    "Fixable findings": 156,
    "Total findings": 140,
    "Critical findings": 148,
    "Unique Critical": 140,
    "Unique Important": 152,
    "Total >30 Days": 140,
}
# Match the top stat tiles: Critical red, Important orange, Moderate dark-yellow, Low green.
_SEVERITY_HEADER_COLORS = {
    "Critical": "red",
    "Unique Critical": "red",
    "Critical findings": "red",
    "Important": "orange",
    "Unique Important": "orange",
    "Moderate": "dark-yellow",
    "Low": "green",
}


def _header_color(header: str) -> str | None:
    if header in _SEVERITY_HEADER_COLORS:
        return _SEVERITY_HEADER_COLORS[header]
    name = header.lower()
    if "critical" in name:
        return "red"
    if "important" in name:
        return "orange"
    if name == "moderate":
        return "dark-yellow"
    if name == "low":
        return "green"
    return None


_TEXT_WIDTHS = {
    "Image": 420,
    "Namespace / deployment": 360,
    "Status": 120,
    "Age": 90,
    "Cluster": 180,
    "Component": 540,
    "Action": 460,
    "Current image family": 360,
    "How to update": 420,
    "Remediation Path": 280,
    "Product": 300,
    "Namespace": 240,
    "Ownership": 240,
    "Age bucket": 160,
}


def table_panel(
    title: str,
    headers: list[str],
    rows: list[list],
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    sort_by: str | None = None,
    by_source: bool = False,
    filters: list[dict] | None = None,
    hide: list[str] | None = None,
    conceal: list[str] | None = None,
    label_header: str | None = None,
    drill: dict | None = None,
    post_filters: list[dict] | None = None,
) -> dict:
    numeric = [header for header in headers if header in _NUMERIC_HEADERS]
    label = label_header or (
        headers[1] if by_source and len(headers) > 1 else (headers[0] if headers else "")
    )
    sort_field = sort_by or (numeric[0] if numeric else label)
    overrides = []
    for header in headers:
        if header in _NUMERIC_HEADERS:
            properties = [
                {"id": "custom.width", "value": _NUMBER_WIDTHS.get(header, _NUMBER_WIDTH)},
                {"id": "custom.align", "value": "right"},
            ]
            color = _header_color(header)
            if color:
                # Native table headers ignore per-column background. Field color
                # tints the header label where Grafana supports it. Cell type
                # stays auto so the numbers are not colored.
                properties.append(
                    {
                        "id": "color",
                        "value": {"mode": "fixed", "fixedColor": color},
                    }
                )
            overrides.append(
                {"matcher": {"id": "byName", "options": header}, "properties": properties}
            )
            continue
        text_width = _TEXT_WIDTHS.get(header)
        if header == label or text_width or header in (conceal or []):
            properties = [
                {"id": "custom.width", "value": text_width or 320},
                {"id": "custom.align", "value": "left"},
            ]
            if header in ("Cluster", "Namespace", "Component", "Ownership"):
                # Column filter sits on the header and steals the sort click.
                # The Namespace, Component, and SRE managed dropdowns already filter these.
                properties.append({"id": "custom.filterable", "value": False})
            if header in (conceal or []):
                properties.append({"id": "custom.hidden", "value": True})
            if header == (drill or {}).get("field", label) and drill:
                properties.append(
                    {
                        "id": "links",
                        "value": [
                            drill_link(
                                drill["variable"],
                                drill["field"],
                                drill.get("fixed"),
                                drill.get("source"),
                                row_cluster=bool(drill.get("row_cluster")),
                            )
                        ],
                    }
                )
            overrides.append(
                {"matcher": {"id": "byName", "options": header}, "properties": properties}
            )
    transformations = list(filters or [])
    if by_source:
        transformations.append(source_filter())
    transformations.extend(post_filters or [])
    if by_source:
        transformations.append(hide_source_column())
    if hide:
        transformations.append(hide_columns(hide))
    # Do NOT convert Namespace/Component/Ownership to string — Grafana then
    # puts literal quotes into __data.fields values used by drill links
    # (e.g. var-component=%22Dev+Spaces+/+UDI%22), and Detail matches nothing.
    conversions = [{"targetField": header, "destinationType": "number"} for header in numeric]
    if conversions:
        transformations.append(
            {
                "id": "convertFieldType",
                "options": {"conversions": conversions},
            }
        )
    return {
        "id": next_id(),
        "type": "table",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": ds_ref(),
        "targets": [csv_target(to_csv(headers, rows))],
        "options": {
            "showHeader": True,
            "cellHeight": "sm",
            "footer": {"show": False, "reducer": ["sum"], "countRows": False, "fields": ""},
            "sortBy": [{"displayName": sort_field, "desc": True}] if sort_field else [],
        },
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "align": "left",
                    "displayMode": "auto",
                    "cellOptions": {"type": "auto"},
                    "inspect": False,
                    "filterable": True,
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}],
                },
            },
            "overrides": overrides,
        },
        "transformations": transformations,
        "transparent": False,
    }


def operator_subscription_panel(
    subscriptions: list[dict],
    x: int,
    y: int,
    w: int,
    h: int,
) -> dict:
    """OLM subscriptions. Current is red when it is not the installed CSV."""
    headers = ["Operator", "Channel", "Installed", "Current", "Update"]
    table_rows: list[list] = []
    update_currents: set[str] = set()
    current_ok: set[str] = set()
    for item in subscriptions:
        installed = str(item.get("installed") or "<none>")
        current = str(item.get("current") or "<none>")
        if installed == "<none>" and current == "<none>":
            status = "Not installed"
        elif installed != current:
            status = "Update available"
            update_currents.add(current)
        else:
            status = "Up to date"
            current_ok.add(current)
        table_rows.append(
            [
                str(item.get("operator") or ""),
                str(item.get("channel") or ""),
                installed,
                current,
                status,
            ]
        )
    table_rows.sort(key=lambda row: (row[0], row[1], row[2]))
    panel = table_panel(
        "Operator subscriptions",
        headers,
        table_rows,
        x,
        y,
        w,
        h,
        sort_by="Operator",
        label_header="__nolink__",
    )
    panel["description"] = (
        "OLM subscriptions on this cluster. "
        "Current is the CSV the channel wants. "
        "It is red when that is not the installed CSV."
    )
    panel["options"]["sortBy"] = [{"displayName": "Operator", "desc": False}]
    widths = {
        "Operator": 420,
        "Channel": 150,
        "Installed": 420,
        "Current": 420,
        "Update": 170,
    }
    overrides = []
    for header, width in widths.items():
        properties: list[dict] = [
            {"id": "custom.width", "value": width},
            {"id": "custom.align", "value": "left"},
        ]
        if header == "Update":
            properties.extend(
                [
                    {
                        "id": "custom.cellOptions",
                        "value": {"type": "color-background", "mode": "basic"},
                    },
                    {
                        "id": "mappings",
                        "value": [
                            {
                                "type": "value",
                                "options": {
                                    "Update available": {
                                        "color": "red",
                                        "index": 0,
                                        "text": "Update available",
                                    },
                                    "Up to date": {"color": "green", "index": 1, "text": "Up to date"},
                                    "Not installed": {
                                        "color": "orange",
                                        "index": 2,
                                        "text": "Not installed",
                                    },
                                },
                            }
                        ],
                    },
                ]
            )
        if header == "Current":
            red_values = sorted(update_currents - current_ok)
            if red_values:
                properties.append(
                    {
                        "id": "custom.cellOptions",
                        "value": {"type": "color-background", "mode": "basic"},
                    }
                )
                properties.append(
                    {
                        "id": "mappings",
                        "value": [
                            {
                                "type": "value",
                                "options": {
                                    value: {"color": "red", "index": index, "text": value}
                                    for index, value in enumerate(red_values)
                                },
                            }
                        ],
                    }
                )
        overrides.append({"matcher": {"id": "byName", "options": header}, "properties": properties})
    panel["fieldConfig"]["overrides"] = overrides
    return panel


def source_filter() -> dict:
    """Keep rows for the Source multi-select (``:pipe``).

    ``allValue`` is ``SOURCE_ALL`` so All shows the pre-aggregated All-sources
    slice only — never a pipe of all three slices (that double-counts KPIs).
    """
    return multi_regex_filter("Source", "source")


def detail_source_filter() -> dict:
    """Source filter for Detail (panel 90) without doubling every row.

    Rollup tables carry a pre-aggregated ``SOURCE_ALL`` slice. Detail rows are
    one finding each (RH or Non-RH). A sentinel ``SourceAll`` column (always
    ``SOURCE_ALL``) matches when Source=All — same pattern as ClusterAll —
    so we do not embed a second copy of every drilldown row (that pushed Full
    JSON over Grafana's 16 MB publish limit).
    """
    return {
        "id": "filterByValue",
        "options": {
            "filters": [
                {
                    "fieldName": "Source",
                    "config": {
                        "id": "regex",
                        "options": {"value": "^(${source:pipe})$"},
                    },
                },
                {
                    "fieldName": "SourceAll",
                    "config": {"id": "equal", "options": {"value": "${source}"}},
                },
            ],
            "match": "any",
            "type": "include",
        },
    }


def hide_columns(names: list[str]) -> dict:
    return {
        "id": "organize",
        "options": {
            "excludeByName": {name: True for name in names},
            "indexByName": {},
            "renameByName": {},
        },
    }


def hide_source_column() -> dict:
    return hide_columns(["Source"])


def drill_link(
    variable: str,
    field: str,
    fixed: dict[str, str] | None = None,
    source: str | None = None,
    *,
    row_cluster: bool = False,
) -> dict:
    """Open Detail (panel 90) for the clicked cell.

    Opens in a **new tab** (``targetBlank``) so the main dashboard URL/filters
    stay put — browser Back on the board does not keep a stale drill state.

    The clicked cell uses ``__value.raw`` (exact bucket/name text). Other fields
    (Repository, Cluster) still use ``__data.fields``. Hidden drill vars reset
    to explicit All tokens (``.*``), not ``$__all``.
    """
    chosen = dict(fixed or {})
    if source:
        chosen[variable] = f'${{__data.fields["{source}"]:percentencode}}'
    else:
        # Clicked cell text — required for Age bucket (en-dash labels) etc.
        chosen[variable] = "${__value.raw:percentencode}"
    if row_cluster and "cluster" not in chosen:
        chosen["cluster"] = '${__data.fields["Cluster"]:percentencode}'
    parts = [
        "/d/${__dashboard.uid}",
        "?orgId=${__org.id}",
        "&${__url_time_range}",
        "&var-picked=yes",
        f"&viewPanel={DETAIL_PANEL_ID}",
    ]
    for name in DRILL_VARIABLES:
        if name in chosen:
            value = chosen[name]
            if not value.startswith("${"):
                value = quote(value, safe="")
            parts.append(f"&var-{name}={value}")
        else:
            reset = DRILL_RESET[name]
            parts.append(f"&var-{name}={reset}")
    return {"title": "Show only this", "targetBlank": True, "url": "".join(parts)}


def namespace_filter(*, strict: bool = False) -> dict:
    """Multi-select Namespace. All interpolates as __ALL__.

    Tables carry NsAll=__ALL__ on every row so All still shows them.
    Stat cards use strict=True and match rollup rows instead.
    Pair with namespace_match_filter() for optional regex (.*devspaces.*).
    """
    filters = [
        {
            "fieldName": "Namespace",
            "config": {
                "id": "regex",
                "options": {"value": "^(${namespace:pipe})$"},
            },
        }
    ]
    if not strict:
        filters.append(
            {
                "fieldName": "NsAll",
                "config": {"id": "equal", "options": {"value": "${namespace}"}},
            }
        )
    return {
        "id": "filterByValue",
        "options": {"filters": filters, "match": "all" if strict else "any", "type": "include"},
    }


def namespace_match_filter() -> dict:
    """Optional Namespace matches textbox. Default .* keeps every row."""
    return {
        "id": "filterByValue",
        "options": {
            "filters": [
                {
                    "fieldName": "Namespace",
                    "config": {
                        "id": "regex",
                        "options": {"value": "${namespace_match}"},
                    },
                }
            ],
            "match": "all",
            "type": "include",
        },
    }


def cluster_filter(*, strict: bool = False) -> dict:
    """Multi-select ACS secured Cluster. Values come from the export (portable)."""
    filters = [
        {
            "fieldName": "Cluster",
            "config": {
                "id": "regex",
                "options": {"value": "^(${cluster:pipe})$"},
            },
        }
    ]
    if not strict:
        filters.append(
            {
                "fieldName": "ClusterAll",
                "config": {"id": "equal", "options": {"value": "${cluster}"}},
            }
        )
    return {
        "id": "filterByValue",
        "options": {
            "filters": filters,
            "match": "all" if strict else "any",
            "type": "include",
        },
    }


def ns_dim_filters(*, strict: bool = False) -> list[dict]:
    """Cluster + Namespace multi-select + optional namespace regex match."""
    return [
        cluster_filter(strict=strict),
        namespace_filter(strict=strict),
        namespace_match_filter(),
    ]


def finding_age_filter(*, strict: bool = False) -> dict:
    """Multi-select Finding age. Same All token as Namespace."""
    filters = [
        {
            "fieldName": "Age",
            "config": {
                "id": "regex",
                "options": {"value": "^(${finding_age:pipe})$"},
            },
        }
    ]
    if not strict:
        filters.append(
            {
                "fieldName": "AgeAll",
                "config": {"id": "equal", "options": {"value": "${finding_age}"}},
            }
        )
    return {
        "id": "filterByValue",
        "options": {"filters": filters, "match": "all" if strict else "any", "type": "include"},
    }


def rollup_after_namespace(
    group_fields: list[str],
    sum_fields: list[str],
    distinct_fields: dict[str, str],
) -> list[dict]:
    """Collapse rows after Namespace and Finding age filters. Drop the Age column."""
    fields: dict[str, dict] = {}
    for name in group_fields:
        fields[name] = {"aggregations": [], "operation": "groupby"}
    for name in sum_fields:
        fields[name] = {"aggregations": ["sum"], "operation": "aggregate"}
    for name in distinct_fields:
        fields[name] = {"aggregations": ["distinctCount"], "operation": "aggregate"}
    rename = {f"{name} (sum)": name for name in sum_fields}
    rename.update({f"{src} (distinctCount)": dest for src, dest in distinct_fields.items()})
    conversions = [
        {"targetField": name, "destinationType": "number"}
        for name in [*sum_fields, *distinct_fields.values()]
        if name in _NUMERIC_HEADERS
    ]
    transforms: list[dict] = [{"id": "groupBy", "options": {"fields": fields}}]
    if rename:
        transforms.append(
            {
                "id": "organize",
                "options": {
                    "excludeByName": {},
                    "indexByName": {},
                    "renameByName": rename,
                },
            }
        )
    if conversions:
        transforms.append(
            {
                "id": "convertFieldType",
                "options": {"conversions": conversions},
            }
        )
    return transforms


def regex_filter(field: str, variable: str) -> dict:
    """Match a searchable dropdown. All uses .* so the table stays complete."""
    return {
        "id": "filterByValue",
        "options": {
            "filters": [
                {
                    "fieldName": field,
                    "config": {
                        "id": "regex",
                        "options": {"value": f"^${{{variable}}}$"},
                    },
                }
            ],
            "match": "all",
            "type": "include",
        },
    }


def multi_regex_filter(field: str, variable: str) -> dict:
    """Multi-select dropdown via :pipe (All must be a regex-safe allValue)."""
    return {
        "id": "filterByValue",
        "options": {
            "filters": [
                {
                    "fieldName": field,
                    "config": {
                        "id": "regex",
                        "options": {"value": f"^${{{variable}:pipe}}$"},
                    },
                }
            ],
            "match": "all",
            "type": "include",
        },
    }


def equal_value_filter(field: str, value: str) -> dict:
    """Keep rows whose field equals an interpolated Grafana value (exact key)."""
    return {
        "id": "filterByValue",
        "options": {
            "filters": [
                {
                    "fieldName": field,
                    "config": {"id": "equal", "options": {"value": value}},
                }
            ],
            "match": "all",
            "type": "include",
        },
    }


def ownership_filter(*, strict: bool = False) -> dict:
    """SRE managed multi-select. All → ``OwnershipAll=__ALL__`` (dual match).

    ``sre`` ``allValue`` is ``__ALL__``. Tables and additive KPIs keep per-label
    rows and match All via OwnershipAll. Unique KPI uses equal SreKey instead.
    """
    filters: list[dict] = [
        {
            "fieldName": "Ownership",
            "config": {
                "id": "regex",
                "options": {"value": "^(${sre:pipe})$"},
            },
        }
    ]
    if not strict:
        filters.append(
            {
                "fieldName": "OwnershipAll",
                "config": {"id": "equal", "options": {"value": "${sre}"}},
            }
        )
    return {
        "id": "filterByValue",
        "options": {
            "filters": filters,
            "match": "all" if strict else "any",
            "type": "include",
        },
    }


def search_variable(
    name: str,
    label: str,
    values: list[str],
    hide: int = 0,
    current: dict | None = None,
    *,
    sort: int | None = None,
    multi: bool = False,
    preserve_order: bool = False,
    all_value: str = ".*",
) -> dict:
    unique = dict.fromkeys(value.strip() for value in values if value and "," not in value)
    if preserve_order:
        cleaned = list(unique)
    elif sort == 5:
        cleaned = sorted(unique, key=str.casefold)
    else:
        cleaned = sorted(unique)
    if current is None:
        current = (
            {"selected": True, "text": ["All"], "value": ["$__all"]}
            if multi
            else {"selected": True, "text": "All", "value": "$__all"}
        )
    selected = current
    all_selected = selected.get("value") in ("$__all", ["$__all"])
    return {
        "name": name,
        "label": label,
        "type": "custom",
        "query": ",".join(cleaned),
        "current": selected,
        "options": [{"selected": all_selected, "text": "All", "value": "$__all"}]
        + [
            {"selected": selected.get("value") == value, "text": value, "value": value}
            for value in cleaned
        ],
        "multi": multi,
        "includeAll": True,
        "allValue": all_value,
        "hide": hide,
        "skipUrlSync": False,
        # 5 = alphabetical, case-insensitive. Grafana ignores option order when this is unset.
        "sort": 0 if sort is None else sort,
    }


def source_variable() -> dict:
    """Source multi-select matching Cluster / Namespace / Finding age UX.

    Dropdown options are Red Hat / Non-Red Hat only — Grafana ``All`` maps to
    ``SOURCE_ALL`` via ``allValue`` (no redundant ``All sources`` chip).
    """
    return search_variable(
        "source",
        "Source",
        [SOURCE_REDHAT, SOURCE_NON_REDHAT],
        multi=True,
        preserve_order=True,
        all_value=SOURCE_ALL,
        current={"selected": True, "text": ["All"], "value": ["$__all"]},
    )


def sre_variable() -> dict:
    """SRE managed multi-select. Grafana All → ``__ALL__`` (Unique + OwnershipAll)."""
    labels = sorted(OWNERSHIP_LABELS.values(), key=str.casefold)
    return search_variable(
        "sre",
        "SRE managed",
        labels,
        sort=5,
        multi=True,
        # Bare __ALL__ matches Unique SreKey + OwnershipAll on additive/tables.
        all_value=FILTER_ALL,
        current={"selected": True, "text": ["All"], "value": ["$__all"]},
    )


_OCP_METRIC_SPECS = (
    ("Vulnerable images", "vulnerable_digests", "blue"),
    ("Unique Critical", "unique_critical", "red"),
    ("Unique Important", "unique_important", "orange"),
    ("Unique CVEs", "unique_total", "purple"),
    ("Findings", "finding_occurrences", "yellow"),
)


_OCP_BAR_CATEGORY = "SRE-managed OpenShift"


def platform_payload_filterable_rows(analysis: dict) -> list[list]:
    """Source × Cluster rows for the SRE-managed OpenShift bar chart."""
    by_source = analysis.get("filterables_by_source") or {}
    sre_label = OWNERSHIP_LABELS.get("sre_managed", "Red Hat SRE Managed Services")
    rows: list[list] = []
    for source in (SOURCE_ALL, SOURCE_REDHAT, SOURCE_NON_REDHAT):
        block = by_source.get(source) or {}
        by_cluster = block.get("ocp_by_cluster") or {}
        if not by_cluster:
            # Fall back to whole-slice ocp so empty Non-RH still has a zero row.
            ocp = block.get("ocp") or analysis.get("ocp") or {}
            by_cluster = {"Unknown": ocp}
        for cluster, ocp in sorted(by_cluster.items()):
            rows.append(
                [
                    source,
                    cluster,
                    _OCP_BAR_CATEGORY,
                    sre_label,
                    *[int(ocp.get(key, 0) or 0) for _label, key, _color in _OCP_METRIC_SPECS],
                    FILTER_ALL,
                    FILTER_ALL,
                ]
            )
    return rows or [
        [
            SOURCE_ALL,
            "Unknown",
            _OCP_BAR_CATEGORY,
            sre_label,
            0,
            0,
            0,
            0,
            0,
            FILTER_ALL,
            FILTER_ALL,
        ]
    ]


def platform_payload_bars(analysis: dict, x: int, y: int, w: int, h: int) -> dict:
    """Bar chart of OpenShift release-image counts (Cluster + Source + SRE)."""
    metric_names = [label for label, _key, _color in _OCP_METRIC_SPECS]
    headers = [
        "Source",
        "Cluster",
        "Category",
        "Ownership",
        *metric_names,
        "ClusterAll",
        "OwnershipAll",
    ]
    rows = platform_payload_filterable_rows(analysis)
    return {
        "id": next_id(),
        "type": "barchart",
        "title": "Red Hat SRE-managed OpenShift images (cluster-wide)",
        "description": (
            "CLUSTER-WIDE within each selected Cluster — ignores Namespace, "
            "Finding age, and Component (platform payload is not "
            "namespace/component-scoped). Cluster, Source, and SRE managed "
            "apply (rows are ownership=Red Hat SRE Managed Services). "
            "Platform containers shipped with the OpenShift release. "
            "Fixed by upgrading OpenShift. "
            "Unique CVEs is Critical plus Important."
        ),
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": ds_ref(),
        "targets": [csv_target(to_csv(headers, rows))],
        "transformations": [
            source_filter(),
            cluster_filter(),
            ownership_filter(),
            hide_source_column(),
            hide_columns(["Cluster", "ClusterAll", "Ownership", "OwnershipAll"]),
            {
                "id": "convertFieldType",
                "options": {
                    "conversions": [
                        {"targetField": "Category", "destinationType": "string"}
                    ]
                },
            },
            {
                "id": "groupBy",
                "options": {
                    "fields": {
                        "Category": {"aggregations": [], "operation": "groupby"},
                        **{
                            name: {"aggregations": ["sum"], "operation": "aggregate"}
                            for name in metric_names
                        },
                    }
                },
            },
            {
                "id": "organize",
                "options": {
                    # Keep Category — barchart needs a string/time field.
                    "excludeByName": {},
                    "indexByName": {},
                    "renameByName": {f"{name} (sum)": name for name in metric_names},
                },
            },
        ],
        "options": {
            "orientation": "horizontal",
            "xTickLabelRotation": 0,
            "showValue": "always",
            "stacking": "none",
            "groupWidth": 0.7,
            "barWidth": 0.8,
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "none"},
            "xField": "Category",
        },
        "fieldConfig": {
            "defaults": {"unit": "none", "decimals": 0},
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": name},
                    "properties": [
                        {"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}
                    ],
                }
                for name, _key, color in _OCP_METRIC_SPECS
            ],
        },
        "transparent": False,
    }


def ocp_age_filterable_rows(
    analysis: dict, *, critical: bool
) -> list[list]:
    """Source × Cluster × Age-bucket rows for OCP CVE-by-age tables."""
    by_source = analysis.get("filterables_by_source") or {}
    key = "ocp_age_critical_by_cluster" if critical else "ocp_age_important_by_cluster"
    legacy_key = "ocp_age_critical" if critical else "ocp_age_important"
    rows: list[list] = []
    for source in (SOURCE_ALL, SOURCE_REDHAT, SOURCE_NON_REDHAT):
        block = by_source.get(source) or {}
        by_cluster = block.get(key) or {}
        if not by_cluster:
            totals = block.get(legacy_key) or analysis.get(legacy_key) or {}
            by_cluster = {"Unknown": totals}
        for cluster, buckets in sorted(by_cluster.items()):
            for age_name in list(AGE_BUCKETS) + ["Unknown"]:
                rows.append(
                    [
                        source,
                        cluster,
                        age_name,
                        int(buckets.get(age_name, 0) or 0),
                        FILTER_ALL,
                    ]
                )
    return rows or [[SOURCE_ALL, "Unknown", AGE_BUCKETS[0], 0, FILTER_ALL]]


def ocp_age_table_panel(
    title: str,
    analysis: dict,
    *,
    critical: bool,
    x: int,
    y: int,
    w: int,
    h: int,
    drill: dict | None = None,
) -> dict:
    """CVE-by-age distribution for SRE-managed OpenShift (Cluster + Source)."""
    headers = ["Source", "Cluster", "Age bucket", "Unique CVEs", "ClusterAll"]
    panel = table_panel(
        title,
        headers,
        ocp_age_filterable_rows(analysis, critical=critical),
        x,
        y,
        w,
        h,
        by_source=True,
        filters=[cluster_filter()],
        post_filters=rollup_after_namespace(
            ["Age bucket"],
            ["Unique CVEs"],
            {},
        ),
        hide=["Cluster", "ClusterAll"],
        drill=drill,
    )
    panel["description"] = (
        "CLUSTER-WIDE within each selected Cluster — ignores Namespace. "
        "Shows the full CVE age *distribution* (AGE_BUCKETS); the Finding age "
        "toolbar filter does not apply here (different bucket scheme). "
        "Cluster and Source filters apply."
    )
    return panel


def _prom_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"')


def posture_metrics_text(
    severity: dict,
    by_cluster: dict[str, dict[str, int]] | None = None,
    by_ns: dict[tuple[str, str], dict[str, int]] | None = None,
) -> str:
    """Prometheus gauges. Scrape time is the point on the chart.

    Always emits legacy ``cve_posture_findings{severity}`` unchanged. Optional
    ``by_cluster`` / ``by_ns`` emit the newer labeled families from the full report.
    """
    lines = [
        "# BEGIN cve_posture",
        "# HELP cve_posture_findings RHACS posture finding counts from the latest CVE Analyzer report",
        "# TYPE cve_posture_findings gauge",
    ]
    for name in POSTURE_SEVERITIES:
        lines.append(f'{POSTURE_METRIC}{{severity="{name}"}} {int(severity.get(name, 0))}')
    if by_cluster is not None:
        lines.append(
            "# HELP cve_posture_findings_by_cluster "
            "RHACS posture finding counts by RHACS cluster and severity"
        )
        lines.append(f"# TYPE {POSTURE_METRIC_BY_CLUSTER} gauge")
        for cluster, counts in sorted(by_cluster.items()):
            cl = _prom_label(cluster)
            for name in POSTURE_SEVERITIES:
                lines.append(
                    f'{POSTURE_METRIC_BY_CLUSTER}{{cluster="{cl}",severity="{name}"}} '
                    f"{int(counts.get(name, 0))}"
                )
    if by_ns is not None:
        lines.append(
            "# HELP cve_posture_findings_by_ns "
            "RHACS posture finding counts by RHACS cluster, namespace, and severity "
            f"(label {POSTURE_NS_LABEL}; not kube scrape namespace)"
        )
        lines.append(f"# TYPE {POSTURE_METRIC_BY_NS} gauge")
        for (cluster, namespace), counts in sorted(by_ns.items()):
            cl = _prom_label(cluster)
            ns = _prom_label(namespace)
            for name in POSTURE_SEVERITIES:
                lines.append(
                    f'{POSTURE_METRIC_BY_NS}{{cluster="{cl}",{POSTURE_NS_LABEL}="{ns}",'
                    f'severity="{name}"}} {int(counts.get(name, 0))}'
                )
    lines.append("# END cve_posture")
    return "\n".join(lines) + "\n"


def merge_posture_metrics(existing: str, block: str) -> str:
    lines = []
    skipping = False
    for line in existing.splitlines():
        if line.strip() == "# BEGIN cve_posture":
            skipping = True
            continue
        if line.strip() == "# END cve_posture":
            skipping = False
            continue
        if skipping:
            continue
        # Exact family prefixes only — keep unrelated gauges (triage, etc.).
        if (
            line.startswith(f"{POSTURE_METRIC}{{")
            or line.startswith(f"{POSTURE_METRIC_BY_CLUSTER}{{")
            or line.startswith(f"{POSTURE_METRIC_BY_NS}{{")
            or line.startswith(f"# HELP {POSTURE_METRIC} ")
            or line == f"# HELP {POSTURE_METRIC}"
            or line.startswith(f"# TYPE {POSTURE_METRIC} ")
            or line == f"# TYPE {POSTURE_METRIC}"
            or line.startswith(f"# HELP {POSTURE_METRIC_BY_CLUSTER} ")
            or line == f"# HELP {POSTURE_METRIC_BY_CLUSTER}"
            or line.startswith(f"# TYPE {POSTURE_METRIC_BY_CLUSTER} ")
            or line == f"# TYPE {POSTURE_METRIC_BY_CLUSTER}"
            or line.startswith(f"# HELP {POSTURE_METRIC_BY_NS} ")
            or line == f"# HELP {POSTURE_METRIC_BY_NS}"
            or line.startswith(f"# TYPE {POSTURE_METRIC_BY_NS} ")
            or line == f"# TYPE {POSTURE_METRIC_BY_NS}"
        ):
            continue
        lines.append(line)
    body = "\n".join(lines).rstrip()
    return f"{body}\n\n{block.strip()}\n" if body else block


def dashboard_scope_clusters(
    cluster_scope: dict | None,
    board_clusters: list[str],
) -> list[str]:
    """Clusters that Grafana All / Panel 11 may sum — dashboard scope only.

    Never expands to every RHACS cluster from metrics when the board is filtered.
    ``board_clusters`` is the dropdown option list derived from table/Detail data.
    """
    scope = cluster_scope or {}
    board = [
        str(c).strip()
        for c in board_clusters
        if str(c).strip() and str(c).strip() not in {FILTER_ALL, "unknown"}
    ]
    board_set = set(board)
    if scope.get("all_clusters", True):
        raw = list(scope.get("available") or [])
    else:
        raw = list(scope.get("selected") or [])
    scoped = [
        str(c).strip()
        for c in raw
        if str(c).strip() and str(c).strip() not in {FILTER_ALL, "unknown"}
    ]
    if board_set and scoped:
        # Intersection: never advertise a cluster that is not on this board.
        ordered = [c for c in scoped if c in board_set]
        return ordered or board
    return scoped or board


def dashboard_cluster_all_value(scope_clusters: list[str]) -> str:
    """Grafana All value: scoped clusters + __ALL__ so tables and PromQL both work.

    Tables: ``^(prod-cluster|ocp-dev|__ALL__)$`` matches real rows and rollups.
    PromQL: ``cluster=~"prod-cluster|ocp-dev|__ALL__"`` matches real labels only
    (``__ALL__`` is not a Prometheus cluster label — never the sole matcher when
    the dashboard scope has at least one real cluster).
    """
    parts = [
        str(c).strip()
        for c in scope_clusters
        if str(c).strip() and str(c).strip() != FILTER_ALL
    ]
    # Alphabetical — matches Grafana sort=5 ``:pipe`` and analytics ClusterKey.
    ordered = sorted(dict.fromkeys(parts), key=str.casefold)
    if not ordered:
        # No scope yet — tables still need the rollup token; PromQL matches nothing
        # until real clusters appear (avoid pretending All = every RHACS cluster).
        return FILTER_ALL
    ordered.append(FILTER_ALL)
    return "|".join(ordered)


def prom_cluster_all_matcher(all_value: str) -> str:
    """What Prometheus actually matches when Grafana All expands ``allValue``.

    Drops ``__ALL__`` (table rollup token). Empty if All would match nothing.
    """
    parts = [p for p in str(all_value or "").split("|") if p and p != FILTER_ALL]
    return "|".join(parts)


def dashboard_namespace_all_value(namespaces: list[str]) -> str:
    """Grafana Namespace All value: board namespaces + ``__ALL__`` (tables + PromQL)."""
    parts = [
        str(n).strip()
        for n in namespaces
        if str(n).strip() and str(n).strip() not in {FILTER_ALL, "Unknown", "unknown"}
    ]
    ordered = list(dict.fromkeys(parts))
    if not ordered:
        return FILTER_ALL
    ordered.append(FILTER_ALL)
    return "|".join(ordered)


def _trend_legacy_expr() -> str:
    """All/All filterable path: unlabeled ``cve_posture_findings``.

    Per-pod totals first (``sum by (severity, pod)``), then median across pods
    (``quantile … 0.5``). That collapses stale scrape targets after rollouts and
    resists a single corrupted textfile (one pod briefly double-published by_ns).
    This metric has no cluster label — cluster filters use by_cluster / by_ns.
    """
    return (
        "quantile by (severity) (0.5, "
        "sum by (severity, pod) ("
        "last_over_time("
        f'{POSTURE_METRIC}{{'
        'job="cve-analyzer-ns-metrics",'
        f'severity=~"{TREND_SEVERITY_FILTER}"'
        "}[1d])))"
    )


def _trend_by_cluster_expr() -> str:
    """Cluster filter: sum selected clusters per pod, then median across pods."""
    return (
        "quantile by (severity) (0.5, "
        "sum by (severity, pod) ("
        "last_over_time("
        f'{POSTURE_METRIC_BY_CLUSTER}{{'
        'job="cve-analyzer-ns-metrics",'
        'cluster=~"${cluster:pipe}",'
        f'severity=~"{TREND_SEVERITY_FILTER}"'
        "}[1d])))"
    )


def _trend_by_ns_expr() -> str:
    """Namespace-restricted path: dropdown pipe AND Namespace matches regex.

    Both selectors always apply — neither silently bypasses the other. An invalid
    ``namespace_match`` regex fails the Prometheus query (Grafana shows an error)
    instead of falling back to all namespaces.

    Sum namespaces per pod (preserves multi-cluster/ns totals for that scrape),
    then take the median pod total so stale or double-published scrapes do not
    inflate the chart.
    """
    return (
        "quantile by (severity) (0.5, "
        "sum by (severity, pod) ("
        "last_over_time("
        f'{POSTURE_METRIC_BY_NS}{{'
        'job="cve-analyzer-ns-metrics",'
        'cluster=~"${cluster:pipe}",'
        f'{POSTURE_NS_LABEL}=~"${{namespace:pipe}}",'
        f'{POSTURE_NS_LABEL}=~"${{namespace_match}}",'
        f'severity=~"{TREND_SEVERITY_FILTER}"'
        "}[1d])))"
    )


def hybrid_findings_trend_gate_expr() -> str:
    """PromQL gate: true only when Grafana Cluster selection text is ``All``.

    Simpler than comparing custom ``allValue`` pipe strings. Manual multi-select
    (even every cluster) keeps ``${cluster:text}`` ≠ ``All`` → by-cluster path.
    """
    return 'absent(_{_="All"}) and absent(_{_="${cluster:text}"})'


def hybrid_namespace_unrestricted_gate_expr() -> str:
    """True only when Namespace=All and Namespace matches is exactly ``.*``.

    Any dropdown subset or non-default regex forces the by-namespace metric path.
    """
    ns_all = 'absent(_{_="All"}) and absent(_{_="${namespace:text}"})'
    match_all = 'absent(_{_=".*"}) and absent(_{_="${namespace_match}"})'
    return f"({ns_all}) and on() ({match_all})"


def filterable_findings_trend_expr(scope_clusters: list[str] | None = None) -> str:
    """Panel 11 PromQL for Dev / subset-scoped boards (never legacy history).

    Unrestricted namespace → by-cluster (scoped All via ``allValue``).
    Any namespace restriction → by-ns. Never uses all-RHACS legacy samples.
    """
    _ = scope_clusters
    ns_free = hybrid_namespace_unrestricted_gate_expr()
    by_cluster = _trend_by_cluster_expr()
    by_ns = _trend_by_ns_expr()
    return (
        f"({by_cluster} and on() ({ns_free})) "
        f"or on() ({by_ns} unless on() ({ns_free}))"
    )


def hybrid_findings_trend_expr() -> str:
    """Phase0/Lite Panel 11: legacy / by-cluster / by-ns.

    - Cluster=All + Namespace=All + match ``.*`` → ``cve_posture_findings`` (Aug+)
    - Cluster subset + Namespace unrestricted → ``…_by_cluster``
    - Any namespace restriction → ``…_by_ns`` (no legacy leak)
    """
    cluster_all = hybrid_findings_trend_gate_expr()
    ns_free = hybrid_namespace_unrestricted_gate_expr()
    legacy = _trend_legacy_expr()
    by_cluster = _trend_by_cluster_expr()
    by_ns = _trend_by_ns_expr()
    return (
        f"({legacy} and on() (({cluster_all}) and on() ({ns_free}))) "
        f"or on() ({by_cluster} and on() ({ns_free}) unless on() ({cluster_all})) "
        f"or on() ({by_ns} unless on() ({ns_free}))"
    )


def legacy_findings_trend_expr() -> str:
    """All-cluster historical PromQL (reference panel — ignores dashboard filters).

    Metric name/job unchanged. Aggregate per pod then median across pods so
    ``last_over_time(...[1d])`` does not sum stale scrape targets after metrics
    Deployment rollouts (and ignores a single double-published outlier).
    """
    return (
        "quantile by (severity) (0.5, "
        "sum by (severity, pod) ("
        f'last_over_time({POSTURE_METRIC}{{job="cve-analyzer-ns-metrics"}}[1d])))'
    )



def prometheus_variable(default_uid: str) -> dict:
    """Hidden Prometheus datasource picker.

    Trend panels still use ${prometheus}. Hide in the UI when there is typically
    one scrape source; override via cve_analyzer_prometheus_datasource_uid.
    """
    return {
        "name": "prometheus",
        "label": "Prometheus",
        "type": "datasource",
        "query": "prometheus",
        "refresh": 1,
        "regex": "",
        "multi": False,
        "includeAll": False,
        "hide": 2,
        "skipUrlSync": False,
        "current": {"selected": True, "text": default_uid, "value": default_uid},
        "options": [],
    }


def openshift_version_variable() -> dict:
    """Current OpenShift version from whichever Prometheus or Thanos source is selected."""
    query = 'label_values(cluster_version{type="current"}, version)'
    return {
        "name": "openshift_version",
        "label": "OpenShift",
        "type": "query",
        "datasource": {"type": "prometheus", "uid": "${prometheus}"},
        "definition": query,
        "query": {
            "qryType": 1,
            "query": query,
            "refId": "PrometheusVariableQueryEditor-VariableQuery",
        },
        "refresh": 1,
        "regex": "",
        "sort": 0,
        "multi": False,
        "includeAll": False,
        "hide": 2,
        "skipUrlSync": False,
        "current": {"selected": False, "text": "version unavailable", "value": ""},
        "options": [],
    }


def openshift_version_panel(x: int, y: int, w: int, h: int) -> dict:
    """Current version from the Prometheus dropdown. Yellow when an update exists."""
    datasource = {"type": "prometheus", "uid": "${prometheus}"}
    # The recommended next version is a label on the conditional-update metric.
    # The count metric only knows that updates exist, so it is the fallback
    # and can show the channel when the version string is absent.
    expr = """
(
  label_replace(
    (
      max by (version) (cluster_version{type="current"}) * 0
      + on() group_left(available)
      (
        label_replace(
          topk(1, cluster_version_conditional_update_condition_seconds{condition="Recommended",status="True"}),
          "available", "$1", "version", "(.*)"
        ) * 0 + 1
      )
    ),
    "status", "Update available: $1", "available", "(.*)"
  )
)
or
(
  label_replace(
    (
      max by (version) (cluster_version{type="current"}) * 0
      + on() group_left(channel)
      (
        topk(1, cluster_version_available_updates > 0) * 0 + 1
      )
    ),
    "status", "Update available ($1)", "channel", "(.*)"
  )
  unless on()
  (cluster_version_conditional_update_condition_seconds{condition="Recommended",status="True"})
)
or
(
  label_replace(
    max by (version) (cluster_version{type="current"}) * 0,
    "status", "Up to date", "version", ".+"
  )
  unless on()
  (
    cluster_version_available_updates > 0
    or
    cluster_version_conditional_update_condition_seconds{condition="Recommended",status="True"}
  )
)
""".strip()
    return {
        "id": next_id(),
        "type": "stat",
        "title": "",
        "description": (
            "OpenShift cluster version from the selected Prometheus or Thanos source. "
            "Green when the cluster is up to date. "
            "Yellow when an update is available. "
            "The recommended version is shown when Prometheus has it."
        ),
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": datasource,
        "targets": [
            {
                "refId": "A",
                "datasource": datasource,
                "expr": expr,
                "instant": True,
                "legendFormat": "OpenShift cluster version: {{version}} — {{status}}",
            }
        ],
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "horizontal",
            "textMode": "name",
            "colorMode": "background",
            "graphMode": "none",
            "justifyMode": "center",
            "wideLayout": True,
            "text": {"titleSize": 14, "valueSize": 14},
        },
        "fieldConfig": {
            "defaults": {
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "yellow", "value": 1},
                    ],
                },
                "noValue": "OpenShift cluster version: unavailable",
                "mappings": [],
            },
            "overrides": [],
        },
        "transparent": False,
    }


def _trend_field_config(colors: dict[str, str]) -> dict:
    return {
        "defaults": {
            "unit": "none",
            "decimals": 0,
            "custom": {
                "drawStyle": "line",
                "lineInterpolation": "linear",
                "lineWidth": 2,
                "fillOpacity": 10,
                "gradientMode": "none",
                "showPoints": "always",
                "pointSize": 6,
                "spanNulls": True,
                "axisPlacement": "auto",
                "scaleDistribution": {"type": "linear"},
            },
        },
        "overrides": [
            {
                "matcher": {"id": "byName", "options": name},
                "properties": [
                    {"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}
                ],
            }
            for name, color in colors.items()
        ],
    }


def findings_trend_panel(
    x: int,
    y: int,
    w: int,
    h: int,
    datasource_uid: str,
    cluster_scope: dict | None = None,
) -> dict:
    """Production / locked Panel 11: all-cluster historical cve_posture_findings."""
    datasource = {"type": "prometheus", "uid": "${prometheus}"}
    colors = {
        "Total": "blue",
        "Critical": "red",
        "Important": "orange",
        "Moderate": "yellow",
        "Low": "green",
    }
    scope = cluster_scope or {}
    if scope.get("all_clusters", True):
        scope_note = (
            "cve_analyzer_clusters is all clusters — this trend matches the rest of the board."
        )
        title = "Findings over time — all-cluster historical trend"
    else:
        selected = ", ".join(scope.get("selected") or []) or "selected"
        scope_note = (
            f"Dashboard tables/Detail are limited to: {selected}. "
            "This trend stays ALL-CLUSTER on purpose so historical gauges are not rewritten."
        )
        title = "Findings over time — ALL-CLUSTER historical trend (not dashboard filter)"
    return {
        "id": next_id(),
        "type": "timeseries",
        "title": title,
        "description": (
            f"{scope_note} "
            "Namespace/Component/Source/Severity/Age dropdowns also do NOT apply here. "
            f'Metric {POSTURE_METRIC}{{job="cve-analyzer-ns-metrics"}} must stay unchanged. '
            "Each older point is one saved report, stamped noon ET on the day in the file name. "
            "Moderate and Low are 0 on those older files. "
            "Important is the High bucket. "
            f"Use the Prometheus dropdown if this Grafana names the datasource something "
            f"other than {datasource_uid}."
        ),
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": datasource,
        "targets": [
            {
                "refId": "A",
                "datasource": datasource,
                "expr": legacy_findings_trend_expr(),
                "legendFormat": "{{severity}}",
                "interval": "1h",
            }
        ],
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "fieldConfig": _trend_field_config(colors),
    }


def filterable_findings_trend_panel(
    x: int,
    y: int,
    w: int,
    h: int,
    datasource_uid: str,
    cluster_scope: dict | None = None,
    scope_clusters: list[str] | None = None,
    hybrid: bool = False,
) -> dict:
    """Phase 1 test-board Panel 11: cluster + severity (optional hybrid history)."""
    datasource = {"type": "prometheus", "uid": "${prometheus}"}
    colors = {
        "Total": "blue",
        "Critical": "red",
        "Important": "orange",
        "Moderate": "yellow",
        "Low": "green",
    }
    scope = cluster_scope or {}
    clusters = list(scope_clusters or [])
    if scope.get("all_clusters", True):
        scope_note = (
            "Responds to Cluster and Severity dropdowns. "
            "All = every RHACS cluster in this dashboard's scope "
            f"({', '.join(clusters) or 'all present'}). "
        )
    else:
        selected = ", ".join(scope.get("selected") or clusters) or "selected"
        scope_note = (
            f"Dashboard tables/Detail are limited to: {selected}. "
            "This trend uses the same Cluster/Severity dropdowns within that scope. "
        )
    if hybrid:
        history_note = (
            "All clusters + All namespaces + Namespace matches .* : historical data "
            f"since August 2, 2026 ({POSTURE_METRIC}). "
            "Cluster subset + unrestricted namespace: since October 28, 2026 "
            f"({POSTURE_METRIC_BY_CLUSTER}). "
            "Any Namespace dropdown or Namespace matches restriction: "
            f"{POSTURE_METRIC_BY_NS} from first scrape (no backfill). "
            "Manual multi-cluster selection never switches to all-cluster history. "
        )
        expr = hybrid_findings_trend_expr()
        # Inherit dashboard 90d so All can show Aug+ history; 1m + higher maxDataPoints
        # keeps brand-new by-cluster / by-ns scrapes visible when a subset is selected.
        timing = {"maxDataPoints": 5000}
    else:
        history_note = (
            f"Unrestricted namespace → {POSTURE_METRIC_BY_CLUSTER}; "
            f"namespace-restricted → {POSTURE_METRIC_BY_NS}. "
            "Never uses all-RHACS legacy history on this board. "
            "Namespace history starts at first scrape (no backfill). "
            "Panel time defaults to last 7 days with a 1m min step so new scrapes "
            "are visible under the dashboard 90d window. "
            "Use the legacy all-cluster panel below for full RHACS historical trends. "
        )
        expr = filterable_findings_trend_expr(clusters)
        timing = {"timeFrom": "now-7d"}
    return {
        "id": next_id(),
        "type": "timeseries",
        "title": "Findings over time — filterable by cluster / namespace",
        "description": (
            f"{scope_note}"
            f"{history_note}"
            "Responds to Cluster, Namespace, and Namespace matches. "
            "Both namespace controls apply together; an invalid Namespace matches "
            "regex fails the query (error) instead of showing all namespaces. "
            "Shows all severities (Critical/Important/Moderate/Low/Total). "
            "Component/Ownership/Image/Age do not apply to this trend. "
            f"Datasource default: {datasource_uid}."
        ),
        **timing,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": datasource,
        "targets": [
            {
                "refId": "A",
                "datasource": datasource,
                "expr": expr,
                "legendFormat": "{{severity}}",
                "interval": "1m",
            }
        ],
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "fieldConfig": _trend_field_config(colors),
    }


def legacy_findings_trend_panel(
    x: int,
    y: int,
    w: int,
    h: int,
    datasource_uid: str,
) -> dict:
    """Temporary reference: original all-cluster history (unchanged metric/PromQL)."""
    datasource = {"type": "prometheus", "uid": "${prometheus}"}
    colors = {
        "Total": "blue",
        "Critical": "red",
        "Important": "orange",
        "Moderate": "yellow",
        "Low": "green",
    }
    return {
        "id": next_id(),
        "type": "timeseries",
        "title": "Findings over time — legacy all-cluster (reference)",
        "description": (
            "Temporary reference while the filterable trend accumulates history. "
            f"Locked metric {POSTURE_METRIC}"
            '{job="cve-analyzer-ns-metrics"} — not filtered by Cluster/Severity. '
            "Do not remove until the by-cluster series has enough scrape history. "
            f"Datasource default: {datasource_uid}."
        ),
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": datasource,
        "targets": [
            {
                "refId": "A",
                "datasource": datasource,
                "expr": legacy_findings_trend_expr(),
                "legendFormat": "{{severity}}",
                "interval": "1h",
            }
        ],
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "fieldConfig": _trend_field_config(colors),
    }


def new_tab_link(label: str, url: str) -> str:
    href = escape(url, quote=True)
    text = escape(label)
    return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{text}</a>'


def markdown_panel(title: str, content: str, x: int, y: int, w: int, h: int) -> dict:
    return {
        "id": next_id(),
        "type": "text",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {"mode": "markdown", "content": content},
        "transparent": True,
    }


def bargauge_panel(
    title: str,
    items: list[tuple[str, int]],
    x: int,
    y: int,
    w: int,
    h: int,
) -> dict:
    if not items:
        items = [("none", 0)]
    headers = [name for name, _ in items]
    values = [val for _, val in items]
    # One-row CSV so each namespace is a numeric field → bargauge series
    csv_text = to_csv(headers, [values])
    return _bargauge(title, csv_text, x, y, w, h, [])


def sourced_bargauge_panel(
    title: str,
    all_items: list[tuple[str, int]],
    redhat_items: list[tuple[str, int]],
    nonredhat_items: list[tuple[str, int]],
    x: int,
    y: int,
    w: int,
    h: int,
) -> dict:
    rows: list[list] = []
    for source, items in (
        (SOURCE_ALL, all_items),
        (SOURCE_REDHAT, redhat_items),
        (SOURCE_NON_REDHAT, nonredhat_items),
    ):
        if not items:
            items = [("Unknown", "none", "Unknown", 0)]
        for item in items:
            if len(item) >= 4:
                cluster, name, age, val = item[0], item[1], item[2], item[3]
            elif len(item) >= 3:
                cluster, name, age, val = "Unknown", item[0], item[1], item[2]
            else:
                cluster, name, age, val = "Unknown", item[0], "Unknown", item[1]
            rows.append(
                [
                    source,
                    cluster,
                    name,
                    age,
                    int(val),
                    FILTER_ALL,
                    FILTER_ALL,
                    FILTER_ALL,
                ]
            )
    csv_text = to_csv(
        ["Source", "Cluster", "Namespace", "Age", "Critical", "ClusterAll", "NsAll", "AgeAll"],
        rows,
    )
    return _bargauge(
        title,
        csv_text,
        x,
        y,
        w,
        h,
        [
            source_filter(),
            *ns_dim_filters(),
            finding_age_filter(),
            *rollup_after_namespace(["Namespace"], ["Critical"], {}),
            hide_source_column(),
            hide_columns(["Cluster", "Age", "ClusterAll", "NsAll", "AgeAll"]),
            {
                "id": "rowsToFields",
                "options": {
                    "mappings": [
                        {"fieldName": "Namespace", "handlerKey": "field.name"},
                        {"fieldName": "Critical", "handlerKey": "field.value"},
                    ]
                },
            },
        ],
    )


def _bargauge(
    title: str,
    csv_text: str,
    x: int,
    y: int,
    w: int,
    h: int,
    transformations: list[dict],
) -> dict:
    return {
        "id": next_id(),
        "type": "bargauge",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": ds_ref(),
        "targets": [csv_target(csv_text)],
        "options": {
            "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
            "orientation": "horizontal",
            "displayMode": "gradient",
            "valueMode": "color",
            "sizing": "auto",
            "minVizWidth": 8,
            "minVizHeight": 16,
            "showUnfilled": True,
            "namePlacement": "auto",
        },
        "fieldConfig": {
            "defaults": {
                "unit": "none",
                "decimals": 0,
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "orange", "value": 10},
                        {"color": "red", "value": 50},
                    ],
                },
            },
            "overrides": [],
        },
        "transformations": transformations,
        "transparent": False,
    }


def sourced_stat_panel(
    title: str,
    rows: list[list],
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    color: str = "blue",
    calc: str = "sum",
    value_field: str = "value",
    with_ownership: bool = True,
) -> dict:
    """Additive KPI card (finding counts). Ownership All via OwnershipAll."""
    panel = stat_panel(title, 0, x, y, w, h, color=color)
    headers = [
        "Source",
        "Cluster",
        "Namespace",
        "Age",
        "Ownership",
        value_field,
        "OwnershipAll",
    ]
    panel["targets"] = [
        csv_target(
            to_csv(
                headers,
                rows
                or [
                    [
                        "All sources",
                        "Unknown",
                        "none",
                        "Unknown",
                        "Non-Red Hat",
                        0,
                        FILTER_ALL,
                    ]
                ],
            )
        )
    ]
    panel["options"]["reduceOptions"] = {
        "values": False,
        "calcs": [calc],
        "fields": f"/^{value_field}$/",
    }
    transformations = [
        source_filter(),
        *ns_dim_filters(strict=True),
        finding_age_filter(strict=True),
        ownership_filter(),
        hide_source_column(),
        hide_columns(["Cluster", "Namespace", "Age", "Ownership", "OwnershipAll"]),
    ]
    if calc != "distinctCount":
        transformations.append(
            {
                "id": "convertFieldType",
                "options": {
                    "conversions": [
                        {"targetField": value_field, "destinationType": "number"}
                    ]
                },
            }
        )
    panel["transformations"] = transformations
    return panel


def sourced_unique_stat_panel(
    title: str,
    rows: list[list],
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    color: str = "blue",
    value_field: str = "value",
) -> dict:
    """Unique CVE KPI — equal keys so All/single hit one distinct rollup.

    Unsupported multi-selects match no row → Grafana no-data (not an inflated sum).
    """
    panel = stat_panel(title, 0, x, y, w, h, color=color)
    headers = ["Source", "ClusterKey", "Namespace", "Age", "SreKey", value_field]
    panel["targets"] = [
        csv_target(
            to_csv(
                headers,
                rows
                or [[SOURCE_ALL, FILTER_ALL, FILTER_ALL, FILTER_ALL, FILTER_ALL, 0]],
            )
        )
    ]
    panel["options"]["reduceOptions"] = {
        "values": False,
        "calcs": ["sum"],
        "fields": f"/^{value_field}$/",
    }
    panel["fieldConfig"]["defaults"]["noValue"] = "n/a"
    panel["transformations"] = [
        equal_value_filter("Source", "${source:pipe}"),
        equal_value_filter("ClusterKey", "${cluster:pipe}"),
        namespace_filter(strict=True),
        namespace_match_filter(),
        finding_age_filter(strict=True),
        equal_value_filter("SreKey", "${sre:pipe}"),
        hide_source_column(),
        hide_columns(["ClusterKey", "Namespace", "Age", "SreKey"]),
        {
            "id": "convertFieldType",
            "options": {
                "conversions": [
                    {"targetField": value_field, "destinationType": "number"}
                ]
            },
        },
    ]
    return panel


_KPI_METRIC_KEYS = {
    "Total": "Findings",
    "Fixable findings": "Fixable Findings",
    "Unique CVEs": "Unique CVEs",
    "Critical": "Critical",
    "Important": "Important",
    "Moderate": "Moderate",
    "Low": "Low",
}


def _stat_item_row(source: str, item: dict, key: str) -> list:
    metric = _KPI_METRIC_KEYS.get(key, key)
    return [
        source,
        item.get("Cluster") or "Unknown",
        item.get("Namespace") or "Unknown",
        item.get("Age") or "Unknown",
        item.get("Ownership") or "",
        int(item.get(metric, item.get(key, 0)) or 0),
        FILTER_ALL,
    ]


def _unique_stat_item_row(source: str, item: dict) -> list:
    return [
        source,
        item.get("ClusterKey") or item.get("Cluster") or FILTER_ALL,
        item.get("Namespace") or FILTER_ALL,
        item.get("Age") or FILTER_ALL,
        item.get("SreKey") or item.get("Ownership") or FILTER_ALL,
        int(item.get("Unique CVEs") or 0),
    ]


def _stat_metric_rows(analysis: dict, key: str) -> list[list]:
    """KPI rows with Ownership so SRE managed filters top counts.

    Additive KPIs: ``filterable_ownership`` slices + synthesized Age=``__ALL__``
    per real cluster×namespace×ownership (+ OwnershipAll for All).

    Unique CVEs: ClusterKey × SreKey exact distinct rollups (not additive).
    """
    rows: list[list] = []
    by_source = analysis.get("filterables_by_source") or {}
    metric = _KPI_METRIC_KEYS.get(key, key)
    if key == "Unique CVEs":
        for source in (SOURCE_ALL, SOURCE_REDHAT, SOURCE_NON_REDHAT):
            block = by_source.get(source) or {}
            for item in block.get("unique_cves_by_ownership_age") or []:
                rows.append(_unique_stat_item_row(source, item))
        # RH+NRS multi-select covers the full source population → All distinct.
        all_block = by_source.get(SOURCE_ALL) or {}
        for item in all_block.get("unique_cves_by_ownership_age") or []:
            rows.append(_unique_stat_item_row(SOURCE_BOTH, item))
        return rows
    for source in (SOURCE_ALL, SOURCE_REDHAT, SOURCE_NON_REDHAT):
        block = by_source.get(source) or {}
        items = block.get("filterable_ownership") or []
        age_all: dict[tuple[str, str, str], int] = {}
        for item in items:
            rows.append(_stat_item_row(source, item, key))
            cl = item.get("Cluster") or "Unknown"
            ns = item.get("Namespace") or "Unknown"
            own = item.get("Ownership") or ""
            if cl != FILTER_ALL and ns != FILTER_ALL and own:
                age_all[(cl, ns, own)] = age_all.get((cl, ns, own), 0) + int(
                    item.get(metric, 0) or 0
                )
        for (cl, ns, own), val in age_all.items():
            rows.append([source, cl, ns, FILTER_ALL, own, val, FILTER_ALL])
    return rows


def source_stat_row(analysis: dict, y: int) -> list[dict]:
    cards = [
        ("Total", _stat_metric_rows(analysis, "Total"), "blue", "sum", "value", False),
        (
            "Unique CVEs",
            _stat_metric_rows(analysis, "Unique CVEs"),
            "blue",
            "sum",
            "value",
            True,
        ),
        (
            "Fixable findings",
            _stat_metric_rows(analysis, "Fixable findings"),
            "purple",
            "sum",
            "value",
            False,
        ),
        ("Critical", _stat_metric_rows(analysis, "Critical"), "red", "sum", "value", False),
        (
            "Important",
            _stat_metric_rows(analysis, "Important"),
            "orange",
            "sum",
            "value",
            False,
        ),
        (
            "Moderate",
            _stat_metric_rows(analysis, "Moderate"),
            "dark-yellow",
            "sum",
            "value",
            False,
        ),
        ("Low", _stat_metric_rows(analysis, "Low"), "green", "sum", "value", False),
    ]
    panels = []
    x = 0
    for title, rows, color, calc, field, is_unique in cards:
        width = 3 if title in {"Critical", "Important", "Moderate", "Low"} else 4
        if is_unique:
            panels.append(
                sourced_unique_stat_panel(
                    title, rows, x, y, width, 4, color=color, value_field=field
                )
            )
        else:
            panels.append(
                sourced_stat_panel(
                    title, rows, x, y, width, 4, color=color, calc=calc, value_field=field
                )
            )
        x += width
    return panels


def tagged_rows(
    all_rows: list[list], redhat_rows: list[list], nonredhat_rows: list[list]
) -> list[list]:
    return (
        [[SOURCE_ALL, *row] for row in all_rows]
        + [[SOURCE_REDHAT, *row] for row in redhat_rows]
        + [[SOURCE_NON_REDHAT, *row] for row in nonredhat_rows]
    )


def namespace_table_rows(items: list[dict]) -> list[list]:
    """Cluster/namespace totals split by finding age. Grafana filters, then rolls up."""
    return [
        [
            item.get("Cluster") or "Unknown",
            item.get("Namespace") or "Unknown",
            item.get("Age") or "Unknown",
            int(item.get("Total", 0)),
            int(item.get("Critical", 0)),
            int(item.get("High", item.get("Important", 0))),
            int(item.get("Moderate", 0)),
            int(item.get("Low", 0)),
            item.get("ClusterAll") or FILTER_ALL,
            item.get("NsAll") or FILTER_ALL,
            item.get("AgeAll") or FILTER_ALL,
        ]
        for item in items
    ]


def component_rows(items: list[dict], limit: int = 200) -> list[list]:
    out = []
    for r in items[:limit]:
        out.append(
            [
                r["Component"],
                int(r["Total"]),
                int(r["Critical"]),
                int(r["High"]),
                int(r["Moderate"]),
                int(r["Low"]),
            ]
        )
    return out


def product_rows(items: list[dict], limit: int = 100) -> list[list]:
    out = []
    for r in items[:limit]:
        out.append(
            [
                r["Product"],
                int(r["Images"]),
                int(r["Finding occurrences"]),
                int(r["Fixable findings"]),
                int(r["Critical findings"]),
                int(r["Unique CVEs"]),
            ]
        )
    return out




def simple_view_table_rows(items: list[dict]) -> list[list]:
    headers = [
        "Cluster",
        "Namespace",
        "Image",
        "Namespace / deployment",
        "Age",
        "Oldest",
        "Critical",
        "Important",
        "Status",
        "ClusterAll",
        "NsAll",
        "AgeAll",
    ]
    return [[item.get(header, "") for header in headers] for item in items]


def sourced_simple_view_rows(analysis: dict) -> list[list]:
    """Tag Simple view rows with Source for the multi-select filter."""
    by_source = analysis.get("filterables_by_source") or {}
    out: list[list] = []
    for source in (SOURCE_ALL, SOURCE_REDHAT, SOURCE_NON_REDHAT):
        block = by_source.get(source) or {}
        items = block.get("simple_view")
        if items is None and source == SOURCE_ALL:
            items = analysis.get("simple_view") or []
        for row in simple_view_table_rows(items or []):
            out.append([source, *row])
    return out or [
        [
            SOURCE_ALL,
            "Unknown",
            "Unknown",
            "none",
            "none",
            "Unknown",
            "—",
            0,
            0,
            "needs_update",
            FILTER_ALL,
            FILTER_ALL,
            FILTER_ALL,
        ]
    ]


def sourced_filterable_rows(
    analysis: dict,
    key: str,
    row_fn,
    **kwargs,
) -> list[list]:
    """Prepend Source to filterable table rows for All / RH / Non-RH slices."""
    by_source = analysis.get("filterables_by_source") or {}
    out: list[list] = []
    for source in (SOURCE_ALL, SOURCE_REDHAT, SOURCE_NON_REDHAT):
        block = by_source.get(source) or {}
        items = block.get(key)
        if items is None and source == SOURCE_ALL:
            items = analysis.get(key) or []
        for row in row_fn(items or [], **kwargs):
            out.append([source, *row])
    return out


def ownership_rows(items: list[dict]) -> list[list]:
    return [
        [
            r["Ownership"],
            int(r["Findings"]),
            int(r["Critical"]),
            int(r["Important"]),
            int(r["Unique CVEs"]),
            int(r["Fixable Findings"]),
        ]
        for r in items
    ]


def ownership_component_rows(
    items: list[dict],
    limit: int = 200,
    *,
    with_repository: bool = False,
) -> list[list]:
    rows = []
    for item in items[:limit]:
        row = [
            item["Component"],
            int(item["Findings"]),
            int(item["Critical"]),
            int(item["Important"]),
            int(item["Unique CVEs"]),
            int(item["Fixable Findings"]),
            item["Action"],
        ]
        if with_repository:
            row.append(item.get("Repository") or "")
        rows.append(row)
    return rows


OPERATOR_UPDATES_UID = "ado-operator-updates"


def _subscription_has_update(item: dict) -> bool:
    installed = str(item.get("installed") or "<none>")
    current = str(item.get("current") or "<none>")
    state = str(item.get("state") or "")
    if state in {"UpgradeAvailable", "UpgradePending"}:
        return True
    if installed == "<none>" and current == "<none>":
        return False
    return installed != current


def operators_with_updates(subscriptions: list[dict]) -> list[dict]:
    """Operators the console would list, with a project count for each."""
    grouped: dict[str, dict] = {}
    for index, item in enumerate(subscriptions):
        if not _subscription_has_update(item):
            continue
        name = str(item.get("operator") or "").strip() or "unknown"
        namespace = str(item.get("namespace") or "").strip() or f"{name}#{index}"
        projects = int(item.get("projects") or 0)
        bucket = grouped.setdefault(name, {"namespaces": set(), "projects": 0})
        bucket["namespaces"].add(namespace)
        bucket["projects"] = max(bucket["projects"], projects, len(bucket["namespaces"]))
    rows = []
    for name, bucket in grouped.items():
        count = max(int(bucket["projects"]), len(bucket["namespaces"]))
        noun = "project" if count == 1 else "projects"
        rows.append(
            {
                "operator": name,
                "projects": count,
                "status": f"{count} {noun} upgrade available",
            }
        )
    rows.sort(key=lambda row: (-row["projects"], row["operator"].lower()))
    return rows


def operator_updates_tile(count: int, x: int, y: int, w: int, h: int) -> dict:
    panel = stat_panel(
        "Operators with updates",
        count,
        x,
        y,
        w,
        h,
        color="yellow" if count else "green",
    )
    panel["description"] = (
        "Operators whose installed version is behind the current one. "
        "Click the number for the list and how many projects each update covers."
    )
    panel["options"]["text"] = {"titleSize": 14, "valueSize": 28}
    panel["fieldConfig"]["defaults"]["links"] = [
        {
            "title": "Operators with updates (cluster-wide)",
            "url": f"/d/{OPERATOR_UPDATES_UID}/operators-with-updates",
            "targetBlank": False,
        }
    ]
    return panel


def build_operator_updates_dashboard(
    subscriptions: list[dict],
    posture_uid: str = "ado-rhacs-vuln-posture",
) -> dict:
    global _PANEL_ID
    _PANEL_ID = 0
    rows = operators_with_updates(subscriptions)
    if rows:
        table = table_panel(
            "Operators with updates",
            ["Operator", "Projects", "Update"],
            [[row["operator"], row["projects"], row["status"]] for row in rows],
            0,
            0,
            24,
            16,
            sort_by="Projects",
        )
        table["description"] = (
            "Same list as the OpenShift console Operators popover. "
            "Projects is how many namespaces have this operator's current or installed version."
        )
        panels = [table]
    else:
        panels = [
            markdown_panel(
                "Operators with updates",
                "No operators have an upgrade available.",
                0,
                0,
                24,
                6,
            )
        ]
    return {
        "uid": OPERATOR_UPDATES_UID,
        "title": "Operators with updates",
        "tags": ["openshift", "operators", "ado"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "",
        "editable": True,
        "graphTooltip": 0,
        "description": "Operators that have an upgrade available, and how many projects each one covers.",
        "panels": panels,
        "annotations": {"list": []},
        "templating": {"list": []},
        "links": [
            {
                "title": "RHACS vulnerability posture",
                "type": "link",
                "icon": "dashboard",
                "url": f"/d/{posture_uid}",
                "keepTime": True,
                "targetBlank": False,
            }
        ],
    }



def filterable_component_rows(
    items: list[dict],
    *,
    with_repository: bool = False,
    limit: int = 5000,
) -> list[list]:
    """Rows for namespace-aware component/image tables."""
    rows: list[list] = []
    for item in (items or [])[:limit]:
        row = [
            item.get("Cluster") or "Unknown",
            item.get("Namespace") or "Unknown",
            item.get("Age") or "Unknown",
            item.get("Ownership") or "",
            item.get("Component") or "Unknown",
            int(item.get("Findings") or 0),
            int(item.get("Critical") or 0),
            int(item.get("Important") or 0),
            int(item.get("Unique CVEs") or 0),
            int(item.get("Fixable Findings") or 0),
            item.get("Action") or "Review",
            item.get("ClusterAll") or FILTER_ALL,
            item.get("NsAll") or FILTER_ALL,
            item.get("AgeAll") or FILTER_ALL,
            item.get("OwnershipAll") or FILTER_ALL,
        ]
        if with_repository:
            row.insert(5, item.get("Repository") or "")
        rows.append(row)
    return rows


def filterable_namespace_findings_rows(
    items: list[dict], *, limit: int = 5000
) -> list[list]:
    """Component×ownership slices for Findings by namespace (filter then roll up)."""
    rows: list[list] = []
    for item in (items or [])[:limit]:
        rows.append(
            [
                item.get("Cluster") or "Unknown",
                item.get("Namespace") or "Unknown",
                item.get("Age") or "Unknown",
                item.get("Ownership") or "",
                item.get("Component") or "Unknown",
                int(item.get("Findings") or 0),
                int(item.get("Critical") or 0),
                int(item.get("High") or item.get("Important") or 0),
                int(item.get("Moderate") or 0),
                int(item.get("Low") or 0),
                item.get("ClusterAll") or FILTER_ALL,
                item.get("NsAll") or FILTER_ALL,
                item.get("AgeAll") or FILTER_ALL,
                item.get("OwnershipAll") or FILTER_ALL,
            ]
        )
    return rows


def filterable_ownership_rows(items: list[dict]) -> list[list]:
    return [
        [
            r.get("Cluster") or "Unknown",
            r.get("Namespace") or "Unknown",
            r.get("Age") or "Unknown",
            r["Ownership"],
            int(r["Findings"]),
            int(r["Critical"]),
            int(r["Important"]),
            int(r["Unique CVEs"]),
            int(r["Fixable Findings"]),
            r.get("ClusterAll") or FILTER_ALL,
            r.get("NsAll") or FILTER_ALL,
            r.get("AgeAll") or FILTER_ALL,
            r.get("OwnershipAll") or FILTER_ALL,
        ]
        for r in (items or [])
    ]


def filterable_remediation_rows(items: list[dict]) -> list[list]:
    return [
        [
            r.get("Cluster") or "Unknown",
            r.get("Namespace") or "Unknown",
            r.get("Age") or "Unknown",
            r.get("Ownership") or "",
            r["Remediation Path"],
            int(r["Findings"]),
            int(r["Critical"]),
            int(r["Important"]),
            int(r["Unique CVEs"]),
            int(r["Fixable Findings"]),
            int(r.get("Products") or 0),
            r.get("ClusterAll") or FILTER_ALL,
            r.get("NsAll") or FILTER_ALL,
            r.get("AgeAll") or FILTER_ALL,
            r.get("OwnershipAll") or FILTER_ALL,
        ]
        for r in (items or [])
    ]


def remediation_rows(items: list[dict]) -> list[list]:
    return [
        [
            r["Remediation Path"],
            int(r["Findings"]),
            int(r["Critical"]),
            int(r["Important"]),
            int(r["Unique CVEs"]),
            int(r["Fixable Findings"]),
            int(r["Products"]),
        ]
        for r in items
    ]


def _truthy_env(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _cve_intel_panels_enabled(uid: str, *, cve_intel_panels: bool = False) -> bool:
    """Approved Phase 0 / nonprod UIDs only; never production. Flag-gated (default off)."""
    if not is_phase0_feature_uid(uid):
        return False
    if cve_intel_panels:
        return True
    return _truthy_env("CVE_ANALYZER_CVE_INTEL_PANELS")


def build_dashboard(
    analysis: dict,
    title: str,
    uid: str,
    prometheus_datasource_uid: str = "Openshift-Prod",
    *,
    lite: bool = False,
    cve_intel_panels: bool = False,
) -> dict:
    """Build the RHACS posture dashboard.

    ``lite=True`` (Phase 0 Lite): omit panel 90 Detail rows and drill-down
    cell links so the Grafana publish body stays under the 16 MiB API limit.
    Summary/KPI panels and panel 11 PromQL stay identical to Full. Default
    ``lite=False`` preserves accepted Full behavior.
    """
    global _PANEL_ID
    _PANEL_ID = 0

    a = analysis["all"]
    rh = analysis["redhat"]
    nrs = analysis.get("non_redhat_sources") or {}
    panels: list[dict] = []
    scope_meta = analysis.get("cluster_scope") or {}
    phase1_trend = phase1_filterable_trend(uid)
    # Dropdown / All-scope must come from board data + cve_analyzer_clusters —
    # never from the full-report by-cluster metric keys alone.
    cluster_values = sorted(
        {
            str(item.get("Cluster") or "Unknown")
            for item in (a.get("by_namespace") or [])
            + (rh.get("by_namespace") or [])
            + (analysis.get("filterable_remediation") or [])
            + (analysis.get("drilldown") or [])
            + (analysis.get("simple_view") or [])
            if str(item.get("Cluster") or "").strip()
            and str(item.get("Cluster")) != FILTER_ALL
        }
    )
    phase1_scope_clusters = dashboard_scope_clusters(scope_meta, cluster_values)

    def drill_opt(spec: dict | None) -> dict | None:
        """Attach Detail drill links only in Full mode (no broken Lite links)."""
        return None if lite else spec

    if lite and "Lite" not in title:
        title = f"{title} [Lite — Detail omitted]"

    send_url = (analysis.get("send_report_url") or "").strip()
    acs_url = (analysis.get("acs_central_url") or "").strip().rstrip("/")
    header_links = []
    if acs_url:
        header_links.append(new_tab_link("ACS", acs_url))
    if send_url:
        header_links.append(new_tab_link("Send report", send_url))
    header_extra = (" &nbsp;&nbsp; " + " &nbsp;&nbsp; ".join(header_links)) if header_links else ""
    lite_banner = ""
    if lite:
        lite_banner = (
            "\n\n> **Phase 0 Lite** — Detail (panel 90) and cell drill-downs are "
            "omitted so Grafana publish stays under the 16 MB limit. Summary "
            "KPI panels and historical trends are unchanged. Not a replacement "
            "for the accepted Full dashboard."
        )
    _cs = analysis.get("cluster_scope") or {}
    if _cs.get("all_clusters", True):
        cluster_banner = "\n\n**Dashboard clusters:** all (metrics: all-cluster)."
    else:
        cluster_banner = (
            "\n\n**Dashboard clusters:** "
            + ", ".join(_cs.get("selected") or [])
            + " (metrics remain all-cluster)."
        )
    panels.append(
        markdown_panel(
            "",
            (
                f"### RHACS vulnerability posture{header_extra}\n\n"
                f"**Report pulled:** {analysis.get('report_pulled') or analysis['generated_at']}"
                f"{cluster_banner}"
                f"{lite_banner}"
            ),
            0,
            0,
            14,
            3,
        )
    )
    panels.append(openshift_version_panel(14, 0, 10, 1))
    # The version badge is one row. The tile under it fills the same two rows
    # so Important and Moderate stay on the same line as the other stat cards.
    panels.append(
        operator_updates_tile(
            len(operators_with_updates(analysis.get("operator_subscriptions") or [])),
            14,
            1,
            10,
            2,
        )
    )

    # One set of cards. Source chooses All, Red Hat, or Non-Red Hat.
    panels.extend(source_stat_row(analysis, y=3))
    # Extra rows for temporary legacy reference panel on Phase 1 test boards only.
    trend_layout_dy = 8 if phase1_trend else 0
    if phase1_trend:
        panels.append(
            filterable_findings_trend_panel(
                0,
                7,
                24,
                8,
                prometheus_datasource_uid,
                cluster_scope=scope_meta,
                scope_clusters=phase1_scope_clusters,
                hybrid=phase1_hybrid_trend(uid),
            )
        )
        # Temporary: keep locked all-cluster history while by-cluster scrapes accumulate.
        panels.append(
            legacy_findings_trend_panel(0, 15, 24, 8, prometheus_datasource_uid)
        )
    else:
        panels.append(
            findings_trend_panel(
                0,
                7,
                24,
                8,
                prometheus_datasource_uid,
                cluster_scope=scope_meta,
            )
        )

    # Component / SRE / Finding age must filter this table. Coarse by_namespace
    # rows lack those dimensions — build from filterable_all_components, then
    # roll up to Cluster×Namespace after toolbar filters.
    ns_findings_headers = [
        "Source",
        "Cluster",
        "Namespace",
        "Age",
        "Ownership",
        "Component",
        "Total",
        "Critical",
        "High",
        "Moderate",
        "Low",
        "ClusterAll",
        "NsAll",
        "AgeAll",
        "OwnershipAll",
    ]
    panels.append(
        table_panel(
            "Findings by namespace",
            ns_findings_headers,
            sourced_filterable_rows(
                analysis, "filterable_all_components", filterable_namespace_findings_rows
            ),
            0,
            56 + trend_layout_dy,
            24,
            14,
            by_source=True,
            filters=[
                *ns_dim_filters(),
                finding_age_filter(),
                ownership_filter(),
                multi_regex_filter("Component", "component"),
            ],
            post_filters=rollup_after_namespace(
                ["Cluster", "Namespace"],
                ["Total", "Critical", "High", "Moderate", "Low"],
                {},
            ),
            hide=[
                "Age",
                "Ownership",
                "Component",
                "ClusterAll",
                "NsAll",
                "AgeAll",
                "OwnershipAll",
            ],
            drill=drill_opt(
                {"variable": "namespace", "field": "Namespace", "row_cluster": True}
            ),
        )
    )

    filterable_comp_headers = [
        "Source",
        "Cluster",
        "Namespace",
        "Age",
        "Ownership",
        "Component",
        "Findings",
        "Critical",
        "Important",
        "Unique CVEs",
        "Fixable Findings",
        "Action",
        "ClusterAll",
        "NsAll",
        "AgeAll",
        "OwnershipAll",
    ]
    filterable_comp_repo_headers = [
        "Source",
        "Cluster",
        "Namespace",
        "Age",
        "Ownership",
        "Component",
        "Repository",
        "Findings",
        "Critical",
        "Important",
        "Unique CVEs",
        "Fixable Findings",
        "Action",
        "ClusterAll",
        "NsAll",
        "AgeAll",
        "OwnershipAll",
    ]
    vuln_ns_filters = [
        *ns_dim_filters(),
        finding_age_filter(),
        ownership_filter(),
        multi_regex_filter("Component", "component"),
    ]
    panels.append(
        table_panel(
            "All components",
            filterable_comp_headers,
            sourced_filterable_rows(
                analysis, "filterable_all_components", filterable_component_rows
            ),
            12,
            70 + trend_layout_dy,
            12,
            12,
            by_source=True,
            filters=vuln_ns_filters,
            post_filters=rollup_after_namespace(
                ["Cluster", "Component"],
                ["Findings", "Critical", "Important", "Unique CVEs", "Fixable Findings"],
                {},
            ),
            hide=["Namespace", "Age", "Ownership", "ClusterAll", "NsAll", "AgeAll", "OwnershipAll"],
            label_header="Component",
            drill=drill_opt(
                {"variable": "component", "field": "Component", "row_cluster": True}
            ),
        )
    )

    panels.append(
        sourced_bargauge_panel(
            "Critical findings by namespace",
            a["critical_by_namespace"] or [("none", 0)],
            rh["critical_by_namespace"] or [("none", 0)],
            nrs.get("critical_by_namespace") or [("none", 0)],
            0,
            15 + trend_layout_dy,
            24,
            10,
        )
    )

    panels.append(platform_payload_bars(analysis, 0, 25 + trend_layout_dy, 24, 10))

    age_critical = ocp_age_table_panel(
        "Critical CVEs by age — SRE-managed OpenShift (cluster-wide)",
        analysis,
        critical=True,
        x=0,
        y=35 + trend_layout_dy,
        w=12,
        h=9,
        drill=drill_opt(
            {
                "variable": "age",
                "field": "Age bucket",
                "fixed": {
                    "severity": "Critical",
                    "payload": "Yes",
                    "sre": "Red Hat SRE Managed Services",
                },
            }
        ),
    )
    age_important = ocp_age_table_panel(
        "Important CVEs by age — SRE-managed OpenShift (cluster-wide)",
        analysis,
        critical=False,
        x=12,
        y=35 + trend_layout_dy,
        w=12,
        h=9,
        drill=drill_opt(
            {
                "variable": "age",
                "field": "Age bucket",
                "fixed": {
                    "severity": "Important",
                    "payload": "Yes",
                    "sre": "Red Hat SRE Managed Services",
                },
            }
        ),
    )
    if lite:
        unavailable = (
            "Detail drill-down unavailable in Phase 0 Lite "
            "(panel 90 omitted for Grafana size)."
        )
        age_critical["description"] = (
            (age_critical.get("description") or "") + "\n\n" + unavailable
        )
        age_important["description"] = (
            (age_important.get("description") or "") + "\n\n" + unavailable
        )
    panels.append(age_critical)
    panels.append(age_important)

    panels.append(
        table_panel(
            "All images",
            filterable_comp_repo_headers,
            sourced_filterable_rows(
                analysis,
                "filterable_all_images",
                filterable_component_rows,
                with_repository=True,
            ),
            0,
            82 + trend_layout_dy,
            24,
            12,
            by_source=True,
            filters=vuln_ns_filters,
            post_filters=rollup_after_namespace(
                ["Cluster", "Component", "Repository"],
                ["Findings", "Critical", "Important", "Unique CVEs", "Fixable Findings"],
                {},
            ),
            hide=["Namespace", "Age", "Ownership", "ClusterAll", "NsAll", "AgeAll", "OwnershipAll"],
            conceal=["Repository"],
            label_header="Component",
            drill=drill_opt(
                {
                    "variable": "image",
                    "field": "Component",
                    "source": "Repository",
                    "row_cluster": True,
                }
            ),
        )
    )

    def _over30_rows(items: list[dict]) -> list[list]:
        return [
            [
                r.get("Cluster") or "Unknown",
                r.get("Namespace") or r.get("Component"),
                r.get("Age") or "Unknown",
                int(r["Critical"]),
                int(r["High"]),
                int(r["Total >30 Days"]),
                r.get("ClusterAll") or FILTER_ALL,
                r.get("NsAll") or FILTER_ALL,
                r.get("AgeAll") or FILTER_ALL,
            ]
            for r in items
        ]

    panels.append(
        table_panel(
            "Unique CVEs older than 30 days by namespace",
            [
                "Source",
                "Cluster",
                "Namespace",
                "Age",
                "Critical",
                "High",
                "Total >30 Days",
                "ClusterAll",
                "NsAll",
                "AgeAll",
            ],
            sourced_filterable_rows(analysis, "component_over_30", _over30_rows),
            0,
            44 + trend_layout_dy,
            12,
            12,
            by_source=True,
            filters=[*ns_dim_filters(), finding_age_filter()],
            post_filters=rollup_after_namespace(
                ["Cluster", "Namespace"],
                ["Critical", "High", "Total >30 Days"],
                {},
            ),
            conceal=["Cluster", "Age", "ClusterAll", "NsAll", "AgeAll"],
            drill=drill_opt(
                {
                    "variable": "namespace",
                    "field": "Namespace",
                    "row_cluster": True,
                    "fixed": {"over30": "Yes", "severity": "(Critical|Important)"},
                }
            ),
        )
    )

    panels.append(
        table_panel(
            "Finding ownership",
            [
                "Source",
                "Cluster",
                "Namespace",
                "Age",
                "Ownership",
                "Findings",
                "Critical",
                "Important",
                "Unique CVEs",
                "Fixable Findings",
                "ClusterAll",
                "NsAll",
                "AgeAll",
        "OwnershipAll",
            ],
            sourced_filterable_rows(
                analysis, "filterable_ownership", filterable_ownership_rows
            ),
            0,
            106 + trend_layout_dy,
            9,
            10,
            by_source=True,
            filters=[
                *ns_dim_filters(),
                finding_age_filter(),
                ownership_filter(),
            ],
            post_filters=rollup_after_namespace(
                ["Ownership"],
                ["Findings", "Critical", "Important", "Unique CVEs", "Fixable Findings"],
                {},
            ),
            hide=["Cluster", "Namespace", "Age", "ClusterAll", "NsAll", "AgeAll",
        "OwnershipAll"],
            drill=drill_opt({"variable": "sre", "field": "Ownership"}),
        )
    )

    panels.append(
        table_panel(
            "Red Hat SRE Managed Services",
            filterable_comp_headers,
            sourced_filterable_rows(
                analysis,
                "filterable_sre_managed_components",
                filterable_component_rows,
            ),
            9,
            106 + trend_layout_dy,
            15,
            10,
            by_source=True,
            filters=vuln_ns_filters,
            post_filters=rollup_after_namespace(
                ["Cluster", "Component"],
                ["Findings", "Critical", "Important", "Unique CVEs", "Fixable Findings"],
                {},
            ),
            hide=["Namespace", "Age", "Ownership", "ClusterAll", "NsAll", "AgeAll", "OwnershipAll"],
            label_header="Component",
            drill=drill_opt(
                {
                    "variable": "component",
                    "field": "Component",
                    "row_cluster": True,
                    "fixed": {"sre": "Red Hat SRE Managed Services"},
                }
            ),
        )
    )
    panels.append(
        table_panel(
            "Red Hat Components",
            filterable_comp_headers,
            sourced_filterable_rows(
                analysis, "filterable_redhat_components", filterable_component_rows
            ),
            0,
            70 + trend_layout_dy,
            12,
            12,
            by_source=True,
            filters=vuln_ns_filters,
            post_filters=rollup_after_namespace(
                ["Cluster", "Component"],
                ["Findings", "Critical", "Important", "Unique CVEs", "Fixable Findings"],
                {},
            ),
            hide=["Namespace", "Age", "Ownership", "ClusterAll", "NsAll", "AgeAll", "OwnershipAll"],
            label_header="Component",
            drill=drill_opt(
                {
                    "variable": "component",
                    "field": "Component",
                    "row_cluster": True,
                    "fixed": {"sre": "Red Hat Components"},
                }
            ),
        )
    )
    panels.append(
        table_panel(
            "Non-Red Hat images",
            filterable_comp_repo_headers,
            sourced_filterable_rows(
                analysis,
                "filterable_non_redhat_components",
                filterable_component_rows,
                with_repository=True,
            ),
            0,
            94 + trend_layout_dy,
            24,
            12,
            by_source=True,
            filters=vuln_ns_filters,
            post_filters=rollup_after_namespace(
                ["Cluster", "Component", "Repository"],
                ["Findings", "Critical", "Important", "Unique CVEs", "Fixable Findings"],
                {},
            ),
            hide=["Namespace", "Age", "Ownership", "ClusterAll", "NsAll", "AgeAll", "OwnershipAll"],
            conceal=["Repository"],
            label_header="Component",
            drill=drill_opt(
                {
                    "variable": "image",
                    "field": "Component",
                    "source": "Repository",
                    "row_cluster": True,
                    "fixed": {"sre": "Non-Red Hat"},
                }
            ),
        )
    )
    panels.append(
        table_panel(
            "Remediation Paths",
            [
                "Source",
                "Cluster",
                "Namespace",
                "Age",
                "Ownership",
                "Remediation Path",
                "Findings",
                "Critical",
                "Important",
                "Unique CVEs",
                "Fixable Findings",
                "Products",
                "ClusterAll",
                "NsAll",
                "AgeAll",
        "OwnershipAll",
            ],
            sourced_filterable_rows(
                analysis, "filterable_remediation", filterable_remediation_rows
            ),
            12,
            44 + trend_layout_dy,
            12,
            12,
            by_source=True,
            filters=[
                *ns_dim_filters(),
                finding_age_filter(),
                ownership_filter(),
            ],
            post_filters=rollup_after_namespace(
                ["Remediation Path"],
                [
                    "Findings",
                    "Critical",
                    "Important",
                    "Unique CVEs",
                    "Fixable Findings",
                    "Products",
                ],
                {},
            ),
            hide=[
                "Cluster",
                "Namespace",
                "Age",
                "Ownership",
                "ClusterAll",
                "NsAll",
                "AgeAll",
                "OwnershipAll",
            ],
        )
    )

    subscriptions = analysis.get("operator_subscriptions") or []
    if subscriptions:
        bottom = max(panel["gridPos"]["y"] + panel["gridPos"]["h"] for panel in panels)
        panels.append(operator_subscription_panel(subscriptions, 0, bottom, 24, 16))

    simple_headers = [
        "Source",
        "Cluster",
        "Namespace",
        "Image",
        "Namespace / deployment",
        "Age",
        "Oldest",
        "Critical",
        "Important",
        "Status",
        "ClusterAll",
        "NsAll",
        "AgeAll",
    ]
    simple_bottom = max(panel["gridPos"]["y"] + panel["gridPos"]["h"] for panel in panels)
    simple = table_panel(
        "Simple view",
        simple_headers,
        sourced_simple_view_rows(analysis),
        0,
        simple_bottom,
        24,
        14,
        by_source=True,
        filters=[*ns_dim_filters(), finding_age_filter()],
        hide=["Cluster", "Namespace", "Age", "ClusterAll", "NsAll", "AgeAll"],
        label_header="Image",
        sort_by="Critical",
    )
    simple["description"] = (
        "Same shape as OpenShift Lifecycle Discover Images: fixable Critical/Important "
        "by cluster, namespace, and image. Cluster, Source, Namespace, and Finding age "
        "filters apply. Oldest is Discover-style days within the selected age bucket. "
        "Severity / Component / SRE managed are not row dimensions on this panel."
    )
    panels.append(simple)

    detail_bottom = max(panel["gridPos"]["y"] + panel["gridPos"]["h"] for panel in panels)
    if lite:
        panels.append(
            markdown_panel(
                "Detail (unavailable in Phase 0 Lite)",
                (
                    "Detail dataset (panel id 90) is **omitted** in Lite mode so the "
                    "Grafana API publish stays under 16 MB. Cell drill-downs that "
                    "would open Detail are disabled — no broken Detail links. "
                    "Re-enable Full mode (`cve_analyzer_dashboard_lite: false`) after "
                    "a Detail size fix to restore drill-down."
                ),
                0,
                detail_bottom,
                24,
                4,
            )
        )
    else:
        detail_headers = [
            "Source",
            "Cluster",
            "Namespace",
            "Ownership",
            "Component",
            "Image",
            "CVE",
            "Severity",
            "Age",
            "Age bucket",
            "Over 30",
            "Payload",
            "Action",
            "Repository",
            "Show",
            "ClusterAll",
            "NsAll",
            "AgeAll",
        "OwnershipAll",
            "SourceAll",
        ]
        detail_rows: list[list] = []
        for item in analysis.get("drilldown") or []:
            detail_rows.append(
                [
                    SOURCE_ALL
                    if header == "SourceAll"
                    else (
                        FILTER_ALL
                        if header in {"ClusterAll", "NsAll", "AgeAll"}
                        else item.get(header, "")
                    )
                    for header in detail_headers
                ]
            )
        # Do not use by_source=True here: that applies source_filter() on Source
        # only and previously required a doubled SOURCE_ALL copy per row.
        detail = table_panel(
            "Detail for the row you clicked",
            detail_headers,
            detail_rows,
            0,
            detail_bottom,
            24,
            14,
            by_source=False,
            filters=[
                detail_source_filter(),
                regex_filter("Show", "picked"),
                *ns_dim_filters(),
                finding_age_filter(),
                ownership_filter(),
                multi_regex_filter("Component", "component"),
                regex_filter("Repository", "image"),
                regex_filter("Age bucket", "age"),
                (
                    multi_regex_filter("Severity", "severity")
                    if phase1_trend
                    else regex_filter("Severity", "severity")
                ),
                regex_filter("Over 30", "over30"),
                regex_filter("Payload", "payload"),
            ],
            hide=[
                "Repository",
                "Show",
                "Age",
                "ClusterAll",
                "NsAll",
                "AgeAll",
                "SourceAll",
            ],
            label_header="CVE",
        )
        detail["id"] = DETAIL_PANEL_ID
        detail["description"] = (
            "CVE findings for the value you clicked (opens in a new tab so the main "
            "board filters stay put — close the tab or use Return below; do not rely "
            f"on browser Back). [Return to dashboard](/d/{uid}?orgId=1&var-picked=none)"
        )
        panels.append(detail)

    if _cve_intel_panels_enabled(uid, cve_intel_panels=cve_intel_panels):
        from cve_intel.build_cve_intel_panels import (  # noqa: WPS433
            DEFAULT_POSTGRES_UID,
            intel_section_panels,
        )

        postgres_uid = (
            os.environ.get("CVE_ANALYZER_CVE_INTEL_POSTGRES_UID") or DEFAULT_POSTGRES_UID
        ).strip()
        # Place Recent reports immediately above Detail (panel 90), not after it.
        detail = next((p for p in panels if p.get("id") == DETAIL_PANEL_ID), None)
        if detail is not None:
            y_start = int(detail["gridPos"]["y"])
        else:
            y_start = max(p["gridPos"]["y"] + p["gridPos"]["h"] for p in panels)
        intel_panels: list[dict] = []
        for panel in intel_section_panels(y_start=y_start, postgres_uid=postgres_uid):
            panel = dict(panel)
            panel["id"] = next_id()
            # Keep Detail panel id 90 stable even if next_id already passed it.
            if panel["id"] == DETAIL_PANEL_ID:
                panel["id"] = next_id()
            intel_panels.append(panel)
        intel_height = sum(int(p["gridPos"]["h"]) for p in intel_panels)
        if detail is not None and intel_height:
            detail["gridPos"] = dict(detail["gridPos"])
            detail["gridPos"]["y"] = y_start + intel_height
        # Insert before Detail so panel order matches visual top→bottom.
        if detail is not None:
            di = next(i for i, p in enumerate(panels) if p.get("id") == DETAIL_PANEL_ID)
            panels[di:di] = intel_panels
        else:
            panels.extend(intel_panels)

    namespace_values = [
        item.get("Namespace") or "Unknown"
        for item in (a.get("by_namespace") or []) + (rh.get("by_namespace") or [])
    ]
    namespace_values.extend(item[0] for item in (a.get("critical_by_namespace") or []) if item)
    namespace_values.extend(item[0] for item in (rh.get("critical_by_namespace") or []) if item)
    namespace_values.extend(
        row.get("Namespace") or row.get("Component")
        for row in (analysis.get("component_over_30") or [])
    )
    component_values = [
        row["Product"] for row in (a["product_lines"] + rh["product_lines"])
    ]
    component_values.extend(
        row["Component"]
        for row in (analysis.get("sre_managed_components") or [])
        + (analysis.get("redhat_components") or [])
        + (analysis.get("non_redhat_components") or [])
        + (analysis.get("all_components") or [])
        + (analysis.get("all_images") or [])
    )
    component_values.extend(
        row["Current image family"] for row in (analysis.get("image_families") or [])
    )

    fingerprint = builder_fingerprint_tag()
    return {
        "uid": uid,
        "title": title,
        "tags": [
            "rhacs",
            "cve",
            "security",
            "ado",
            "ownership",
            fingerprint,
        ],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "",
        "time": {"from": "now-90d", "to": "now"},
        "editable": True,
        "graphTooltip": 1,
        "description": (
            f"Live RHACS posture from CVE Analyzer. CSV {analysis.get('csv_report_name', analysis['report_date'])}. "
            f"Updated {analysis['generated_at']}. Ownership + remediation path tables. "
            f"Builder fingerprint {fingerprint}. "
            + (
                "Clusters: all. "
                if (analysis.get("cluster_scope") or {}).get("all_clusters", True)
                else "Clusters: "
                + ",".join((analysis.get("cluster_scope") or {}).get("selected") or [])
                + " (dashboard scope). "
            )
            + (
                "Findings trend filters by Cluster/Severity/Namespace; "
                "legacy all-cluster reference panel retained. "
                if phase1_trend
                else "Findings trend is all-cluster historical (not Cluster/Severity filtered). "
            )
        ),
        "panels": panels,
        "annotations": {"list": []},
        "templating": {
            "list": [
                search_variable(
                    "cluster",
                    "Cluster",
                    cluster_values,
                    sort=5,
                    multi=True,
                    # Always scoped clusters + __ALL__ (tables + PromQL + KPI).
                    # Bare __ALL__ zeros additive KPIs (rows use real cluster names).
                    all_value=dashboard_cluster_all_value(phase1_scope_clusters),
                ),
                source_variable(),
                search_variable(
                    "namespace",
                    "Namespace",
                    namespace_values,
                    sort=5,
                    multi=True,
                    # Board namespaces + __ALL__ so Panel 11 PromQL and KPI All
                    # match real labels (not Unique-CVE rollups only).
                    all_value=dashboard_namespace_all_value(namespace_values),
                ),
                {
                    "name": "namespace_match",
                    "label": "Namespace matches",
                    "type": "textbox",
                    "query": ".*",
                    "current": {"selected": True, "text": ".*", "value": ".*"},
                    "options": [],
                    "hide": 0,
                    "skipUrlSync": False,
                    "description": (
                        "Regex against Namespace (default .* = unrestricted). "
                        "Combined with the Namespace dropdown on Panel 11 "
                        f"({POSTURE_METRIC_BY_NS}). "
                        "Invalid regex fails the trend query (shows an error) — "
                        "it does not silently match all namespaces. "
                        "Example: .*devspaces.*."
                    ),
                },
                search_variable(
                    "finding_age",
                    "Finding age",
                    list(FINDING_AGE_BUCKETS) + ["Unknown"],
                    multi=True,
                    sort=0,
                    preserve_order=True,
                    all_value=FILTER_ALL,
                ),
                search_variable(
                    "component",
                    "Component",
                    component_values,
                    sort=5,
                    multi=True,
                    all_value=".*",
                ),
                sre_variable(),
                search_variable(
                    "image",
                    "Image",
                    [row.get("Repository", "") for row in (analysis.get("drilldown") or [])],
                    hide=2,
                ),
                search_variable("age", "Age", list(AGE_BUCKETS) + ["Unknown"], hide=2),
                # Severity toolbar removed — trend always shows all severities.
                # Hidden var kept so Detail drill links that pin severity still work.
                search_variable(
                    "severity",
                    "Severity",
                    ["Critical", "Important", "Moderate", "Low", "Total"],
                    multi=True,
                    all_value=TREND_SEVERITY_FILTER,
                    hide=2,
                ),
                search_variable("over30", "Older than 30 days", ["Yes", "No"], hide=2),
                search_variable("payload", "OpenShift payload", ["Yes", "No"], hide=2),
                search_variable(
                    "picked",
                    "Detail",
                    ["yes", "none"],
                    hide=2,
                    current={"selected": True, "text": "none", "value": "none"},
                ),
                # Hidden: trend datasource + OCP version query (not ACS cluster filter).
                prometheus_variable(prometheus_datasource_uid),
                openshift_version_variable(),
            ]
        },
        "links": [],
    }



def _load_installed_images(path: str) -> dict[str, set[str]] | None:
    if not path:
        return None
    file = Path(path)
    if not file.exists():
        return None
    raw = json.loads(file.read_text(encoding="utf-8"))
    installed: dict[str, set[str]] = {}
    if not isinstance(raw, dict):
        return None
    for repository, tags in raw.items():
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            continue
        clean = {str(tag) for tag in tags if str(tag).strip()}
        if clean:
            installed[str(repository)] = clean
    return installed or None


def _load_operator_subscriptions(path: str) -> list[dict]:
    if not path:
        return []
    file = Path(path)
    if not file.exists():
        return []
    raw = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def newest_scrubbed(data_dir: Path) -> Path | None:
    files = list(data_dir.glob("RHACS_Vulnerability_Report_SCRUBBED_*.csv"))
    if not files:
        return None
    return max(files, key=lambda path: (scrubbed_pull_time(path), path.stat().st_mtime))



def serialize_dashboard_json(dash: dict, *, compact: bool = True) -> str:
    """Serialize dashboard for Grafana publish.

    Phase 4C-1: compact (no indent) is the default publish format. Pretty
    indent=2 remains available for local debug comparison only.
    """
    if compact:
        return json.dumps(dash, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(dash, ensure_ascii=False, indent=2)


def main() -> None:
    fingerprint = builder_fingerprint_tag()
    print(
        f"RHACS dashboard builder fingerprint: {fingerprint} "
        f"sha256={builder_source_sha256()}",
        flush=True,
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("data_json", nargs="?", default="")
    ap.add_argument("out_json")
    ap.add_argument("--title", default="RHACS Vulnerability Posture (ADO)")
    ap.add_argument("--uid", default="ado-rhacs-vuln-posture")
    ap.add_argument("--scrubbed-csv", default="")
    ap.add_argument("--families-yaml", default="")
    ap.add_argument("--report-date", default="", help="YYYY-MM-DD (default: latest discovered / now)")
    ap.add_argument("--data-dir", default="", help="Auto-pick newest scrubbed CSV from this dir")
    ap.add_argument(
        "--prometheus-datasource-uid",
        default="Openshift-Prod",
        help="Grafana datasource UID for the findings trend",
    )
    ap.add_argument(
        "--metrics-out",
        default="",
        help="Write cve_posture_findings gauges for the Prometheus textfile",
    )
    ap.add_argument("--send-report-url", default="", help="Header link for the send-report job")
    ap.add_argument(
        "--acs-central-url",
        default="",
        help="RHACS Central URL for the ACS header link",
    )
    ap.add_argument("--installed-images", default="", help="JSON map of repository to running tags")
    ap.add_argument("--operator-subscriptions", default="", help="JSON list of OLM subscriptions")
    ap.add_argument(
        "--lite",
        action="store_true",
        help=(
            "Phase 0 Lite: omit panel 90 Detail dataset and drill-down links "
            "(Grafana 16 MB publish). Also set CVE_ANALYZER_DASHBOARD_LITE=true."
        ),
    )
    ap.add_argument(
        "--cve-intel-panels",
        action="store_true",
        help=(
            "Append Red Hat CVE Intelligence Postgres panels on approved Phase 0 / "
            "nonprod UIDs (see CVE_ANALYZER_PHASE0_FEATURE_UIDS). "
            "Also CVE_ANALYZER_CVE_INTEL_PANELS=true. Never applies to production UID."
        ),
    )
    ap.add_argument(
        "--cluster",
        action="append",
        default=[],
        dest="clusters",
        help=(
            "RHACS cluster name to include in the dashboard (repeatable). "
            "Empty = all clusters. Exact names only. Also CVE_ANALYZER_CLUSTERS "
            "comma-separated. Metrics gauges always use all clusters."
        ),
    )
    args = ap.parse_args()
    lite = bool(args.lite) or (
        (os.environ.get("CVE_ANALYZER_DASHBOARD_LITE") or "").strip().lower()
        in ("1", "true", "yes", "on")
    )
    cve_intel_panels = bool(args.cve_intel_panels) or (
        (os.environ.get("CVE_ANALYZER_CVE_INTEL_PANELS") or "").strip().lower()
        in ("1", "true", "yes", "on")
    )
    clusters = [str(name).strip() for name in (args.clusters or []) if str(name).strip()]
    env_clusters = (os.environ.get("CVE_ANALYZER_CLUSTERS") or "").strip()
    if env_clusters and not clusters:
        clusters = [part.strip() for part in env_clusters.split(",") if part.strip()]

    data_json = Path(args.data_json) if args.data_json else None
    scrubbed = Path(args.scrubbed_csv) if args.scrubbed_csv else None
    if args.data_dir and not scrubbed:
        scrubbed = newest_scrubbed(Path(args.data_dir))
    if scrubbed is None and data_json is not None:
        scrubbed = newest_scrubbed(data_json.parent)

    families = Path(args.families_yaml) if args.families_yaml else None
    if families is None:
        for cand in (
            Path("image_families.yaml"),
            Path(__file__).with_name("image_families.yaml"),
        ):
            if cand.exists():
                families = cand
                break

    report_date = None
    if args.report_date:
        report_date = datetime.fromisoformat(args.report_date).replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )

    t_total = time.perf_counter()
    installed = _load_installed_images(args.installed_images)
    analysis = analyze_paths(
        scrubbed,
        data_json,
        families,
        report_date=report_date,
        installed=installed,
        clusters=clusters,
    )
    subscriptions = _load_operator_subscriptions(args.operator_subscriptions)
    if subscriptions:
        analysis["operator_subscriptions"] = subscriptions
    scope = analysis.get("cluster_scope") or {}
    dash_scope = (
        "all"
        if scope.get("all_clusters", True)
        else ",".join(scope.get("selected") or [])
    )
    print(
        f"CLUSTER_SCOPE dashboard={dash_scope} "
        f"rows_before={scope.get('rows_before')} "
        f"rows_after={scope.get('rows_after')} "
        f"available={','.join(scope.get('available') or [])} "
        f"metrics_scope={analysis.get('metrics_scope', 'all_clusters')}",
        flush=True,
    )
    if args.metrics_out:
        # Never publish subset gauges into the shared textfile — all three
        # families come from the full RHACS report. Dashboard JSON still uses
        # the filtered analysis above for tables/Detail.
        metrics_sev = analysis.get("metrics_severity_all_clusters") or analysis["all"][
            "severity"
        ]
        metrics_by_cluster = analysis.get("metrics_severity_by_cluster") or {}
        metrics_by_ns = analysis.get("metrics_severity_by_ns") or {}
        Path(args.metrics_out).write_text(
            posture_metrics_text(
                metrics_sev,
                by_cluster=metrics_by_cluster,
                by_ns=metrics_by_ns,
            ),
            encoding="utf-8",
        )
        by_total = sum(int(v.get("Total", 0)) for v in metrics_by_cluster.values())
        by_ns_total = sum(int(v.get("Total", 0)) for v in metrics_by_ns.values())
        print(
            "METRICS_SCOPE all_clusters "
            f"(dashboard_clusters={dash_scope}) "
            f"findings_total={int(metrics_sev.get('Total', 0))} "
            f"by_cluster_clusters={len(metrics_by_cluster)} "
            f"by_cluster_total={by_total} "
            f"by_ns_series={len(metrics_by_ns)} "
            f"by_ns_total={by_ns_total}",
            flush=True,
        )
    if args.send_report_url:
        analysis["send_report_url"] = args.send_report_url
    if args.acs_central_url:
        analysis["acs_central_url"] = args.acs_central_url.strip().rstrip("/")
    t_panels = time.perf_counter()
    dash = build_dashboard(
        analysis,
        args.title,
        args.uid,
        prometheus_datasource_uid=args.prometheus_datasource_uid,
        lite=lite,
        cve_intel_panels=cve_intel_panels,
    )
    print(
        f"TIMING Dashboard Build/panel_assembly: {time.perf_counter() - t_panels:.3f}s "
        f"lite={lite} cve_intel_panels={cve_intel_panels}",
        flush=True,
    )
    detail_rows = len(analysis.get("drilldown") or [])
    embedded_detail = 0
    if not lite:
        p90 = next((p for p in dash["panels"] if p.get("id") == DETAIL_PANEL_ID), None)
        if p90 and (p90.get("targets") or []):
            csv_text = (p90["targets"][0].get("csvContent") or "")
            embedded_detail = max(0, csv_text.count("\n") - 1)
    # Equivalent-input serialize compare (same dash object): indent vs compact.
    t_pretty = time.perf_counter()
    pretty_text = serialize_dashboard_json(dash, compact=False)
    pretty_secs = time.perf_counter() - t_pretty
    t_compact = time.perf_counter()
    compact_text = serialize_dashboard_json(dash, compact=True)
    compact_secs = time.perf_counter() - t_compact
    print(
        f"TIMING Dashboard Build/json_serialize_indent2: {pretty_secs:.3f}s "
        f"bytes={len(pretty_text.encode('utf-8'))}",
        flush=True,
    )
    print(
        f"TIMING Dashboard Build/json_serialize_compact: {compact_secs:.3f}s "
        f"bytes={len(compact_text.encode('utf-8'))}",
        flush=True,
    )
    out = Path(args.out_json)
    # Phase 4C-1: publish compact JSON (keys/values/order unchanged).
    out.write_text(compact_text, encoding="utf-8")
    updates = build_operator_updates_dashboard(subscriptions, posture_uid=args.uid)
    updates_path = out.with_name("operator-updates-dashboard.json")
    updates_path.write_text(
        serialize_dashboard_json(updates, compact=True), encoding="utf-8"
    )
    types = sorted({p["type"] for p in dash["panels"]})
    total_secs = time.perf_counter() - t_total
    print(
        f"TIMING Dashboard Build/total: {total_secs:.3f}s "
        f"lite={lite} detail_rows={detail_rows} "
        f"detail_rows_embedded={embedded_detail} json_bytes={out.stat().st_size}",
        flush=True,
    )
    print(
        f"Wrote {out} ({out.stat().st_size} bytes) panels={len(dash['panels'])} "
        f"types={types} lite={lite} report_date={analysis['report_date']} "
        f"source={analysis['source_label']}"
    )


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        # Cluster selection / config errors — keep Contoller stdout readable.
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2) from exc
