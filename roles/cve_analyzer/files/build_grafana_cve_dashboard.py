#!/usr/bin/env python3
"""Build Grafana dashboard JSON from cve-analyzer data.json (dict rows or legacy arrays)."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Field names match build_report_v2.py data.json dict keys (and R[] index for legacy arrays)
FIELDS = {
    "priority": 0,
    "action": 1,
    "cve": 2,
    "product": 7,
    "image_short": 8,
    "remediation": 19,  # remediation_path in dict rows
    "fix_status": 32,
    "kev_added": 39,  # kev_date_added in dict rows
    "kev_due": 40,  # kev_due_date in dict rows
}
DICT_ALIASES = {
    "remediation": "remediation_path",
    "kev_added": "kev_date_added",
    "kev_due": "kev_due_date",
}


def row_val(row, field: str):
    if isinstance(row, dict):
        key = DICT_ALIASES.get(field, field)
        return row.get(key, "") or ""
    return row[FIELDS[field]] if FIELDS[field] < len(row) else ""


def summarize(rows: list) -> dict:
    pc: Counter = Counter()
    ac: Counter = Counter()
    rem_sum: dict = defaultdict(lambda: {"p": 0, "m": 0, "p1": 0, "c": set()})
    prod_sum: dict = defaultdict(lambda: {"t": 0, "p": 0, "p1": 0, "c": set(), "i": set()})
    kev_records = []
    for r in rows:
        priority = row_val(r, "priority")
        action = row_val(r, "action")
        cve = row_val(r, "cve")
        pc[priority] += 1
        ac[action] += 1
        rem = row_val(r, "remediation") or "Unknown"
        rem_sum[rem]["p" if action == "PATCH" else "m"] += 1
        if str(priority).startswith("P1"):
            rem_sum[rem]["p1"] += 1
        rem_sum[rem]["c"].add(cve)
        pl = row_val(r, "product") or "Unknown"
        prod_sum[pl]["t"] += 1
        if action == "PATCH":
            prod_sum[pl]["p"] += 1
        if str(priority).startswith("P1"):
            prod_sum[pl]["p1"] += 1
        prod_sum[pl]["c"].add(cve)
        prod_sum[pl]["i"].add(row_val(r, "image_short"))
        if row_val(r, "kev_added"):
            kev_records.append(r)
    return {
        "records": len(rows),
        "cves": len({row_val(r, "cve") for r in rows}),
        "patch": ac.get("PATCH", 0),
        "monitor": ac.get("MONITOR", 0),
        "p1": sum(v for k, v in pc.items() if str(k).startswith("P1")),
        "p2": sum(v for k, v in pc.items() if str(k).startswith("P2")),
        "fix_fixed": sum(1 for r in rows if row_val(r, "fix_status") == "FIXED_IN_LATEST"),
        "fix_still": sum(1 for r in rows if row_val(r, "fix_status") == "STILL_VULNERABLE"),
        "kev": len(kev_records),
        "rem_sum": rem_sum,
        "prod_sum": prod_sum,
        "kev_records": kev_records,
    }


COLOR_MAP = {
    "blue": "#0066CC",
    "red": "#C9190B",
    "orange": "#EC7A08",
    "green": "#3E8635",
    "yellow": "#F0AB00",
}


def html_stat_row(stats: list[tuple[str, int | str, str]]) -> str:
    """Render a row of stat tiles (label, value, color key)."""
    tiles = []
    for label, val, color in stats:
        bg = COLOR_MAP.get(color, "#0066CC")
        fg = "#151515" if color == "yellow" else "#fff"
        tiles.append(
            f'<div style="flex:1;min-width:0;background:{bg};color:{fg};border-radius:6px;'
            f'padding:14px 8px;text-align:center">'
            f'<div style="font-size:28px;font-weight:700;line-height:1">{val:,}</div>'
            f'<div style="font-size:11px;margin-top:8px;font-weight:600;opacity:.95;'
            f'text-transform:uppercase;letter-spacing:.04em">{label}</div></div>'
        )
    return (
        '<div style="display:flex;gap:10px;font-family:RedHatText,Helvetica,Arial,sans-serif">'
        + "".join(tiles)
        + "</div>"
    )


def html_table(title: str, columns: list[str], rows: list[list]) -> str:
    head = "".join(
        f'<th style="padding:6px;border-bottom:1px solid #2c3034;text-align:left">{c}</th>'
        for c in columns
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            f'<td style="padding:8px 6px;border-bottom:1px solid #2c3034">{c}</td>'
            for c in row
        )
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        f'<div style="font-family:RedHatText,Helvetica,Arial,sans-serif;color:#f0f0f0">'
        f'<div style="font-size:15px;font-weight:700;margin-bottom:10px">{title}</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:12px">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )


def text_panel(pid: int, title: str, html: str, x: int, y: int, w: int, h: int) -> dict:
    return {
        "id": pid,
        "type": "text",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {"mode": "html", "content": html},
    }


def build_dashboard(summary: dict, title: str, uid: str) -> dict:
    s = summary
    panels = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    panels.append(
        text_panel(
            1,
            "",
            f'<div style="font-family:RedHatText,Helvetica,Arial,sans-serif;color:#f0f0f0">'
            f'<div style="font-size:22px;font-weight:700">{title}</div>'
            f'<div style="font-size:13px;opacity:.75;margin-top:4px">cve-analyzer pipeline · updated {now}</div></div>',
            0,
            0,
            24,
            3,
        )
    )

    panels.append(
        text_panel(
            10,
            "",
            html_stat_row(
                [
                    ("Finding occurrences", s["records"], "blue"),
                    ("Unique CVEs", s["cves"], "blue"),
                    ("Fixable (PATCH action)", s["patch"], "red"),
                    ("Monitor action", s["monitor"], "blue"),
                ]
            )
            + '<div style="font-family:RedHatText,Helvetica,Arial,sans-serif;color:#b8bbbe;'
            'font-size:11px;margin-top:8px">'
            "Finding occurrences = rows in data.json (CVE+image aggregates from the export). "
            "Unique CVEs = distinct CVE IDs. "
            "Fixable (PATCH action) = triage action PATCH (not the same as unique CVEs)."
            "</div>",
            0,
            3,
            24,
            6,
        )
    )
    panels.append(
        text_panel(
            11,
            "",
            html_stat_row(
                [
                    ("P1 Critical", s["p1"], "red"),
                    ("P2 High", s["p2"], "orange"),
                    ("Fixed in Latest", s["fix_fixed"], "green"),
                    ("Not Fixed", s["fix_still"], "red"),
                ]
            ),
            0,
            9,
            24,
            5,
        )
    )
    panels.append(
        text_panel(
            12,
            "",
            html_stat_row([("CISA KEV", s["kev"], "yellow")]),
            0,
            14,
            6,
            4,
        )
    )

    rem_rows = sorted(
        [[k[:80], v["p"], v["m"], v["p1"], len(v["c"])] for k, v in s["rem_sum"].items()],
        key=lambda r: (-int(r[1]), -int(r[3])),
    )[:15]
    panels.append(
        text_panel(
            20,
            "Remediation Action Summary",
            html_table(
                "Remediation Action Summary",
                ["Remediation Action", "Fixable findings", "Monitor findings", "Critical findings", "Unique CVEs"],
                rem_rows,
            ),
            0,
            18,
            24,
            10,
        )
    )

    prod_rows = sorted(
        [[k, len(v["i"]), v["t"], v["p"], v["p1"], len(v["c"])] for k, v in s["prod_sum"].items()],
        key=lambda r: (-int(r[2]),),
    )[:15]
    panels.append(
        text_panel(
            21,
            "Product Line Summary",
            html_table(
                "Product Line Summary",
                ["Product", "Images", "Finding occurrences", "Fixable findings", "Critical findings", "Unique CVEs"],
                prod_rows,
            ),
            0,
            28,
            24,
            10,
        )
    )

    return {
        "uid": uid,
        "title": title,
        "tags": ["cve-analyzer", "rhacs", "prod"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "",
        "time": {"from": "now-6h", "to": "now"},
        "panels": panels,
        "description": f"Generated from cve-analyzer pipeline. Updated {now}.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_json")
    ap.add_argument("output_json")
    ap.add_argument("--title", default="OpenShift CVE Triage Report - Prod")
    ap.add_argument("--uid", default="ado-rhacs-cve-triage")
    args = ap.parse_args()
    rows = json.loads(Path(args.data_json).read_text(encoding="utf-8"))
    summary = summarize(rows)
    dash = build_dashboard(summary, args.title, args.uid)
    Path(args.output_json).write_text(json.dumps(dash, indent=2), encoding="utf-8")
    print(f"Wrote Grafana dashboard to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
