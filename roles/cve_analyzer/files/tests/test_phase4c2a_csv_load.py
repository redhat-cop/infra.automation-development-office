"""Phase 4C-2A: one-shot header binding must match legacy per-call _pick output."""
from __future__ import annotations

import csv
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

FILES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FILES))

import build_rhacs_vuln_dashboard as builder  # noqa: E402
import rhacs_report_analytics as analytics  # noqa: E402


def _legacy_pick(row: dict, *names: str) -> str:
    """Pre-4C-2A _pick: rebuild normalized map on every call."""
    norm = {analytics._norm_col(k): v for k, v in row.items()}
    for name in names:
        key = analytics._norm_col(name)
        if key in norm and norm[key] not in (None, ""):
            return str(norm[key])
    return ""


def _legacy_load_scrubbed_rows(csv_path: Path) -> list[dict]:
    """Reference loader using legacy _pick semantics (DictReader unchanged)."""
    rows: list[dict] = []
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:  # pragma: no cover
        csv.field_size_limit(2**31 - 1)

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            if "RawVulnerabilityJSON" in raw:
                raw["RawVulnerabilityJSON"] = ""
            if "RawComponentJSON" in raw:
                raw["RawComponentJSON"] = ""
            cve = _legacy_pick(raw, "CVE", "CVE ID").strip().upper()
            if not cve:
                continue
            image = _legacy_pick(raw, "Image", "Image Name")
            namespace = _legacy_pick(raw, "Namespace")
            discovered = analytics.parse_date(
                _legacy_pick(
                    raw,
                    "FirstSystemOccurrence",
                    "First Image Occurrence",
                    "Discovered At",
                    "Discovered",
                )
            )
            age_raw = _legacy_pick(raw, "AgeDays")
            age = int(float(age_raw)) if age_raw not in ("", None) else None
            rows.append(
                {
                    "cve": cve,
                    "severity": analytics.normalize_severity(
                        _legacy_pick(raw, "Severity")
                    ),
                    "image": image,
                    "repository": analytics.extract_repository(image),
                    "digest": analytics.extract_digest(image)
                    or _legacy_pick(raw, "ImageDigest"),
                    "cluster": _legacy_pick(raw, "Cluster", "ClusterName")
                    or "Unknown",
                    "namespace": namespace,
                    "deployment": _legacy_pick(
                        raw, "Deployment", "DeploymentName"
                    ),
                    "component": _legacy_pick(
                        raw, "Component", "RHACSComponentGroup"
                    )
                    or namespace
                    or "Unknown",
                    "discovered": discovered,
                    "age_days": age,
                    "redhat_source": analytics._truthy(
                        _legacy_pick(raw, "RedHatSource")
                    ),
                    "fixable": analytics._truthy(_legacy_pick(raw, "Fixable")),
                    "sources": _legacy_pick(raw, "Sources"),
                }
            )
    return rows


