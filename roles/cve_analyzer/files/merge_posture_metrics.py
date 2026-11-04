#!/usr/bin/env python3
"""Keep cve_posture_findings in the scraped Prometheus textfile."""

from __future__ import annotations

import sys
from pathlib import Path

BEGIN = "# BEGIN cve_posture"
END = "# END cve_posture"
METRIC = "cve_posture_findings"
METRIC_BY_CLUSTER = "cve_posture_findings_by_cluster"
METRIC_BY_NS = "cve_posture_findings_by_ns"


def _is_posture_family_line(line: str) -> bool:
    """True for exact posture gauge families / HELP / TYPE only."""
    return (
        line.startswith(f"{METRIC}{{")
        or line.startswith(f"{METRIC_BY_CLUSTER}{{")
        or line.startswith(f"{METRIC_BY_NS}{{")
        or line.startswith(f"# HELP {METRIC} ")
        or line == f"# HELP {METRIC}"
        or line.startswith(f"# TYPE {METRIC} ")
        or line == f"# TYPE {METRIC}"
        or line.startswith(f"# HELP {METRIC_BY_CLUSTER} ")
        or line == f"# HELP {METRIC_BY_CLUSTER}"
        or line.startswith(f"# TYPE {METRIC_BY_CLUSTER} ")
        or line == f"# TYPE {METRIC_BY_CLUSTER}"
        or line.startswith(f"# HELP {METRIC_BY_NS} ")
        or line == f"# HELP {METRIC_BY_NS}"
        or line.startswith(f"# TYPE {METRIC_BY_NS} ")
        or line == f"# TYPE {METRIC_BY_NS}"
    )


def merge(existing: str, block: str) -> str:
    lines: list[str] = []
    skipping = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped == BEGIN:
            skipping = True
            continue
        if stripped == END:
            skipping = False
            continue
        if skipping:
            continue
        # Exact family prefixes only — do not drop unrelated gauges.
        if _is_posture_family_line(line):
            continue
        lines.append(line)
    body = "\n".join(lines).rstrip()
    return f"{body}\n\n{block.strip()}\n" if body else block


def main() -> None:
    existing_path, block_path, out_path = sys.argv[1:]
    existing = Path(existing_path).read_text(encoding="utf-8") if Path(existing_path).is_file() else ""
    block = Path(block_path).read_text(encoding="utf-8")
    Path(out_path).write_text(merge(existing, block), encoding="utf-8")


if __name__ == "__main__":
    main()
