#!/usr/bin/env python3
"""RHACS report analytics for Grafana dashboards.

Calculation semantics match the lab RHACS analyzer contract:

1. Finding occurrence = one source CSV row (never drop rows for counts).
2. Unique CVE = distinct CVE ID after filter.
3. Unique CVE by component = dedupe inside each namespace/component.
4. Component TOTAL = sum of per-component unique counts (not global dedupe).
5. OCP payload = repository exactly quay.io/openshift-release-dev/ocp-v4.0-art-dev
6. OCP vulnerable images = distinct sha256 digests in that repo.
7. OCP unique CVEs = global dedupe across all ocp-v4.0-art-dev images.
8. Severity: Critical; Important or High -> Important.
9. Age = report_date - FirstSystemOccurrence (fallback FirstImageOccurrence).
10. Age buckets non-cumulative: <30, 30-60, 60-90, 90-180, 180+.
11. Unique CVE age uses earliest discovered date so one bucket only.
12. Image-family grouping is remediation grouping from image_families.yaml.
13. Ownership buckets (sre_managed / redhat_component / non_redhat) come from
    image_families.yaml only — never from RedHatSource.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import combinations
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

AGE_BUCKETS = [
    "Under 14 days",
    "14–30 days",
    "30–60 days",
    "60–90 days",
    "90–180 days",
    "Over 180 days",
]
# Dashboard Finding age dropdown. Avoid "+" so Grafana regex filters stay literal.
FINDING_AGE_BUCKETS = [
    "0-15 days",
    "15-30 days",
    "30-60 days",
    "Over 60 days",
]
# Grafana allValue for Namespace and Finding age. Real rows use this on NsAll/AgeAll
# so "All" still matches. Stat cards also emit rollup rows keyed by this token.
FILTER_ALL = "__ALL__"

OCP_DEFAULT_REPO = "quay.io/openshift-release-dev/ocp-v4.0-art-dev"


def _norm_col(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value or "").strip().lower()
    return s in {"1", "true", "yes", "y", "t"}


def normalize_severity(value: Any) -> str:
    s = str(value or "").strip().upper()
    if "CRITICAL" in s:
        return "Critical"
    if "IMPORTANT" in s or "HIGH" in s:
        return "Important"
    if "MODERATE" in s or "MEDIUM" in s:
        return "Moderate"
    if "LOW" in s:
        return "Low"
    return (str(value or "Unknown").strip().title() or "Unknown")


def extract_repository(image: str) -> str:
    image = str(image or "").strip()
    if "@" in image:
        image = image.split("@", 1)[0]
    if image.count(":") >= 2 or (image.startswith("localhost") and ":" in image):
        # registry:port/repo:tag — strip tag after last /
        host_path, _, maybe_tag = image.rpartition(":")
        if "/" in maybe_tag:
            return image
        if "/" in host_path:
            return host_path
    elif ":" in image and "@" not in image:
        # name:tag without digest
        left, _, right = image.rpartition(":")
        if "/" in left and right and "/" not in right:
            return left
    return image


def image_popup_label(repository: str, tag: str = "") -> str:
    """Installed image, name first: ``grafana docker.io/grafana/grafana:13.1.3``."""
    text = str(repository or "").strip()
    if not text:
        return ""
    name = text.rstrip("/").rsplit("/", 1)[-1] if "/" in text else text
    ref = text
    if tag and not ref.endswith(f":{tag}"):
        ref = f"{text}:{tag}"
    if name and ref != name:
        return f"{name} {ref}"
    return ref


def update_image_action(repository: str, tag: str) -> str:
    """Newer image in the same shape as the installed component."""
    return f"update {image_popup_label(repository, tag)}"


def pick_tag(tags: set[str] | list[str]) -> str:
    """Prefer the installed release tag over a digest, latest, or a build id."""
    clean: list[str] = []
    latest = ""
    for tag in tags:
        text = str(tag or "").strip()
        if not text or "@" in text or "/" in text or text.startswith("sha256"):
            continue
        if text.lower() == "latest":
            latest = text
            continue
        clean.append(text)
    if not clean:
        return latest
    semver = [tag for tag in clean if re.match(r"^v?\d+(\.\d+){0,3}([-+.].*)?$", tag)]
    pool = semver or clean
    return sorted(pool, key=lambda tag: (tag.count("-"), len(tag), tag))[0]


def _group_tag(group: list[dict], repository: str, installed: dict[str, set[str]] | None) -> str:
    tags = {extract_tag(str(row.get("image") or "")) for row in group}
    tags.discard("")
    extra = (installed or {}).get(repository) or set()
    if isinstance(extra, str):
        extra = {extra}
    tags.update(extra)
    return pick_tag(tags)


def extract_digest(image: str) -> str:
    m = re.search(r"@sha256:([a-fA-F0-9]+)", str(image or ""))
    return f"sha256:{m.group(1).lower()}" if m else ""


# UI / Central CSV exports often use English month dates ("October 09, 2026")
# without AgeDays. ISO and numeric forms come from the Contoller parser path.
_PARSE_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%B %d, %Y",  # October 09, 2026
    "%B %d %Y",  # October 09 2026
    "%b %d, %Y",  # Oct 09, 2026
    "%b %d %Y",  # Oct 09 2026
    "%B %d, %Y %H:%M:%S",
    "%b %d, %Y %H:%M:%S",
)


def parse_date(value: Any) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = None
        # Drop trailing timezone labels UI exports sometimes append.
        base = re.sub(r"\s+(UTC|GMT|[A-Z]{2,5})$", "", text).strip()
        for fmt in _PARSE_DATE_FORMATS:
            try:
                dt = datetime.strptime(base, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_days(discovered: datetime | None, report_date: datetime) -> int | None:
    if discovered is None:
        return None
    return max(0, (report_date - discovered).days)


def age_bucket(days: int | None) -> str:
    if days is None:
        return "Unknown"
    if days < 14:
        return "Under 14 days"
    if days < 30:
        return "14–30 days"
    if days < 60:
        return "30–60 days"
    if days < 90:
        return "60–90 days"
    if days < 180:
        return "90–180 days"
    return "Over 180 days"


def finding_age_bucket(days: int | None) -> str:
    """Coarse slice that matches the Finding age dropdown."""
    if days is None:
        return "Unknown"
    if days < 15:
        return "0-15 days"
    if days < 30:
        return "15-30 days"
    if days < 60:
        return "30-60 days"
    return "Over 60 days"


def load_image_families(path: Path | None) -> dict:
    default = {"ocp_payload_repository": OCP_DEFAULT_REPO, "families": []}
    if not path or not path.exists():
        # try sibling .json
        if path and path.with_suffix(".json").exists():
            path = path.with_suffix(".json")
        else:
            return default
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    elif yaml is not None:
        data = yaml.safe_load(text) or {}
    else:
        json_sib = path.with_suffix(".json")
        if json_sib.exists():
            data = json.loads(json_sib.read_text(encoding="utf-8"))
        else:
            return default
    data.setdefault("ocp_payload_repository", OCP_DEFAULT_REPO)
    data.setdefault("families", [])
    return data


OWNERSHIP_LABELS = {
    "sre_managed": "Red Hat SRE Managed Services",
    "redhat_component": "Red Hat Components",
    "non_redhat": "Non-Red Hat",
}

REMEDIATION_LABELS = {
    "ocp_upgrade": "OCP Upgrade",
    "operator_update": "Operator Update",
    "vendor_image_update": "Vendor Image Update",
    "custom_rebuild": "Custom Image Rebuild",
    "review": "Needs Review",
}


def classify_family(image: str, namespace: str, cfg: dict) -> dict:
    """Classify a finding into remediation family and ownership.

    First YAML match wins. Ownership comes from image/repo/namespace
    classification only — never from RedHatSource (advisory source).

    Returns keys: family, vendor, ownership, remediation_type, action
    """
    img = (image or "").lower()
    ns = (namespace or "").lower()
    repo = extract_repository(image).lower()
    for fam in cfg.get("families") or []:
        match = fam.get("match") or {}
        hit = False
        # Prefer repository / image matches; namespace still allowed.
        for r in match.get("repository_equals") or []:
            if repo == str(r).lower():
                hit = True
        for needle in match.get("image_contains") or []:
            if str(needle).lower() in img:
                hit = True
        for n in match.get("namespace") or []:
            if ns == str(n).lower():
                hit = True
        for p in match.get("namespace_prefix") or []:
            if ns.startswith(str(p).lower()):
                hit = True
        for s in match.get("namespace_suffix") or []:
            if ns.endswith(str(s).lower()):
                hit = True
        if hit:
            return {
                "family": str(fam.get("name") or repo or "Unknown"),
                "vendor": str(fam.get("vendor") or "Unknown"),
                "ownership": str(fam.get("ownership") or "non_redhat"),
                "remediation_type": str(fam.get("remediation_type") or "review"),
                "action": str(fam.get("action") or "Review image owner/update path"),
            }
    default = cfg.get("default") or {}
    return {
        "family": extract_repository(image) or image or "Unknown",
        "vendor": str(default.get("vendor") or "Unknown"),
        "ownership": str(default.get("ownership") or "non_redhat"),
        "remediation_type": str(default.get("remediation_type") or "review"),
        "action": str(default.get("action") or "Determine application owner / update path"),
    }


DEFAULT_REVIEW_ACTION = "Determine application owner / update path"
_CATALOG_API = "https://catalog.redhat.com/api/containers/v1"
_REDHAT_REGISTRIES = ("registry.redhat.io/", "registry.access.redhat.com/")


def extract_tag(image: str) -> str:
    image = str(image or "").strip()
    if "@" in image:
        image = image.split("@", 1)[0]
    repo = extract_repository(image)
    prefix = repo + ":"
    if image.startswith(prefix):
        return image[len(prefix) :]
    return ""


def _catalog_get(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            if attempt == 2:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def _redhat_repo_name(repository: str) -> str:
    for prefix in _REDHAT_REGISTRIES:
        if repository.startswith(prefix):
            return repository[len(prefix) :]
    return ""


def _pick_version_tag(tags: list[str], running_tags: set[str]) -> str:
    names = [tag for tag in tags if tag and tag.lower() != "latest"]
    for running in sorted(running_tags):
        builds = [name for name in names if name.startswith(running + "-")]
        if builds:
            return sorted(builds, key=len)[-1]
    builds = [name for name in names if re.search(r"-\d{5,}$", name)]
    if builds:
        return sorted(builds)[-1]
    if names:
        return names[0]
    return "latest"


_PUBLISHED_CACHE: dict[str, dict | None] = {}


def published_redhat_image(repository: str) -> dict | None:
    """Current published image for a registry.redhat.io repository.

    Uses the catalog freshness grade (the image the floating tag points at).
    """
    if repository in _PUBLISHED_CACHE:
        return _PUBLISHED_CACHE[repository]
    found = _published_redhat_image(repository)
    _PUBLISHED_CACHE[repository] = found
    return found


def _published_redhat_image(repository: str) -> dict | None:
    repo_name = _redhat_repo_name(repository)
    if not repo_name:
        return None
    quoted = urllib.parse.quote(repo_name, safe="")
    document = None
    for registry in ("registry.access.redhat.com", "registry.redhat.io"):
        document = _catalog_get(
            f"{_CATALOG_API}/repositories/registry/{registry}/repository/{quoted}"
        )
        if document and document.get("repository"):
            break
        document = None
    if not document:
        return None
    image_id = ""
    for grade in document.get("content_stream_grades") or []:
        for item in grade.get("image_ids") or []:
            if str(item.get("arch") or "amd64") == "amd64" and item.get("id"):
                image_id = str(item["id"])
                break
        if image_id:
            break
    image = _catalog_get(f"{_CATALOG_API}/images/id/{image_id}") if image_id else None
    if not image:
        query = urllib.parse.urlencode(
            {
                "filter": f"repositories.repository=={repo_name}",
                "page_size": "30",
                "sort_by": "last_update_date[desc]",
            }
        )
        listed = _catalog_get(f"{_CATALOG_API}/images?{query}") or {}
        for candidate in listed.get("data") or []:
            if candidate.get("architecture") not in (None, "", "amd64"):
                continue
            image = candidate
            break
    if not image:
        return None
    published = ""
    tags: list[str] = []
    digests: set[str] = set()
    image_digest = str(image.get("image_id") or "")
    if image_digest:
        digests.add(image_digest.lower())
    for entry in image.get("repositories") or []:
        if str(entry.get("repository") or "") != repo_name:
            continue
        published = str(entry.get("push_date") or "")[:10]
        for key in ("manifest_list_digest", "manifest_schema2_digest"):
            value = str(entry.get(key) or "")
            if value:
                digests.add(value.lower())
        tags = [str(tag.get("name") or "") for tag in (entry.get("tags") or []) if tag.get("name")]
        break
    if not digests:
        return None
    return {"digests": digests, "tags": tags, "published": published}


def _dockerhub_repo(repository: str) -> tuple[str, str] | None:
    rest = ""
    for prefix in ("docker.io/", "registry-1.docker.io/", "index.docker.io/"):
        if repository.startswith(prefix):
            rest = repository[len(prefix) :]
            break
    if not rest:
        return None
    if "/" not in rest:
        return "library", rest
    namespace, name = rest.split("/", 1)
    if not namespace or not name or "/" in name:
        return None
    return namespace, name


def _parse_semver_tag(tag: str) -> tuple[tuple[int, ...], str] | None:
    match = re.match(r"^(v?)(\d+(?:\.\d+){1,3})([-.][A-Za-z].*)?$", tag)
    if not match:
        return None
    return tuple(int(part) for part in match.group(2).split(".")), match.group(3) or ""


def newer_semver_tag(running: str, candidates: list[str]) -> str:
    """Newest same-flavor tag within the same major version."""
    parsed = _parse_semver_tag(running)
    if not parsed:
        return ""
    running_version, suffix = parsed
    best: tuple[int, ...] | None = None
    best_tag = ""
    for tag in candidates:
        got = _parse_semver_tag(tag)
        if not got:
            continue
        version, candidate_suffix = got
        if candidate_suffix != suffix or not version or version[0] != running_version[0]:
            continue
        if version <= running_version:
            continue
        if best is None or version > best:
            best = version
            best_tag = tag
    return best_tag


_DOCKERHUB_TAGS: dict[str, list[str]] = {}


def dockerhub_tags(repository: str) -> list[str]:
    repo = _dockerhub_repo(repository)
    if not repo:
        return []
    cache_key = f"{repo[0]}/{repo[1]}"
    if cache_key in _DOCKERHUB_TAGS:
        return _DOCKERHUB_TAGS[cache_key]
    namespace, name = repo
    found: list[str] = []
    url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/tags?page_size=100&ordering=last_updated"
    for _page in range(3):
        document = _catalog_get(url)
        if not document:
            break
        for item in document.get("results") or []:
            tag = str(item.get("name") or "")
            if tag:
                found.append(tag)
        url = str(document.get("next") or "")
        if not url:
            break
    _DOCKERHUB_TAGS[cache_key] = found
    return found


def image_update_action(repository: str, digests: set[str], running_tags: set[str]) -> str:
    """Say whether a newer image tag is published than the one running."""
    installed = pick_tag(running_tags)
    if not _redhat_repo_name(repository):
        newer = newer_semver_tag(installed, dockerhub_tags(repository)) if installed else ""
        if newer:
            return update_image_action(repository, newer)
        if installed and _dockerhub_repo(repository):
            return f"No newer image ({image_popup_label(repository, installed)})"
        return "Not in the Red Hat image catalog"
    published = published_redhat_image(repository)
    if not published:
        return "Could not check for a newer image"
    version = _pick_version_tag(published["tags"], running_tags)
    running = {item.lower() for item in digests if item}
    current = published["digests"]
    if not running:
        return f"Latest published: {image_popup_label(repository, version)}"
    if running.issubset(current):
        shown = installed or version
        return f"No newer image ({image_popup_label(repository, shown)})"
    return update_image_action(repository, version)


def _image_updates_enabled() -> bool:
    # Phase 4B: default OFF (disconnected-safe). Explicit true/1/yes/on still enables
    # catalog.redhat.com / Docker Hub checks. Unset or empty → disabled.
    raw = os.environ.get("CVE_ANALYZER_IMAGE_UPDATE_CHECK", "false")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def annotate_image_updates(items: list[dict], by_family: dict[str, list[dict]]) -> None:
    """Replace the generic owner action with a catalog image-update check."""
    if not _image_updates_enabled():
        return
    targets: list[tuple[dict, str, set[str], set[str]]] = []
    for item in items:
        if item.get("Action") != DEFAULT_REVIEW_ACTION:
            continue
        group = by_family.get(item["Component"]) or []
        repository = next(
            (str(row.get("repository") or "") for row in group if row.get("repository")),
            str(item.get("Component") or ""),
        )
        digests = {str(row.get("digest") or "") for row in group if row.get("digest")}
        running_tags = {extract_tag(str(row.get("image") or "")) for row in group}
        running_tags.discard("")
        targets.append((item, repository, digests, running_tags))
    if not targets:
        return

    def _check(target: tuple[dict, str, set[str], set[str]]) -> None:
        item, repository, digests, running_tags = target
        item["Action"] = image_update_action(repository, digests, running_tags)

    workers = min(8, len(targets))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_check, targets))


def classify_rows(rows: list[dict], cfg: dict) -> None:
    """Add ownership/remediation metadata to every analytic row (in place)."""
    for row in rows:
        classification = classify_family(
            row.get("image", ""),
            row.get("namespace", ""),
            cfg,
        )
        row["family"] = classification["family"]
        row["vendor"] = classification["vendor"]
        row["ownership"] = classification["ownership"]
        row["remediation_type"] = classification["remediation_type"]
        row["remediation_action"] = classification["action"]


def summarize_rows(rows: list[dict]) -> dict:
    """Standard summary for any collection of findings."""
    sev = severity_counts(rows)
    critical_rows = [r for r in rows if r["severity"] == "Critical"]
    important_rows = [r for r in rows if r["severity"] == "Important"]
    return {
        "Findings": len(rows),
        "Critical": len(critical_rows),
        "Important": len(important_rows),
        # Full severity split for Findings-by-namespace rollups (High ≡ Important).
        "High": int(sev.get("Important", 0)),
        "Moderate": int(sev.get("Moderate", 0)),
        "Low": int(sev.get("Low", 0)),
        "Unique CVEs": len(unique_cves(rows)),
        "Unique Critical": len(unique_cves(rows, "Critical")),
        "Unique Important": len(unique_cves(rows, "Important")),
        "Fixable Findings": sum(1 for r in rows if r.get("fixable")),
    }


def ownership_summary(rows: list[dict]) -> list[dict]:
    """Mutually exclusive ownership buckets (finding occurrences)."""
    order = ["sre_managed", "redhat_component", "non_redhat"]
    groups: dict[str, list[dict]] = {k: [] for k in order}
    for row in rows:
        key = row.get("ownership") or "non_redhat"
        if key not in groups:
            key = "non_redhat"
        groups[key].append(row)
    out = []
    for key in order:
        summary = summarize_rows(groups[key])
        out.append(
            {
                "Ownership": OWNERSHIP_LABELS.get(key, key),
                **summary,
            }
        )
    return out


def _label_image_rows(
    items: list[dict],
    grouped: dict[str, list[dict]],
    installed: dict[str, set[str]] | None,
) -> None:
    for item in items:
        key = str(item.get("Component") or "")
        group = grouped.get(key) or []
        repository = next(
            (str(row.get("repository") or "") for row in group if row.get("repository")),
            key,
        )
        item["Repository"] = repository
        if "/" not in repository:
            continue
        item["Component"] = image_popup_label(repository, _group_tag(group, repository, installed))


def _append_missing_installed(
    items: list[dict],
    grouped: dict[str, list[dict]],
    installed: dict[str, set[str]] | None,
    known_repos: set[str],
) -> None:
    """RHACS omits images with no findings. Keep the running tag on the image table."""
    for repository, tags in (installed or {}).items():
        if repository in known_repos or "/" not in repository:
            continue
        tag_set = tags if isinstance(tags, (set, list, tuple)) else {str(tags)}
        tag = pick_tag(tag_set)
        if not tag:
            continue
        grouped[repository] = [{"repository": repository, "image": f"{repository}:{tag}", "digest": ""}]
        items.append(
            {
                "Component": repository,
                "Findings": 0,
                "Critical": 0,
                "Important": 0,
                "Unique CVEs": 0,
                "Unique Critical": 0,
                "Unique Important": 0,
                "Fixable Findings": 0,
                "Action": DEFAULT_REVIEW_ACTION,
            }
        )


def ownership_component_table(
    rows: list[dict],
    ownership: str,
    installed: dict[str, set[str]] | None = None,
) -> list[dict]:
    """Per-component breakdown inside one ownership bucket."""
    subset = [r for r in rows if (r.get("ownership") or "non_redhat") == ownership]
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in subset:
        by_family[str(row.get("family") or "Unknown")].append(row)
    out = []
    for family, group in by_family.items():
        summary = summarize_rows(group)
        action = next(
            (str(r.get("remediation_action") or "") for r in group if r.get("remediation_action")),
            "Review",
        )
        out.append(
            {
                "Component": family,
                **summary,
                "Action": action,
            }
        )
    if ownership == "non_redhat":
        known = {str(row.get("repository") or "") for row in rows if row.get("repository")}
        _append_missing_installed(out, by_family, installed, known)
        annotate_image_updates(out, by_family)
        _label_image_rows(out, by_family, installed)
        out.sort(
            key=lambda item: (
                0 if item["Findings"] == 0 and str(item["Action"]).startswith("update ") else 1,
                -item["Findings"],
                item["Component"],
            )
        )
    else:
        out.sort(key=lambda item: (-item["Findings"], item["Component"]))
    return out


def grouped_action_table(rows: list[dict], key: str) -> tuple[list[dict], dict[str, list[dict]]]:
    """One row per family or image repository, with the same columns as Non-Red Hat."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        name = str(row.get(key) or "").strip() or "Unknown"
        grouped[name].append(row)
    out = []
    for name, group in grouped.items():
        summary = summarize_rows(group)
        action = next(
            (str(item.get("remediation_action") or "") for item in group if item.get("remediation_action")),
            "Review",
        )
        out.append({"Component": name, **summary, "Action": action})
    out.sort(key=lambda item: (-item["Findings"], item["Component"]))
    return out, grouped


