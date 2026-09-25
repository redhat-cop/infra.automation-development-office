"""Adapt a Grafana dashboard JSON for OpenshiftProd / OpenshiftProdInfra / Openshift folders."""
from __future__ import annotations

import argparse
import json
import re
import sys


K8S_VAR = {
    "current": {"selected": True, "text": "OpenshiftProd", "value": "OpenshiftProd"},
    "hide": 0,
    "includeAll": False,
    "label": "K8S",
    "multi": False,
    "name": "datasource",
    "options": [],
    "query": "prometheus",
    "refresh": 1,
    # Only OpenshiftProd and OpenshiftProdInfra (uid == name from create_datasource).
    "regex": "/^OpenshiftProd(Infra)?$/",
    "skipUrlSync": False,
    "type": "datasource",
}

# String / uid forms that should be remapped to the folder Prometheus target.
# Keep legacy Openshift-Prod / Openshift-Dev so old source JSON is rewritten.
LEGACY_DS_STRINGS = {
    "Openshift",
    "Openshift-Prod",
    "Openshift-Dev",
    "OpenshiftProd",
    "OpenshiftProdInfra",
    "Prometheus",
    "prometheus",
    "grafana_datasource",
    "{{ grafana_datasource }}",
    "${grafana_datasource}",
    "${datasource}",
    "${DS_OPENSHIFT}",
    "DS_OPENSHIFT",
    "$datasource",
}


def load(path: str) -> dict:
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"\{%\s*raw\s*%\}\s*", "", text)
    text = re.sub(r"\s*\{%\s*endraw\s*%\}", "", text)
    # If Jinja left an unreplaced grafana_datasource token, make JSON parseable
    # and rewrite to a known placeholder that rewrite_prometheus_ds will fix.
    text = text.replace("{{ grafana_datasource }}", "grafana_datasource")
    return json.loads(text)


def ensure_k8s_var(dash: dict, *, pinned: str | None = None, hide: int = 0) -> None:
    templating = dash.setdefault("templating", {})
    others = [v for v in templating.get("list", []) if v.get("name") != "datasource"]
    var = json.loads(json.dumps(K8S_VAR))
    var["hide"] = hide
    if pinned:
        var["current"] = {"selected": True, "text": pinned, "value": pinned}
        var["regex"] = f"/^{re.escape(pinned)}$/"
        var["query"] = "prometheus"
    others.insert(0, var)
    templating["list"] = others


def _should_rewrite_ds(ds, *, all_prometheus: bool = False) -> bool:
    """Return True if this datasource ref should be remapped.

    Contoller / Grafana-exported boards often use opaque UIDs (e.g. PBFA97CFB…)
    that are not Openshift-* / grafana_datasource. For pin|multi, rewrite every
    prometheus-typed ref; otherwise only legacy ADO placeholders.
    """
    if isinstance(ds, str):
        if ds in LEGACY_DS_STRINGS:
            return True
        if ds.startswith("Openshift"):
            return True
        if "grafana_datasource" in ds or "DS_OPENSHIFT" in ds:
            return True
        if ds.startswith("${") and "datasource" in ds.lower():
            return True
        # pin|multi: any bare string prometheus-looking name (not Loki/Tempo/etc.)
        if all_prometheus and ds.lower() not in (
            "loki",
            "tempo",
            "jaeger",
            "elasticsearch",
            "grafana",
            "-- dashboard --",
            "-- mixed --",
        ):
            return True
        return False
    if isinstance(ds, dict):
        ds_type = (ds.get("type") or "").lower()
        uid = str(ds.get("uid") or "")
        name = str(ds.get("name") or "")
        if ds_type in ("prometheus", ""):
            # pin|multi: always remap prometheus (including opaque Grafana UIDs)
            if all_prometheus:
                return True
            if (
                uid in LEGACY_DS_STRINGS
                or name in LEGACY_DS_STRINGS
                or uid.startswith("Openshift")
                or name.startswith("Openshift")
                or "grafana_datasource" in uid
                or "grafana_datasource" in name
                or "DS_OPENSHIFT" in uid
                or "DS_OPENSHIFT" in name
                or uid.startswith("${")
            ):
                return True
            # Bare / empty prometheus refs
            if not uid and not name:
                return True
        return False
    return False


