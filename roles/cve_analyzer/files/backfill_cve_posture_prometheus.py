"""Write cve_posture_findings samples for old RHACS scrubbed CSVs.

The live metrics pod is scraped as a gauge, so each new CVE Analyzer run
is stored at scrape time. This script is only for reports that already
exist as files. It counts the same five series the Findings over time
panel draws and stamps each one with the report day from the file name.
A clock in the name is used when it is present. A day-only name is
noon America/New_York:

    RHACS_Vulnerability_Report_SCRUBBED_08_October_2026_8-06_PM.csv
    RHACS_Vulnerability_Report_Prod Vulnerability report (COPY)_31_August_2026.csv

--date overrides one file. A name with no day is an error.

    python3 backfill_cve_posture_prometheus.py reports/*.csv -o /tmp/cve_posture_backfill.prom
    python3 backfill_cve_posture_prometheus.py reports/*.csv --blocks /tmp/cve-blocks

--blocks builds Prometheus TSDB blocks for another environment. Copy each
directory under that path into the target Prometheus data directory, then
restart Prometheus. Retention there must cover the oldest report. Do not
append these lines to the live scrape file: OpenShift forces
honor_timestamps off, so a scrape stores them as "now" and replaces the
current gauge.

The Findings panel has to use a one-day lookback or a wide time step
skips a single noon sample:

    sum by (severity) (last_over_time(cve_posture_findings{job="cve-analyzer-ns-metrics"}[1d]))

Set the dashboard range long enough to include the oldest day.
High in the CSV is stored as severity="Important". Total is every row.
Moderate and Low are 0 when the file has only Critical and Important.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SEVERITIES = ("Total", "Critical", "Important", "Moderate", "Low")
METRIC = "cve_posture_findings"


def _eastern_tz():
    """America/New_York when tzdata exists; else fixed UTC-4 (typical EDT)."""
    try:
        return ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        print(
            "Warning: no tzdata for America/New_York "
            "(pip install tzdata, or dnf install tzdata). "
            "Using fixed UTC-4 for day-only report stamps.",
            file=sys.stderr,
        )
        return timezone(timedelta(hours=-4))


EASTERN = _eastern_tz()
NAME_RE = re.compile(
    r"(?P<day>\d{1,2})_(?P<month>January|February|March|April|May|June|July|"
    r"August|September|October|November|December)_(?P<year>\d{4})"
    r"(?:[_-](?P<hour>\d{1,2})-(?P<minute>\d{2})_(?P<ampm>AM|PM))?",
    re.IGNORECASE,
)


def normalize_severity(value: str) -> str:
    text = str(value or "").strip().upper()
    if "CRITICAL" in text:
        return "Critical"
    if "IMPORTANT" in text or "HIGH" in text:
        return "Important"
    if "MODERATE" in text or "MEDIUM" in text:
        return "Moderate"
    if "LOW" in text:
        return "Low"
    return ""


def report_time(path: Path, override: str) -> datetime:
    if override:
        parsed = datetime.fromisoformat(override)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=EASTERN)
        return parsed
    match = None
    for found in NAME_RE.finditer(path.name):
        match = found
    if not match:
        raise SystemExit(
            f"{path.name} has no day in the name. "
            "Expected something like 31_August_2026, with an optional 8-06_PM."
        )
    clock = f"{int(match.group('day')):02d} {match.group('month')} {match.group('year')}"
    pattern = "%d %B %Y"
    if match.group("hour"):
        clock += f" {int(match.group('hour')):02d}:{match.group('minute')} {match.group('ampm').upper()}"
        pattern += " %I:%M %p"
    else:
        clock += " 12:00 PM"
        pattern += " %I:%M %p"
    return datetime.strptime(clock, pattern).replace(tzinfo=EASTERN)


def count_findings(path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    total = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "Severity" not in reader.fieldnames:
            raise SystemExit(f"{path} has no Severity column")
        for row in reader:
            total += 1
            name = normalize_severity(row.get("Severity") or "")
            if name:
                counts[name] += 1
    counts["Total"] = total
    return {name: int(counts.get(name, 0)) for name in SEVERITIES}


def series_labels(job: str) -> str:
    return f'job="{job}",severity='


def openmetrics(samples: list[tuple[datetime, dict[str, int]]], job: str, unit: str) -> str:
    lines = [
        f"# HELP {METRIC} RHACS posture finding counts from a CVE Analyzer report",
        f"# TYPE {METRIC} gauge",
    ]
    labels = series_labels(job)
    for when, counts in sorted(samples, key=lambda item: item[0]):
        stamp = int(when.timestamp() * (1000 if unit == "ms" else 1))
        for name in SEVERITIES:
            lines.append(f'{METRIC}{{{labels}"{name}"}} {counts[name]} {stamp}')
    lines.append("# EOF")
    return "\n".join(lines) + "\n"


def write_blocks(samples: list[tuple[datetime, dict[str, int]]], job: str, blocks: Path, promtool: str) -> None:
    """promtool 3.x treats an OpenMetrics timestamp as seconds and stores milliseconds."""
    tool = shutil.which(promtool)
    if tool is None:
        raise SystemExit(f"promtool not found ({promtool}). Pass --promtool with its path.")
    if blocks.exists() and any(blocks.iterdir()):
        raise SystemExit(f"{blocks} is not empty")
    blocks.mkdir(parents=True, exist_ok=True)
    seconds = blocks / "samples.prom"
    seconds.write_text(openmetrics(samples, job, "s"), encoding="utf-8")
    subprocess.run(
        [tool, "tsdb", "create-blocks-from", "openmetrics", str(seconds), str(blocks)],
        check=True,
    )
    seconds.unlink()
    oldest = min(when.timestamp() for when, _counts in samples) * 1000
    newest = max(when.timestamp() for when, _counts in samples) * 1000
    found = 0
    for meta_path in blocks.glob("*/meta.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not (oldest - 1000) <= meta["minTime"] <= (newest + 1000):
            raise SystemExit(
                f"{meta_path.parent.name} minTime {meta['minTime']} is outside "
                f"{int(oldest)}..{int(newest)}. Refusing to leave bad blocks in {blocks}."
            )
        found += 1
    expected = len({when for when, _counts in samples})
    if found != expected:
        raise SystemExit(f"expected {expected} blocks, found {found}")
    print(
        f"Wrote {found} blocks in {blocks}. "
        "Copy each ULID directory into the target Prometheus data directory, then restart it. "
        f"Retention must cover {datetime.fromtimestamp(oldest / 1000, EASTERN).date()} "
        "through today. Leave the live scrape gauges unchanged.",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="+", type=Path, help="Scrubbed RHACS CSV reports")
    parser.add_argument("-o", "--output", type=Path, help="OpenMetrics file (default: stdout)")
    parser.add_argument("--blocks", type=Path, help="Directory for Prometheus TSDB blocks")
    parser.add_argument("--promtool", default="promtool", help="promtool binary used by --blocks")
    parser.add_argument(
        "--job",
        default="cve-analyzer-ns-metrics",
        help="job label so the Findings panel query matches these samples",
    )
    parser.add_argument(
        "--date",
        default="",
        help="ISO timestamp used for every file, for example 2026-10-08T20:06:00-04:00",
    )
    args = parser.parse_args()
    if args.date and len(args.csv) != 1:
        raise SystemExit("--date applies to one CSV; omit it to use each file name")

    samples: list[tuple[datetime, dict[str, int]]] = []
    for path in args.csv:
        when = report_time(path, args.date)
        counts = count_findings(path)
        samples.append((when, counts))
        print(
            f"{path.name} {when.isoformat()} "
            + " ".join(f"{name}={counts[name]}" for name in SEVERITIES),
            file=sys.stderr,
        )
    body = openmetrics(samples, args.job, "ms")
    if args.blocks:
        write_blocks(samples, args.job, args.blocks, args.promtool)
    if args.output:
        args.output.write_text(body, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    elif not args.blocks:
        sys.stdout.write(body)


if __name__ == "__main__":
    main()