def all_components_table(rows: list[dict], cfg: dict) -> list[dict]:
    """Named products only. Unmatched image repositories stay on the image tables."""
    names = {str(fam.get("name")) for fam in (cfg.get("families") or []) if fam.get("name")}
    table, _grouped = grouped_action_table(
        [row for row in rows if row.get("family") in names],
        "family",
    )
    return table


def all_images_table(rows: list[dict], installed: dict[str, set[str]] | None = None) -> list[dict]:
    """Images that belong to a named component. Unmatched repos stay on Non-Red Hat images."""
    matched = [row for row in rows if (row.get("ownership") or "non_redhat") != "non_redhat"]
    table, grouped = grouped_action_table(matched, "repository")
    annotate_image_updates(table, grouped)
    _label_image_rows(table, grouped, installed)
    return table


def remediation_summary(rows: list[dict]) -> list[dict]:
    """How findings get fixed (remediation_type buckets)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        remediation_type = row.get("remediation_type") or "review"
        groups[str(remediation_type)].append(row)
    order = [
        "ocp_upgrade",
        "operator_update",
        "vendor_image_update",
        "custom_rebuild",
        "review",
    ]
    keys = order + [k for k in groups if k not in order]
    output = []
    for remediation_type in keys:
        group = groups.get(remediation_type) or []
        if not group and remediation_type not in groups:
            continue
        summary = summarize_rows(group)
        products = sorted({str(r.get("family") or "Unknown") for r in group})
        output.append(
            {
                "Remediation Path": REMEDIATION_LABELS.get(
                    remediation_type, remediation_type
                ),
                **summary,
                "Products": len(products),
                "Product List": ", ".join(products[:12])
                + ("…" if len(products) > 12 else ""),
            }
        )
    output.sort(key=lambda x: (-x["Findings"], x["Remediation Path"]))
    return output



def _finding_age_of(row: dict) -> str:
    return str(row.get("finding_age") or finding_age_bucket(row.get("age_days")))


def _cluster_of(row: dict) -> str:
    return str(row.get("cluster") or "Unknown").strip() or "Unknown"


def metrics_cluster_label(row: dict) -> str:
    """Prometheus cluster label. Empty/missing → explicit ``unknown`` (never dropped)."""
    name = str(row.get("cluster") or "").strip()
    return name if name else "unknown"


def severity_counts_by_cluster(rows: list[dict]) -> dict[str, dict[str, int]]:
    """Per-cluster severity finding counts for cve_posture_findings_by_cluster."""
    by_cluster: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        cluster = metrics_cluster_label(row)
        sev = str(row.get("severity") or "Unknown")
        by_cluster[cluster][sev] += 1
        by_cluster[cluster]["Total"] += 1
    return {
        cluster: {
            "Critical": counts.get("Critical", 0),
            "Important": counts.get("Important", 0),
            "Moderate": counts.get("Moderate", 0),
            "Low": counts.get("Low", 0),
            "Total": counts.get("Total", 0),
        }
        for cluster, counts in sorted(by_cluster.items())
    }


def metrics_namespace_label(row: dict) -> str:
    """RHACS namespace value for ``rhacs_namespace`` (not kube scrape ``namespace``).

    Empty/missing → explicit ``unknown`` (never dropped).
    """
    name = str(row.get("namespace") or "").strip()
    return name if name else "unknown"


def severity_counts_by_ns(
    rows: list[dict],
) -> dict[tuple[str, str], dict[str, int]]:
    """Per-(cluster, namespace) severity counts for cve_posture_findings_by_ns."""
    by_ns: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for row in rows:
        key = (metrics_cluster_label(row), metrics_namespace_label(row))
        sev = str(row.get("severity") or "Unknown")
        by_ns[key][sev] += 1
        by_ns[key]["Total"] += 1
    return {
        key: {
            "Critical": counts.get("Critical", 0),
            "Important": counts.get("Important", 0),
            "Moderate": counts.get("Moderate", 0),
            "Low": counts.get("Low", 0),
            "Total": counts.get("Total", 0),
        }
        for key, counts in sorted(by_ns.items())
    }


def discover_clusters(rows: list[dict]) -> list[str]:
    """Sorted unique RHACS cluster names present in analytic rows."""
    return sorted({_cluster_of(row) for row in rows})


def filter_rows_by_clusters(
    rows: list[dict],
    clusters: list[str] | tuple[str, ...] | None,
) -> tuple[list[dict], dict[str, Any]]:
    """Optionally restrict rows to exact RHACS cluster names.

    ``clusters`` empty/None → all clusters (existing behavior).
    Names must match the report exactly; unknown names raise ``ValueError``.
    Does not mutate or rewrite the source CSV.
    """
    available = discover_clusters(rows)
    selected = [str(name).strip() for name in (clusters or []) if str(name).strip()]
    # Preserve caller order while dropping duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in selected:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    if not ordered:
        meta = {
            "all_clusters": True,
            "selected": [],
            "available": available,
            "rows_before": len(rows),
            "rows_after": len(rows),
        }
        return rows, meta
    missing = [name for name in ordered if name not in set(available)]
    if missing:
        avail = ", ".join(available) if available else "(none)"
        raise ValueError(
            "cve_analyzer_clusters names not found in RHACS report: "
            + ", ".join(missing)
            + f". Available clusters: {avail}"
        )
    wanted = set(ordered)
    filtered = [row for row in rows if _cluster_of(row) in wanted]
    meta = {
        "all_clusters": False,
        "selected": ordered,
        "available": available,
        "rows_before": len(rows),
        "rows_after": len(filtered),
    }
    return filtered, meta


def namespace_remediation_rows(rows: list[dict]) -> list[dict]:
    """Cluster x namespace x age x ownership x remediation path for filter-then-sum."""
    by: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        own = row.get("ownership") or "non_redhat"
        own_label = OWNERSHIP_LABELS.get(own, own)
        by[
            (
                _cluster_of(row),
                str(row.get("namespace") or "Unknown"),
                _finding_age_of(row),
                own_label,
                str(row.get("remediation_type") or "review"),
            )
        ].append(row)
    out: list[dict] = []
    for (cluster, namespace, age, own_label, rem), group in sorted(by.items()):
        summary = summarize_rows(group)
        products = {str(r.get("family") or "Unknown") for r in group}
        out.append(
            {
                "Cluster": cluster,
                "Namespace": namespace,
                "Age": age,
                "Ownership": own_label,
                "Remediation Path": REMEDIATION_LABELS.get(rem, rem),
                **summary,
                "Products": len(products),
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    out.sort(
        key=lambda item: (
            -item["Findings"],
            item["Remediation Path"],
            item["Ownership"],
            item["Cluster"],
            item["Namespace"],
        )
    )
    return out


def ownership_label_order() -> list[str]:
    """Alphabetical — must match Grafana ``sre_variable`` sort=5 / ``:pipe`` order."""
    return sorted(OWNERSHIP_LABELS.values(), key=str.casefold)


def pipe_key(values: list[str], order: list[str]) -> str:
    """Join selected labels in dropdown order (Grafana ``:pipe`` order)."""
    wanted = set(values)
    return "|".join(item for item in order if item in wanted)


def cluster_all_key(clusters: list[str]) -> str:
    """Grafana Cluster All value: ``c1|c2|…|__ALL__`` (builder dashboard_cluster_all_value)."""
    parts = [
        str(c).strip()
        for c in clusters
        if str(c).strip() and str(c).strip() != FILTER_ALL
    ]
    ordered = sorted(dict.fromkeys(parts), key=str.casefold)
    if not ordered:
        return FILTER_ALL
    ordered.append(FILTER_ALL)
    return "|".join(ordered)


def finding_age_multi_keys(ages: list[str] | None = None) -> list[str]:
    """Grafana ``${finding_age:pipe}`` keys for multi-select age unions.

    Singles and ``FILTER_ALL`` are separate. Multi keys use dropdown option order
    so equal-filter matches ``15-30 days|30-60 days|Over 60 days`` (Over 14) etc.
    """
    ordered = list(ages) if ages is not None else list(FINDING_AGE_BUCKETS) + ["Unknown"]
    keys: list[str] = []
    for rank in range(2, len(ordered) + 1):
        for combo in combinations(range(len(ordered)), rank):
            keys.append("|".join(ordered[i] for i in combo))
    return keys


def unique_cves_kpi_filterable(rows: list[dict]) -> list[dict]:
    """Exact COUNT(DISTINCT CVE) rollups for the Unique KPI card.

    Rows carry ClusterKey / SreKey / Age for Grafana **equal** ``${var:pipe}``
    filters so All and single-select hit one precomputed union. Combined Finding
    age (Over 14 / Over 30 / arbitrary multi) uses **set union** of per-bucket
    CVE sets — never a sum of Unique counts. A CVE on findings in multiple age
    buckets is counted once in the combined-age key and once in ``Age=__ALL__``.

    Unsupported multis match no row → Grafana ``n/a`` (not zero / not a sum).
    """
    own_order = ownership_label_order()
    clusters = sorted(
        {
            _cluster_of(r)
            for r in rows
            if _cluster_of(r) and _cluster_of(r) != FILTER_ALL
        }
    )
    ages = list(FINDING_AGE_BUCKETS) + ["Unknown"]
    age_multi = finding_age_multi_keys(ages)
    age_keys_all = ages + [FILTER_ALL] + age_multi
    cl_all = cluster_all_key(clusters)
    cl_multi = "|".join(clusters) if len(clusters) > 1 else ""
    all_own_pipe = "|".join(own_order)

    # lookup_cl: real cluster or FILTER_ALL; own: label / pair / all-pipe / FILTER_ALL
    by: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        cve = str(row.get("cve") or "").strip()
        if not cve:
            continue
        cl = _cluster_of(row)
        own = OWNERSHIP_LABELS.get(
            row.get("ownership") or "non_redhat", "Non-Red Hat"
        )
        age = _finding_age_of(row)
        for cl_key in (cl, FILTER_ALL):
            for own_key in (own, FILTER_ALL):
                # Per-finding age membership (CVE may sit in several singles).
                by[(cl_key, own_key, age)].add(cve)
                by[(cl_key, own_key, FILTER_ALL)].add(cve)

    # Combined-age keys = set union of member buckets (exact distinct, not sum).
    base_own = list(own_order) + [FILTER_ALL]
    for cl_key in list(clusters) + [FILTER_ALL]:
        for own_key in base_own:
            for age_pipe in age_multi:
                union: set[str] = set()
                for part in age_pipe.split("|"):
                    union |= by.get((cl_key, own_key, part), set())
                by[(cl_key, own_key, age_pipe)] = union

    for i, a in enumerate(own_order):
        for b in own_order[i + 1 :]:
            pair = pipe_key([a, b], own_order)
            for cl_key in list(clusters) + [FILTER_ALL]:
                for age_key in age_keys_all:
                    by[(cl_key, pair, age_key)] = set(
                        by.get((cl_key, a, age_key), set())
                    ) | set(by.get((cl_key, b, age_key), set()))

    # Manual select-all-three chips → pipe of labels (not allValue __ALL__).
    for cl_key in list(clusters) + [FILTER_ALL]:
        for age_key in age_keys_all:
            by[(cl_key, all_own_pipe, age_key)] = set(
                by.get((cl_key, FILTER_ALL, age_key), set())
            )

    # (ClusterKey, lookup_cl)
    cluster_keys: list[tuple[str, str]] = [(cl_all, FILTER_ALL)]
    if cl_multi and cl_multi != cl_all:
        cluster_keys.append((cl_multi, FILTER_ALL))
    for cluster in clusters:
        cluster_keys.append((cluster, cluster))

    sre_keys = [FILTER_ALL, *own_order, all_own_pipe]
    for i, a in enumerate(own_order):
        for b in own_order[i + 1 :]:
            sre_keys.append(pipe_key([a, b], own_order))
    sre_keys = list(dict.fromkeys(sre_keys))

    out: list[dict] = []
    for ck, lc in cluster_keys:
        for sk in sre_keys:
            for ak in age_keys_all:
                cves = by.get((lc, sk, ak), set())
                out.append(
                    {
                        "Cluster": FILTER_ALL if lc == FILTER_ALL else ck,
                        "Namespace": FILTER_ALL,
                        "Age": ak,
                        "Ownership": FILTER_ALL if sk in (FILTER_ALL, all_own_pipe) else sk,
                        "ClusterKey": ck,
                        "SreKey": sk,
                        "Unique CVEs": len(cves),
                        "ClusterAll": FILTER_ALL,
                        "NsAll": FILTER_ALL,
                        "AgeAll": FILTER_ALL,
                        "OwnershipAll": FILTER_ALL,
                    }
                )
    return out


def unique_cves_by_ownership_age(rows: list[dict]) -> list[dict]:
    """Unique KPI rollups (ClusterKey / SreKey equal-filter grain)."""
    return unique_cves_kpi_filterable(rows)


def namespace_ownership_summary_rows(rows: list[dict]) -> list[dict]:
    """Cluster x namespace x age x ownership rollups."""
    order = ["sre_managed", "redhat_component", "non_redhat"]
    by: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        ownership = row.get("ownership") or "non_redhat"
        if ownership not in order:
            ownership = "non_redhat"
        by[(_cluster_of(row), str(row.get("namespace") or "Unknown"), _finding_age_of(row), ownership)].append(
            row
        )
    out: list[dict] = []
    for (cluster, namespace, age, ownership), group in sorted(by.items()):
        summary = summarize_rows(group)
        out.append(
            {
                "Cluster": cluster,
                "Namespace": namespace,
                "Age": age,
                "Ownership": OWNERSHIP_LABELS.get(ownership, ownership),
                **summary,
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    out.sort(key=lambda item: (-item["Findings"], item["Ownership"], item["Cluster"], item["Namespace"]))
    return out


def namespace_ownership_component_rows(
    rows: list[dict],
    ownership: str | None = None,
    *,
    named_families_only: bool = False,
    families_cfg: dict | None = None,
    key: str = "family",
) -> list[dict]:
    """Cluster x namespace x age x ownership x component rollups."""
    names = {
        str(fam.get("name"))
        for fam in ((families_cfg or {}).get("families") or [])
        if fam.get("name")
    }
    by: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        own = row.get("ownership") or "non_redhat"
        if ownership is not None and own != ownership:
            continue
        if named_families_only and row.get("family") not in names:
            continue
        cluster = _cluster_of(row)
        namespace = str(row.get("namespace") or "Unknown")
        age = _finding_age_of(row)
        component = str(row.get(key) or row.get("family") or "Unknown").strip() or "Unknown"
        own_label = OWNERSHIP_LABELS.get(own, own)
        by[(cluster, namespace, age, own_label, component)].append(row)
    out: list[dict] = []
    for (cluster, namespace, age, own_label, component), group in sorted(by.items()):
        summary = summarize_rows(group)
        action = next(
            (
                str(r.get("remediation_action") or "")
                for r in group
                if r.get("remediation_action")
            ),
            "Review",
        )
        repository = next(
            (str(r.get("repository") or "") for r in group if r.get("repository")),
            "",
        )
        out.append(
            {
                "Cluster": cluster,
                "Namespace": namespace,
                "Age": age,
                "Ownership": own_label,
                "Component": component,
                "Repository": repository,
                **summary,
                "Action": action,
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    out.sort(key=lambda item: (-item["Findings"], item["Component"], item["Cluster"], item["Namespace"]))
    return out


def _header_column_map(fieldnames: list[str] | None) -> dict[str, str]:
    """Map normalized header → original CSV column name (last duplicate wins).

    Phase 4C-2A: bind once per file so ``_pick`` does not re-normalize every
    column on every field lookup. Matches prior dict-comprehension order where
    later headers overwrite earlier ones for the same normalized key.
    """
    colmap: dict[str, str] = {}
    for name in fieldnames or []:
        colmap[_norm_col(name)] = name
    return colmap


def _pick(row: dict, *names: str, colmap: dict[str, str] | None = None) -> str:
    """Return first non-empty cell among alias names (normalized header match).

    When ``colmap`` is provided (preferred in ``load_scrubbed_rows``), headers are
    not re-normalized per call. Without ``colmap``, behavior matches the legacy
    per-call rebuild of a normalized key→value map from ``row.items()``.
    """
    if colmap is None:
        # Legacy path: rebuild normalized key → value (last column wins).
        norm = {_norm_col(k): v for k, v in row.items()}
        for name in names:
            key = _norm_col(name)
            if key in norm and norm[key] not in (None, ""):
                return str(norm[key])
        return ""

    for name in names:
        key = _norm_col(name)
        col = colmap.get(key)
        if col is None:
            continue
        val = row.get(col)
        if val not in (None, ""):
            return str(val)
    return ""


def load_scrubbed_rows(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    # Scrubbed export embeds RawVulnerabilityJSON / RawComponentJSON which can
    # exceed the default csv field size (128KiB).
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:  # pragma: no cover
        csv.field_size_limit(2**31 - 1)

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        # Phase 4C-2A: normalize/bind headers once per file (not per _pick).
        colmap = _header_column_map(list(reader.fieldnames or []))
        for raw in reader:
            # Drop giant unused blobs early so DictReader values stay small in RAM
            if "RawVulnerabilityJSON" in raw:
                raw["RawVulnerabilityJSON"] = ""
            if "RawComponentJSON" in raw:
                raw["RawComponentJSON"] = ""
            cve = _pick(raw, "CVE", "CVE ID", colmap=colmap).strip().upper()
            if not cve:
                continue
            image = _pick(raw, "Image", "Image Name", colmap=colmap)
            namespace = _pick(raw, "Namespace", colmap=colmap)
            discovered = parse_date(
                _pick(
                    raw,
                    "FirstSystemOccurrence",
                    "First Image Occurrence",
                    "Discovered At",
                    "Discovered",
                    colmap=colmap,
                )
            )
            # Prefer parser AgeDays when present
            age_raw = _pick(raw, "AgeDays", colmap=colmap)
            age = int(float(age_raw)) if age_raw not in ("", None) else None
            rows.append(
                {
                    "cve": cve,
                    "severity": normalize_severity(
                        _pick(raw, "Severity", colmap=colmap)
                    ),
                    "image": image,
                    "repository": extract_repository(image),
                    "digest": extract_digest(image)
                    or _pick(raw, "ImageDigest", colmap=colmap),
                    "cluster": _pick(raw, "Cluster", "ClusterName", colmap=colmap)
                    or "Unknown",
                    "namespace": namespace,
                    "deployment": _pick(
                        raw, "Deployment", "DeploymentName", colmap=colmap
                    ),
                    "component": _pick(
                        raw, "Component", "RHACSComponentGroup", colmap=colmap
                    )
                    or namespace
                    or "Unknown",
                    "discovered": discovered,
                    "age_days": age,
                    "redhat_source": _truthy(
                        _pick(raw, "RedHatSource", colmap=colmap)
                    ),
                    "fixable": _truthy(_pick(raw, "Fixable", colmap=colmap)),
                    "sources": _pick(raw, "Sources", colmap=colmap),
                }
            )
    return rows


def load_data_json_rows(path: Path) -> list[dict]:
    """Fallback: expand data.json rows (CVE+image aggregates) into analytic rows."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cve = str(item.get("cve") or "").strip().upper()
        if not cve:
            continue
        image = str(item.get("image_full") or item.get("image_short") or "")
        namespaces = str(item.get("namespaces") or "Unknown")
        ns_list = [n.strip() for n in re.split(r"[;,]", namespaces) if n.strip()] or ["Unknown"]
        discovered = parse_date(item.get("discovered"))
        sev = normalize_severity(item.get("severity") or item.get("rh_severity"))
        rh = bool(item.get("rh_severity") or item.get("rh_cvss"))
        for ns in ns_list:
            rows.append(
                {
                    "cve": cve,
                    "severity": sev,
                    "image": image,
                    "repository": extract_repository(image),
                    "digest": extract_digest(image),
                    "cluster": str(item.get("cluster") or "Unknown"),
                    "namespace": ns,
                    "deployment": str(item.get("deployment") or ""),
                    "component": str(item.get("product") or item.get("component") or ns or "Unknown"),
                    "discovered": discovered,
                    "age_days": None,
                    "redhat_source": rh,
                    "fixable": str(item.get("action") or "").upper() == "PATCH",
                    "sources": "",
                }
            )
    return rows