def rewrite_prometheus_ds(
    obj, pinned: str | None = None, *, all_prometheus: bool = False
) -> None:
    target = {"type": "prometheus", "uid": pinned or "${datasource}"}
    if isinstance(obj, dict):
        if "datasource" in obj and _should_rewrite_ds(
            obj["datasource"], all_prometheus=all_prometheus
        ):
            obj["datasource"] = dict(target)
        for v in obj.values():
            rewrite_prometheus_ds(v, pinned=pinned, all_prometheus=all_prometheus)
    elif isinstance(obj, list):
        for v in obj:
            rewrite_prometheus_ds(v, pinned=pinned, all_prometheus=all_prometheus)


def apply_uid(dash: dict, uid_suffix: str) -> None:
    base = str(dash.get("uid") or "ado-dashboard")
    # strip prior cluster suffixes
    base = re.sub(r"-(prod|dev|infra)$", "", base, flags=re.I)
    dash["uid"] = f"{base}{uid_suffix}" if uid_suffix else base


def apply_title(dash: dict, title_cluster: str, mode: str) -> None:
    title = str(dash.get("title") or "Dashboard")
    title = re.sub(r"^OpenShift\s+(Prod|Dev|Infra)\s*[—-]\s*", "OpenShift — ", title, flags=re.I)
    title = re.sub(r"^OpenShift\s*[—-]\s*", "OpenShift — ", title, flags=re.I)
    if mode == "pin" and title_cluster:
        # OpenshiftProd / OpenshiftProdInfra folders: cluster-specific title
        if title.startswith("OpenShift — "):
            dash["title"] = f"OpenShift {title_cluster} — {title[len('OpenShift — '):]}"
        else:
            dash["title"] = f"OpenShift {title_cluster} — {title}"
    else:
        dash["title"] = title if title.startswith("OpenShift") else title


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--mode", choices=("pin", "multi", "none"), default="none")
    parser.add_argument("--datasource", default="")
    parser.add_argument(
        "--datasource-uid",
        default="",
        help="Grafana datasource uid (defaults to --datasource name)",
    )
    parser.add_argument(
        "--uid-suffix",
        default="",
        help="Suffix like prod/infra or -prod/-infra (leading dash optional)",
    )
    parser.add_argument("--title-cluster", default="")
    args = parser.parse_args()

    dash = load(args.src)
    dash["id"] = None

    uid_suffix = str(args.uid_suffix or "").strip()
    if uid_suffix and not uid_suffix.startswith("-"):
        uid_suffix = f"-{uid_suffix}"

    ds_name = str(args.datasource or "").strip() or "OpenshiftProd"
    ds_uid = str(args.datasource_uid or "").strip() or ds_name

    if args.mode == "none":
        # Legacy placeholders only — do not clobber unrelated prometheus UIDs.
        rewrite_prometheus_ds(dash, pinned=ds_uid, all_prometheus=False)
        open(args.dest, "w", encoding="utf-8").write(json.dumps(dash, indent=2) + "\n")
        return 0

    if args.mode == "pin":
        apply_uid(dash, uid_suffix)
        apply_title(dash, args.title_cluster or "", "pin")
        # Contoller exports use opaque UIDs; remap all prometheus refs to pin target.
        rewrite_prometheus_ds(dash, pinned=ds_uid, all_prometheus=True)
        # no K8S dropdown in single-cluster folders
        templating = dash.setdefault("templating", {})
        templating["list"] = [v for v in templating.get("list", []) if v.get("name") != "datasource"]
    elif args.mode == "multi":
        apply_uid(dash, "")
        apply_title(dash, "", "multi")
        rewrite_prometheus_ds(dash, pinned=None, all_prometheus=True)
        ensure_k8s_var(dash, pinned=None, hide=0)

    open(args.dest, "w", encoding="utf-8").write(json.dumps(dash, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