# Contoller-shaped headers (subset sufficient for loader + Raw* empties).
CONTROLLERISH_FIELDS = [
    "LivePods",
    "Cluster",
    "Namespace",
    "Deployment",
    "RHACSComponentGroup",
    "Image",
    "ImageDigest",
    "Component",
    "ComponentVersion",
    "CVE",
    "Severity",
    "Sources",
    "RedHatSource",
    "Fixable",
    "FirstSystemOccurrence",
    "FirstImageOccurrence",
    "AgeDays",
    "RawVulnerabilityJSON",
    "RawComponentJSON",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestHeaderColumnMap(unittest.TestCase):
    def test_last_duplicate_normalized_name_wins(self):
        colmap = analytics._header_column_map(["CVE", "cve", "CVE ID"])
        # "CVE" and "cve" both normalize to "cve"; last wins → column "cve"
        self.assertEqual(colmap[analytics._norm_col("CVE")], "cve")
        self.assertEqual(colmap[analytics._norm_col("CVE ID")], "CVE ID")

    def test_pick_mapped_skips_empty_then_alias(self):
        row = {"CVE": "", "CVE ID": "CVE-2024-1"}
        colmap = analytics._header_column_map(["CVE", "CVE ID"])
        self.assertEqual(
            analytics._pick(row, "CVE", "CVE ID", colmap=colmap), "CVE-2024-1"
        )

    def test_pick_mapped_missing_column(self):
        row = {"Namespace": "ns1"}
        colmap = analytics._header_column_map(["Namespace"])
        self.assertEqual(analytics._pick(row, "CVE", "CVE ID", colmap=colmap), "")

    def test_pick_mapped_matches_legacy_on_aliases(self):
        row = {
            "ClusterName": "prod",
            "Image Name": "quay.io/app@sha256:abc",
            "Discovered At": "2026-01-15T00:00:00Z",
        }
        colmap = analytics._header_column_map(list(row.keys()))
        for names in (
            ("Cluster", "ClusterName"),
            ("Image", "Image Name"),
            ("FirstSystemOccurrence", "First Image Occurrence", "Discovered At", "Discovered"),
        ):
            self.assertEqual(
                analytics._pick(row, *names, colmap=colmap),
                _legacy_pick(row, *names),
                msg=names,
            )


class TestLoadScrubbedEquivalence(unittest.TestCase):
    def test_identical_to_legacy_controllerish_fixture(self):
        rows_in = [
            {
                "LivePods": "1",
                "Cluster": "prod",
                "Namespace": "aap",
                "Deployment": "web",
                "RHACSComponentGroup": "",
                "Image": "quay.io/app/demo:1@sha256:abcd",
                "ImageDigest": "",
                "Component": "openssl",
                "ComponentVersion": "1.0",
                "CVE": "CVE-2024-111",
                "Severity": "Critical",
                "Sources": "Red Hat",
                "RedHatSource": "true",
                "Fixable": "true",
                "FirstSystemOccurrence": "2026-01-01T12:00:00Z",
                "FirstImageOccurrence": "",
                "AgeDays": "40",
                "RawVulnerabilityJSON": "",
                "RawComponentJSON": "",
            },
            {
                "Cluster": "",
                "ClusterName": "edge",  # alias path — not in CONTROLLERISH; add below
                "Namespace": "ns2",
                "Deployment": "",
                "DeploymentName": "dep2",
                "Image": "",
                "Image Name": "registry.redhat.io/ubi9/ubi:latest",
                "Component": "",
                "RHACSComponentGroup": "ACM / MCE",
                "CVE": "",
                "CVE ID": "cve-2024-222",
                "Severity": "HIGH",
                "RedHatSource": "yes",
                "Fixable": "0",
                "Discovered At": "2026-02-01T00:00:00Z",
                "AgeDays": "",
                "RawVulnerabilityJSON": "{}",
                "RawComponentJSON": "{}",
            },
            {
                # skipped: no CVE
                "Cluster": "prod",
                "Namespace": "empty",
                "CVE": "",
                "Severity": "Low",
            },
        ]
        fields = list(
            dict.fromkeys(
                CONTROLLERISH_FIELDS
                + ["ClusterName", "Image Name", "CVE ID", "DeploymentName", "Discovered At"]
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scrubbed.csv"
            _write_csv(path, fields, rows_in)
            optimized = analytics.load_scrubbed_rows(path)
            legacy = _legacy_load_scrubbed_rows(path)
        self.assertEqual(len(optimized), len(legacy))
        self.assertEqual(optimized, legacy)
        self.assertEqual(len(optimized), 2)
        self.assertEqual(optimized[0]["cve"], "CVE-2024-111")
        self.assertEqual(optimized[1]["cve"], "CVE-2024-222")
        self.assertEqual(optimized[1]["cluster"], "edge")
        self.assertEqual(optimized[1]["component"], "ACM / MCE")

    def test_duplicate_normalized_headers_last_wins(self):
        # Two headers that normalize to "cve"; last column value used (may be empty).
        fields = ["CVE", "cve", "Severity", "Image", "Namespace", "Cluster"]
        rows_in = [
            {
                "CVE": "CVE-FIRST",
                "cve": "CVE-LAST",
                "Severity": "Low",
                "Image": "img:1",
                "Namespace": "ns",
                "Cluster": "c",
            },
            {
                "CVE": "CVE-ONLY-FIRST",
                "cve": "",
                "Severity": "Low",
                "Image": "img:2",
                "Namespace": "ns",
                "Cluster": "c",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dup.csv"
            _write_csv(path, fields, rows_in)
            optimized = analytics.load_scrubbed_rows(path)
            legacy = _legacy_load_scrubbed_rows(path)
        self.assertEqual(optimized, legacy)
        self.assertEqual(optimized[0]["cve"], "CVE-LAST")
        # Last column empty → legacy skips empty mapped value; only one norm key "cve"
        # so empty last wins and CVE is missing → row skipped in both.
        self.assertEqual(len(optimized), 1)


class TestLoadScrubbedDownloadsEquivalence(unittest.TestCase):
    """Optional: large Downloads scrubbed CSV if present."""

    def test_downloads_scrubbed_matches_legacy_when_present(self):
        cands = sorted(
            Path.home().joinpath("Downloads").glob("*SCRUBBED*.csv"),
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not cands:
            self.skipTest("No Downloads *SCRUBBED*.csv")
        path = cands[0]
        optimized = analytics.load_scrubbed_rows(path)
        legacy = _legacy_load_scrubbed_rows(path)
        self.assertEqual(len(optimized), len(legacy))
        self.assertEqual(optimized, legacy)


class TestDownstreamUnchanged(unittest.TestCase):
    def test_build_analysis_and_metrics_stable_on_fixture(self):
        fields = CONTROLLERISH_FIELDS
        rows_in = [
            {
                "Cluster": "prod",
                "Namespace": "aap",
                "Deployment": "web",
                "Image": "quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:abc",
                "ImageDigest": "sha256:abc",
                "Component": "payload",
                "CVE": "CVE-2024-300",
                "Severity": "Critical",
                "Sources": "",
                "RedHatSource": "true",
                "Fixable": "true",
                "FirstSystemOccurrence": "2026-01-10T00:00:00Z",
                "AgeDays": "50",
                "RawVulnerabilityJSON": "",
                "RawComponentJSON": "",
            }
        ]
        cfg = {
            "families": [
                {
                    "name": "OCP payload",
                    "ownership": "sre_managed",
                    "remediation_type": "ocp_upgrade",
                    "action": "Upgrade OpenShift",
                    "match": {
                        "repository_equals": [
                            "quay.io/openshift-release-dev/ocp-v4.0-art-dev"
                        ]
                    },
                }
            ],
            "ocp_payload_repository": "quay.io/openshift-release-dev/ocp-v4.0-art-dev",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scrubbed.csv"
            _write_csv(path, fields, rows_in)
            loaded = analytics.load_scrubbed_rows(path)
        report_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        analysis = analytics.build_analysis(
            loaded, report_date, cfg, "fixture", installed=None
        )
        self.assertEqual(analysis["all"]["severity"]["Critical"], 1)
        drill = analysis["drilldown"]
        self.assertEqual(len(drill), 1)
        self.assertEqual(drill[0]["CVE"], "CVE-2024-300")
        prom = builder.posture_metrics_text(analysis["all"]["severity"])
        self.assertIn("cve_posture_findings", prom)


def _benchmark_pair(path: Path, rounds: int = 3) -> dict:
    # Warm once
    analytics.load_scrubbed_rows(path)
    _legacy_load_scrubbed_rows(path)

    def _timed(fn):
        times = []
        rows = None
        for _round in range(rounds):
            t0 = time.perf_counter()
            rows = fn(path)
            times.append(time.perf_counter() - t0)
        return min(times), len(rows or [])

    base_t, n = _timed(_legacy_load_scrubbed_rows)
    opt_t, n2 = _timed(analytics.load_scrubbed_rows)
    assert n == n2
    with path.open(newline="", encoding="utf-8") as fh:
        cols = len(csv.DictReader(fh).fieldnames or [])
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "rows": n,
        "cols": cols,
        "baseline_s": base_t,
        "optimized_s": opt_t,
        "improvement_pct": (1.0 - opt_t / base_t) * 100.0 if base_t else 0.0,
    }


class TestPerformanceLocal(unittest.TestCase):
    def test_optimized_not_slower_than_legacy_on_fixture(self):
        # Synthetic wider Contoller-ish file (~25k rows) for stable CI/local bench.
        fields = CONTROLLERISH_FIELDS
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bench.csv"
            with path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                for i in range(25000):
                    w.writerow(
                        {
                            "Cluster": "prod",
                            "Namespace": f"ns{i % 50}",
                            "Deployment": "d",
                            "Image": f"quay.io/app/x:{i}@sha256:{i:064x}"[:80],
                            "Component": "comp",
                            "CVE": f"CVE-2024-{i % 10000}",
                            "Severity": "Important",
                            "RedHatSource": "true",
                            "Fixable": "true",
                            "FirstSystemOccurrence": "2026-01-01T00:00:00Z",
                            "AgeDays": str(i % 200),
                            "RawVulnerabilityJSON": "",
                            "RawComponentJSON": "",
                        }
                    )
            stats = _benchmark_pair(path, rounds=2)
        self.assertEqual(stats["rows"], 25000)
        # Allow tiny noise; require clear win on this CPU-bound fixture.
        self.assertLess(stats["optimized_s"], stats["baseline_s"] * 0.85)
        # Print for operator report (unittest -v shows on failure; always emit).
        print(
            f"\n4C-2A bench fixture: rows={stats['rows']} cols={stats['cols']} "
            f"size={stats['bytes']} baseline={stats['baseline_s']:.3f}s "
            f"optimized={stats['optimized_s']:.3f}s "
            f"improvement={stats['improvement_pct']:.1f}%",
            flush=True,
        )


if __name__ == "__main__":
    # Optional Downloads bench for the human report.
    cands = sorted(
        Path.home().joinpath("Downloads").glob("*SCRUBBED*.csv"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if cands:
        print("Downloads scrubbed bench:", _benchmark_pair(cands[0], rounds=2))
    unittest.main(verbosity=2)