def finalize_ages(rows: list[dict], report_date: datetime) -> None:
    for row in rows:
        if row.get("age_days") is None:
            row["age_days"] = age_days(row.get("discovered"), report_date)
        row["age_bucket"] = age_bucket(row.get("age_days"))
        row["finding_age"] = finding_age_bucket(row.get("age_days"))


def unique_cves(rows: list[dict], severity: str | None = None) -> set[str]:
    out: set[str] = set()
    for r in rows:
        if severity and r["severity"] != severity:
            continue
        out.add(r["cve"])
    return out


def severity_counts(rows: list[dict]) -> Counter:
    return Counter(r["severity"] for r in rows)


def component_finding_table(rows: list[dict], key: str = "component") -> list[dict]:
    """Finding occurrences by component (not unique CVEs) — matches sample tables."""
    by: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        name = (r.get(key) or "Unknown").strip() or "Unknown"
        by[name][r["severity"]] += 1
        by[name]["Total"] += 1
    out = []
    for name, c in by.items():
        out.append(
            {
                "Component": name,
                "Total": c["Total"],
                "Critical": c.get("Critical", 0),
                "High": c.get("Important", 0),  # table header uses High
                "Moderate": c.get("Moderate", 0),
                "Low": c.get("Low", 0),
            }
        )
    out.sort(key=lambda x: (-x["Total"], x["Component"]))
    return out


def product_line_summary(rows: list[dict], cfg: dict) -> list[dict]:
    """Group by remediation family; count images, finding occurrences, unique CVEs, fixable."""
    groups: dict[str, dict] = {}
    for r in rows:
        family = r.get("family")
        action = r.get("remediation_action")
        if not family or not action:
            classification = classify_family(r["image"], r["namespace"], cfg)
            family = classification["family"]
            action = classification["action"]
        g = groups.setdefault(
            family,
            {"family": family, "action": action, "images": set(), "findings": 0, "cves": set(), "fixable": 0, "p1": 0},
        )
        if r["digest"]:
            g["images"].add(r["digest"])
        elif r["image"]:
            g["images"].add(r["image"])
        g["findings"] += 1
        g["cves"].add(r["cve"])
        if r.get("fixable"):
            g["fixable"] += 1
        if r["severity"] == "Critical":
            g["p1"] += 1
    out = []
    for g in groups.values():
        out.append(
            {
                "Product": g["family"],
                "Images": len(g["images"]),
                "Finding occurrences": g["findings"],
                "Fixable findings": g["fixable"],
                "Critical findings": g["p1"],
                "Unique CVEs": len(g["cves"]),
                "How to update": g["action"],
            }
        )
    out.sort(key=lambda x: (-x["Finding occurrences"], x["Product"]))
    return out


def namespace_stat_rows(rows: list[dict]) -> list[dict]:
    """Finding counts per cluster/namespace/age so Grafana can filter then sum."""
    by: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        cluster = _cluster_of(row)
        namespace = str(row.get("namespace") or "Unknown")
        age = str(row.get("finding_age") or finding_age_bucket(row.get("age_days")))
        by[(cluster, namespace, age)].append(row)
    out: list[dict] = []
    for cluster, namespace, age in sorted(by):
        group = by[(cluster, namespace, age)]
        sev = severity_counts(group)
        out.append(
            {
                "Cluster": cluster,
                "Namespace": namespace,
                "Age": age,
                "Total": len(group),
                "Critical": sev.get("Critical", 0),
                "Important": sev.get("Important", 0),
                "High": sev.get("Important", 0),
                "Moderate": sev.get("Moderate", 0),
                "Low": sev.get("Low", 0),
                "Fixable findings": sum(1 for item in group if item.get("fixable")),
                "Unique CVEs": len({str(item.get("cve") or "") for item in group if item.get("cve")}),
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    return out
def _namespace_metric_row(
    group: list[dict], cluster: str, namespace: str, age: str
) -> dict:
    sev = severity_counts(group)
    return {
        "Cluster": cluster,
        "Namespace": namespace,
        "Age": age,
        "Total": len(group),
        "Critical": sev.get("Critical", 0),
        "Important": sev.get("Important", 0),
        "High": sev.get("Important", 0),
        "Moderate": sev.get("Moderate", 0),
        "Low": sev.get("Low", 0),
        "Fixable findings": sum(1 for item in group if item.get("fixable")),
        "Unique CVEs": len({str(item.get("cve") or "") for item in group if item.get("cve")}),
        "ClusterAll": FILTER_ALL,
        "NsAll": FILTER_ALL,
        "AgeAll": FILTER_ALL,
    }


def namespace_filter_rollups(rows: list[dict]) -> list[dict]:
    """Exact totals for All clusters/namespaces/ages combinations.

    Slice rows stay in namespace_stat_rows. Extra rows use FILTER_ALL tokens so
    strict dropdown matches can show one number without listing every CVE.
    """
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    by_cluster_ns: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_cluster_age: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_ns: dict[str, list[dict]] = defaultdict(list)
    by_age: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        cluster = _cluster_of(row)
        namespace = str(row.get("namespace") or "Unknown")
        age = str(row.get("finding_age") or finding_age_bucket(row.get("age_days")))
        by_cluster[cluster].append(row)
        by_cluster_ns[(cluster, namespace)].append(row)
        by_cluster_age[(cluster, age)].append(row)
        by_ns[namespace].append(row)
        by_age[age].append(row)
    out: list[dict] = []
    # Per cluster totals (All namespaces, All ages)
    out.extend(
        _namespace_metric_row(group, cluster, FILTER_ALL, FILTER_ALL)
        for cluster, group in sorted(by_cluster.items())
    )
    # Per cluster + namespace (All ages)
    out.extend(
        _namespace_metric_row(group, cluster, namespace, FILTER_ALL)
        for (cluster, namespace), group in sorted(by_cluster_ns.items())
    )
    # Per cluster + age (All namespaces)
    out.extend(
        _namespace_metric_row(group, cluster, FILTER_ALL, age)
        for (cluster, age), group in sorted(by_cluster_age.items())
    )
    # Cross-cluster namespace / age / grand total (Cluster = All token)
    out.extend(
        _namespace_metric_row(group, FILTER_ALL, namespace, FILTER_ALL)
        for namespace, group in sorted(by_ns.items())
    )
    out.extend(
        _namespace_metric_row(group, FILTER_ALL, FILTER_ALL, age)
        for age, group in sorted(by_age.items())
    )
    out.append(_namespace_metric_row(rows, FILTER_ALL, FILTER_ALL, FILTER_ALL))
    return out


def namespace_critical_bars(rows: list[dict], limit: int = 12) -> list[tuple]:
    """Top namespaces by critical count, split by cluster and finding age."""
    by_slice: Counter = Counter()
    by_ns: Counter = Counter()
    for row in rows:
        if row["severity"] != "Critical":
            continue
        cluster = _cluster_of(row)
        namespace = row["namespace"] or "Unknown"
        age = str(row.get("finding_age") or finding_age_bucket(row.get("age_days")))
        by_slice[(cluster, namespace, age)] += 1
        by_ns[(cluster, namespace)] += 1
    top = {key for key, _count in by_ns.most_common(limit)}
    out = [
        (cluster, namespace, age, count)
        for (cluster, namespace, age), count in by_slice.items()
        if (cluster, namespace) in top
    ]
    out.sort(key=lambda item: (-item[3], item[0], item[1], item[2]))
    return out


def ocp_payload_report(rows: list[dict], cfg: dict) -> dict:
    repo = (cfg.get("ocp_payload_repository") or OCP_DEFAULT_REPO).lower()
    ocp = [r for r in rows if str(r.get("repository") or "").lower() == repo]
    critical = unique_cves(ocp, "Critical")
    important = unique_cves(ocp, "Important")
    digests = {r["digest"] for r in ocp if r.get("digest")}
    return {
        "repository": repo,
        "vulnerable_digests": len(digests),
        "unique_critical": len(critical),
        "unique_important": len(important),
        "unique_total": len(critical | important),
        "finding_occurrences": len(ocp),
        "rows": ocp,
    }


def ocp_payload_by_cluster(rows: list[dict], cfg: dict) -> dict[str, dict]:
    """Per-cluster OpenShift payload rollups (cluster-wide within each cluster)."""
    repo = (cfg.get("ocp_payload_repository") or OCP_DEFAULT_REPO).lower()
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if str(row.get("repository") or "").lower() != repo:
            continue
        by_cluster[_cluster_of(row)].append(row)
    out: dict[str, dict] = {}
    for cluster, group in sorted(by_cluster.items()):
        report = ocp_payload_report(group, cfg)
        out[cluster] = {k: v for k, v in report.items() if k != "rows"}
    return out


def unique_cve_age_buckets(rows: list[dict], severity: str, report_date: datetime) -> dict[str, int]:
    """One age per unique CVE using earliest discovered date."""
    earliest: dict[str, datetime] = {}
    for r in rows:
        if r["severity"] != severity:
            continue
        disc = r.get("discovered")
        if disc is None:
            continue
        prev = earliest.get(r["cve"])
        if prev is None or disc < prev:
            earliest[r["cve"]] = disc
    buckets = {b: 0 for b in AGE_BUCKETS}
    buckets["Unknown"] = 0
    for cve, disc in earliest.items():
        buckets[age_bucket(age_days(disc, report_date))] += 1
    # Also count CVEs with no date via age_days on any row
    dated = set(earliest)
    for r in rows:
        if r["severity"] != severity or r["cve"] in dated:
            continue
        buckets[age_bucket(r.get("age_days"))] += 1
        dated.add(r["cve"])
    return buckets


def unique_cve_age_buckets_by_cluster(
    rows: list[dict], severity: str, report_date: datetime, cfg: dict
) -> dict[str, dict[str, int]]:
    """Per-cluster unique-CVE age distribution for OCP payload images."""
    repo = (cfg.get("ocp_payload_repository") or OCP_DEFAULT_REPO).lower()
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if str(row.get("repository") or "").lower() != repo:
            continue
        by_cluster[_cluster_of(row)].append(row)
    return {
        cluster: unique_cve_age_buckets(group, severity, report_date)
        for cluster, group in sorted(by_cluster.items())
    }


def drilldown_rows(rows: list[dict], cfg: dict, limit: int = 16000) -> list[dict]:
    """One row per namespace, component, image, and CVE so a click can filter to it.

    Critical and Important are kept first. Moderate and Low stop at ``limit``
    so the dashboard stays small enough for Grafana to open.
    """
    payload_repo = (cfg.get("ocp_payload_repository") or OCP_DEFAULT_REPO).lower()
    rank = {"Critical": 0, "Important": 1, "Moderate": 2, "Low": 3}
    seen: set[tuple] = set()
    kept: list[dict] = []
    for row in sorted(rows, key=lambda item: rank.get(item.get("severity"), 9)):
        severity = str(row.get("severity") or "Unknown")
        if len(kept) >= limit and rank.get(severity, 9) > 1:
            continue
        namespace = str(row.get("namespace") or "Unknown")
        family = str(row.get("family") or "Unknown")
        repository = str(row.get("repository") or "")
        cve = str(row.get("cve") or "")
        days = row.get("age_days")
        bucket = age_bucket(days if isinstance(days, int) else None)
        action = str(row.get("remediation_action") or "Review")
        key = (_cluster_of(row), namespace, family, repository, cve, severity, bucket, action)
        if key in seen:
            continue
        seen.add(key)
        tag = extract_tag(str(row.get("image") or ""))
        image = image_popup_label(repository, tag) or str(row.get("image") or repository)
        kept.append(
            {
                "Cluster": _cluster_of(row),
                "Namespace": namespace,
                "Ownership": OWNERSHIP_LABELS.get(row.get("ownership") or "non_redhat", "Non-Red Hat"),
                "Component": family,
                "Repository": repository,
                "Image": image,
                "CVE": cve,
                "Severity": severity,
                "Age bucket": bucket,
                "Age": finding_age_bucket(days if isinstance(days, int) else None),
                "Over 30": "Yes" if isinstance(days, int) and days >= 30 else "No",
                "Payload": "Yes" if repository.lower() == payload_repo else "No",
                "Source": (
                    "Red Hat sources"
                    if row.get("redhat_source")
                    else "Non-Red Hat sources"
                ),
                "Action": action,
                "Show": "yes",
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    return kept


def component_over_30(rows: list[dict]) -> list[dict]:
    old = [r for r in rows if r.get("age_days") is not None and r["age_days"] >= 30]
    by_ns: dict[tuple[str, str, str], list] = defaultdict(list)
    for r in old:
        cluster = _cluster_of(r)
        namespace = r["namespace"] or "Unknown"
        age = str(r.get("finding_age") or finding_age_bucket(r.get("age_days")))
        by_ns[(cluster, namespace, age)].append(r)
    out = []
    for (cluster, namespace, age), group in by_ns.items():
        crit = unique_cves(group, "Critical")
        high = unique_cves(group, "Important")
        out.append(
            {
                "Cluster": cluster,
                "Namespace": namespace,
                "Component": namespace,
                "Age": age,
                "Critical": len(crit),
                "High": len(high),
                "Total >30 Days": len(crit | high),
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    out.sort(
        key=lambda x: (-x["Total >30 Days"], -x["Critical"], x["Cluster"], x["Namespace"], x["Age"])
    )
    return out
def image_family_table(rows: list[dict], cfg: dict) -> list[dict]:
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        family = r.get("family")
        action = r.get("remediation_action")
        if not family or not action:
            classification = classify_family(r["image"], r["namespace"], cfg)
            family = classification["family"]
            action = classification["action"]
        groups[(family, action)].add(r["cve"])
    out = [
        {
            "Current image family": family,
            "Unique CVEs": len(cves),
            "How to update": action,
        }
        for (family, action), cves in groups.items()
    ]
    out.sort(key=lambda x: (-x["Unique CVEs"], x["Current image family"]))
    return out


def _local_generated_at() -> str:
    now = datetime.now(ZoneInfo("America/New_York"))
    clock = now.strftime("%I:%M %p").lstrip("0")
    return f"{now.strftime('%Y-%m-%d')} {clock} ET"


def scrubbed_pull_time(path: Path | None) -> datetime:
    """UTC time from RHACS_Vulnerability_Report_SCRUBBED_YYYY-MM-DD_HHMMSS."""
    match = None
    if path is not None:
        match = re.search(
            r"RHACS_Vulnerability_Report_SCRUBBED_(\d{4}-\d{2}-\d{2}_\d{6})",
            path.name,
        )
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def format_report_pulled(when: datetime) -> str:
    local = when.astimezone(ZoneInfo("America/New_York"))
    clock = local.strftime("%I:%M %p").lstrip("0")
    return f"{local.strftime('%Y-%m-%d')} {clock} ET"


def csv_report_display_name(path: Path | None) -> str:
    """Saved report filename, clock in Eastern, from the UTC stamp in the name."""
    local = scrubbed_pull_time(path).astimezone(ZoneInfo("America/New_York"))
    clock = local.strftime("%I-%M_%p").lstrip("0")
    day = local.strftime("%d_%B_%Y")
    return f"RHACS_Vulnerability_Report_SCRUBBED_{day}_{clock}.csv"



def _short_image(image: str) -> str:
    image = str(image or "")
    if "@sha256:" in image:
        repo, dig = image.split("@sha256:", 1)
        return f"{repo}@sha256:{dig[:12]}…"
    if len(image) > 72:
        return image[:69] + "…"
    return image or "Unknown"


def _workload_ref(namespace: str, deployment: str) -> str:
    ns = (namespace or "").strip() or "Unknown"
    dep = (deployment or "").strip()
    return f"{ns}/{dep}" if dep else ns


def _format_workloads(workloads: list[str], show: int = 3) -> str:
    if not workloads:
        return "—"
    shown = workloads[:show]
    extra = len(workloads) - len(shown)
    text = ", ".join(shown)
    if extra > 0:
        text = f"{text} (+{extra} more)"
    return text


def _age_days_label(age_days: int | None) -> str:
    if age_days is None:
        return "—"
    if age_days < 1:
        return "<1d"
    return f"{int(age_days)}d"


def simple_view_rows(rows: list[dict], limit: int = 200) -> list[dict]:
    """Discover-email style image table (fixable Critical/Important).

    One row per cluster + namespace + image + finding-age bucket so Cluster,
    Namespace, and Finding age dashboard filters narrow correctly. ``Age`` is
    the finding-age bucket (same tokens as other CSV panels); ``Oldest`` is
    Discover-style oldest finding age in days within that bucket.
    """
    buckets: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        if not row.get("fixable"):
            continue
        sev = str(row.get("severity") or "")
        if sev not in {"Critical", "Important"}:
            continue
        cluster = _cluster_of(row)
        namespace = str(row.get("namespace") or "Unknown")
        image = str(row.get("image") or "").strip() or "Unknown"
        age_label = _finding_age_of(row)
        key = (cluster, namespace, image, age_label)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "cluster": cluster,
                "namespace": namespace,
                "image": image,
                "age": age_label,
                "deployments": set(),
                "critical_cves": set(),
                "important_cves": set(),
                "age_days": None,
            }
            buckets[key] = bucket
        dep = str(row.get("deployment") or "").strip()
        bucket["deployments"].add(_workload_ref(namespace, dep))
        cve = str(row.get("cve") or "")
        if sev == "Critical" and cve:
            bucket["critical_cves"].add(cve)
        elif sev == "Important" and cve:
            bucket["important_cves"].add(cve)
        age = row.get("age_days")
        if isinstance(age, int):
            if bucket["age_days"] is None or age > bucket["age_days"]:
                bucket["age_days"] = age

    out: list[dict] = []
    for bucket in buckets.values():
        critical = len(bucket["critical_cves"])
        important = len(bucket["important_cves"])
        if critical + important <= 0:
            continue
        out.append(
            {
                "Cluster": bucket["cluster"],
                "Namespace": bucket["namespace"],
                "Image": _short_image(bucket["image"]),
                "ImageFull": bucket["image"],
                "Namespace / deployment": _format_workloads(
                    sorted(bucket["deployments"])
                ),
                "Age": bucket["age"],
                "Oldest": _age_days_label(bucket["age_days"]),
                "Critical": critical,
                "Important": important,
                "Status": "needs_update",
                "ClusterAll": FILTER_ALL,
                "NsAll": FILTER_ALL,
                "AgeAll": FILTER_ALL,
            }
        )
    out.sort(
        key=lambda item: (
            -int(item["Critical"]),
            -int(item["Important"]),
            item["Cluster"],
            item["Namespace"],
            item["Image"],
            item["Age"],
        )
    )
    return out[: max(1, int(limit))]


def _timing_line(phase: str, seconds: float, **fields: Any) -> None:
    """Phase 4C-0: stdout timing for Contoller / local logs (no secrets)."""
    extras = " ".join(f"{key}={value}" for key, value in fields.items())
    suffix = f" {extras}" if extras else ""
    print(f"TIMING Dashboard Build/{phase}: {seconds:.3f}s{suffix}", flush=True)


def build_analysis(
    rows: list[dict],
    report_date: datetime,
    families_cfg: dict,
    source_label: str,
    installed: dict[str, set[str]] | None = None,
) -> dict:
    t_roll = time.perf_counter()
    finalize_ages(rows, report_date)
    # Ownership/remediation from image_families.yaml — not RedHatSource.
    classify_rows(rows, families_cfg)
    all_rows = rows
    rh_rows = [r for r in rows if r.get("redhat_source")]
    non_rh_source_rows = [r for r in rows if not r.get("redhat_source")]
    ocp = ocp_payload_report(all_rows, families_cfg)

    def pack(subset: list[dict]) -> dict:
        sev = severity_counts(subset)
        return {
            "finding_occurrences": len(subset),
            "unique_cves": len(unique_cves(subset)),
            "fixable_findings": sum(1 for r in subset if r.get("fixable")),
            "severity": {
                "Critical": sev.get("Critical", 0),
                "Important": sev.get("Important", 0),
                "Moderate": sev.get("Moderate", 0),
                "Low": sev.get("Low", 0),
                "Total": len(subset),
            },
            "unique_severity": {
                "Critical": len(unique_cves(subset, "Critical")),
                "Important": len(unique_cves(subset, "Important")),
            },
            "by_component": component_finding_table(subset, key="component"),
            "by_namespace_component": component_finding_table(subset, key="namespace"),
            "by_namespace": namespace_stat_rows(subset),
            "namespace_rollups": namespace_filter_rollups(subset),
            "product_lines": product_line_summary(subset, families_cfg),
            "critical_by_namespace": namespace_critical_bars(subset),
        }

    def filterable_pack(subset: list[dict]) -> dict:
        """Namespace-aware rollups for one Source slice (All / RH / Non-RH)."""
        ocp_slice = ocp_payload_report(subset, families_cfg)
        return {
            "filterable_remediation": namespace_remediation_rows(subset),
            "filterable_ownership": namespace_ownership_summary_rows(subset),
            "unique_cves_by_ownership_age": unique_cves_by_ownership_age(subset),
            "filterable_sre_managed_components": namespace_ownership_component_rows(
                subset, "sre_managed"
            ),
            "filterable_redhat_components": namespace_ownership_component_rows(
                subset, "redhat_component"
            ),
            "filterable_non_redhat_components": namespace_ownership_component_rows(
                subset, "non_redhat", key="repository"
            ),
            "filterable_all_components": namespace_ownership_component_rows(
                subset,
                named_families_only=True,
                families_cfg=families_cfg,
            ),
            "filterable_all_images": namespace_ownership_component_rows(
                subset,
                ownership="redhat_component",
                key="repository",
            )
            + namespace_ownership_component_rows(
                subset,
                ownership="sre_managed",
                key="repository",
            ),
            "component_over_30": component_over_30(subset),
            "simple_view": simple_view_rows(subset),
            "ocp": {k: v for k, v in ocp_slice.items() if k != "rows"},
            "ocp_by_cluster": ocp_payload_by_cluster(subset, families_cfg),
            "ocp_age_critical": unique_cve_age_buckets(
                ocp_slice["rows"], "Critical", report_date
            ),
            "ocp_age_important": unique_cve_age_buckets(
                ocp_slice["rows"], "Important", report_date
            ),
            "ocp_age_critical_by_cluster": unique_cve_age_buckets_by_cluster(
                subset, "Critical", report_date, families_cfg
            ),
            "ocp_age_important_by_cluster": unique_cve_age_buckets_by_cluster(
                subset, "Important", report_date, families_cfg
            ),
        }

    filterables_all = filterable_pack(all_rows)
    filterables_rh = filterable_pack(rh_rows)
    filterables_nrs = filterable_pack(non_rh_source_rows)
    analysis = {
        "source_label": source_label,
        "report_date": report_date.strftime("%Y-%m-%d"),
        "generated_at": _local_generated_at(),
        "all": pack(all_rows),
        "redhat": pack(rh_rows),
        "non_redhat_sources": pack(non_rh_source_rows),
        "ownership_summary": ownership_summary(all_rows),
        "sre_managed_components": ownership_component_table(all_rows, "sre_managed"),
        "redhat_components": ownership_component_table(all_rows, "redhat_component"),
        "non_redhat_components": ownership_component_table(all_rows, "non_redhat", installed),
        "all_components": all_components_table(all_rows, families_cfg),
        "all_images": all_images_table(all_rows, installed),
        "remediation_summary": remediation_summary(all_rows),
        # Namespace-aware rollups for Grafana filter-then-aggregate (Phase 1).
        # Root keys remain the All-sources slice for backward-compatible tests.
        **{k: v for k, v in filterables_all.items() if k.startswith("filterable_")},
        "component_over_30": filterables_all["component_over_30"],
        "filterables_by_source": {
            "All sources": filterables_all,
            "Red Hat sources": filterables_rh,
            "Non-Red Hat sources": filterables_nrs,
        },
        "ocp": {k: v for k, v in ocp.items() if k != "rows"},
        "ocp_by_cluster": filterables_all["ocp_by_cluster"],
        "ocp_age_critical": filterables_all["ocp_age_critical"],
        "ocp_age_important": filterables_all["ocp_age_important"],
        "ocp_age_critical_by_cluster": filterables_all["ocp_age_critical_by_cluster"],
        "ocp_age_important_by_cluster": filterables_all["ocp_age_important_by_cluster"],
        "image_families": image_family_table(all_rows, families_cfg),
        "simple_view": filterables_all["simple_view"],
    }
    _timing_line(
        "classify_analytics_rollups",
        time.perf_counter() - t_roll,
        rows=len(all_rows),
    )

    t_detail = time.perf_counter()
    analysis["drilldown"] = drilldown_rows(all_rows, families_cfg)
    _timing_line(
        "detail_panel_90_rows",
        time.perf_counter() - t_detail,
        detail_rows=len(analysis["drilldown"]),
    )
    return analysis


def analyze_paths(
    scrubbed_csv: Path | None,
    data_json: Path | None,
    families_yaml: Path | None,
    report_date: datetime | None = None,
    installed: dict[str, set[str]] | None = None,
    clusters: list[str] | tuple[str, ...] | None = None,
) -> dict:
    families_cfg = load_image_families(families_yaml)
    rows: list[dict] | None = None
    source_label = ""
    t_load = time.perf_counter()
    if scrubbed_csv and scrubbed_csv.exists():
        try:
            rows = load_scrubbed_rows(scrubbed_csv)
            source_label = f"scrubbed CSV ({scrubbed_csv.name})"
        except csv.Error as exc:
            # Fall back so Grafana still updates if scrubbed CSV is unreadable.
            print(f"WARNING: scrubbed CSV load failed ({exc}); falling back to data.json")
            rows = None
    if rows is None:
        if data_json and data_json.exists():
            rows = load_data_json_rows(data_json)
            source_label = f"data.json fallback ({data_json.name})"
        else:
            raise FileNotFoundError("Need scrubbed CSV or data.json")
    _timing_line(
        "csv_load_parse",
        time.perf_counter() - t_load,
        rows=len(rows),
        source=source_label.split("(")[0].strip().replace(" ", "_"),
    )
    if report_date is None:
        report_date = scrubbed_pull_time(scrubbed_csv if scrubbed_csv and scrubbed_csv.exists() else None)

    # Legacy + by-cluster + by-ns gauges. Always from the full report — never from
    # cve_analyzer_clusters / dashboard table filters.
    metrics_sev = severity_counts(rows)
    metrics_severity = {
        "Critical": metrics_sev.get("Critical", 0),
        "Important": metrics_sev.get("Important", 0),
        "Moderate": metrics_sev.get("Moderate", 0),
        "Low": metrics_sev.get("Low", 0),
        "Total": len(rows),
    }
    metrics_by_cluster = severity_counts_by_cluster(rows)
    metrics_by_ns = severity_counts_by_ns(rows)

    t_filter = time.perf_counter()
    filtered, cluster_scope = filter_rows_by_clusters(rows, clusters)
    scope_label = (
        "all"
        if cluster_scope["all_clusters"]
        else ",".join(cluster_scope["selected"])
    )
    _timing_line(
        "cluster_filter",
        time.perf_counter() - t_filter,
        rows_before=cluster_scope["rows_before"],
        rows_after=cluster_scope["rows_after"],
        clusters=scope_label or "all",
    )
    if not cluster_scope["all_clusters"]:
        source_label = f"{source_label}; clusters={scope_label}"

    analysis = build_analysis(filtered, report_date, families_cfg, source_label, installed)
    pulled = scrubbed_pull_time(scrubbed_csv if scrubbed_csv and scrubbed_csv.exists() else None)
    analysis["csv_report_name"] = csv_report_display_name(
        scrubbed_csv if rows and scrubbed_csv else None
    )
    analysis["report_pulled"] = format_report_pulled(pulled)
    analysis["cluster_scope"] = cluster_scope
    analysis["metrics_severity_all_clusters"] = metrics_severity
    analysis["metrics_severity_by_cluster"] = metrics_by_cluster
    analysis["metrics_severity_by_ns"] = metrics_by_ns
    analysis["metrics_scope"] = "all_clusters"
    return analysis
