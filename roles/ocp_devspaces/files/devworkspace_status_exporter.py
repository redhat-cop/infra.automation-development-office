"""Expose DevWorkspace phase and VS Code extensions for Grafana.

Label names use dw_* so Prometheus scrape labels never collide with
workspace fields. Extensions are read from Running workspace pods
(/checode/remote/extensions) via pods/exec.
"""
from __future__ import annotations

import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

from kubernetes import client, config
from kubernetes.stream import stream

PORT = int(os.environ.get("METRICS_PORT", "8080"))
GROUP = "workspace.devfile.io"
VERSION = "v1alpha2"
PLURAL = "devworkspaces"
SCRAPE_EXTENSIONS = os.environ.get("DW_SCRAPE_EXTENSIONS", "true").lower() in (
    "1",
    "true",
    "yes",
)
EXTENSIONS_DIR = os.environ.get(
    "DW_EXTENSIONS_DIR", "/checode/remote/extensions"
)
TOOLING_CONTAINER = os.environ.get("DW_TOOLING_CONTAINER", "tooling-container")


def load_clients():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CustomObjectsApi(), client.CoreV1Api()


def sanitize(value: str, limit: int = 180) -> str:
    value = (value or "").replace("\n", " ").replace("\r", " ").strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = re.sub(r"[\x00-\x1f]", "", value)
    if len(value) > limit:
        value = value[: limit - 3] + "..."
    return value


def parse_extension_dirname(dirname: str) -> tuple[str, str, str]:
    """Parse publisher.name-version-target → (id, version, publisher)."""
    dirname = dirname.strip().rstrip("/")
    if not dirname or dirname == "extensions.json":
        return "", "", ""
    # e.g. redhat.ansible-25.12.3-universal
    m = re.match(
        r"^([a-zA-Z0-9-]+)\.([a-zA-Z0-9-]+)-([0-9][^/]*?)(?:-(universal|linux-x64|web))?$",
        dirname,
    )
    if m:
        publisher, name, version, _target = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"{publisher}.{name}", version, publisher
    return dirname, "", ""


def find_workspace_pod(core: client.CoreV1Api, namespace: str, wid: str) -> str | None:
    try:
        pods = core.list_namespaced_pod(namespace)
    except Exception:  # noqa: BLE001
        return None
    prefix = f"{wid}-"
    for pod in pods.items or []:
        name = pod.metadata.name or ""
        if name.startswith(prefix) or name.startswith("workspace") and wid in name:
            phase = (pod.status.phase if pod.status else None) or ""
            if phase == "Running":
                return name
    return None


def list_pod_extensions(
    core: client.CoreV1Api, namespace: str, pod: str
) -> list[tuple[str, str, str]]:
    """Return list of (ext_id, ext_version, ext_publisher)."""
    cmd = [
        "sh",
        "-c",
        f"ls -1 {EXTENSIONS_DIR} 2>/dev/null | grep -v '^extensions.json$' || true",
    ]
    try:
        out = stream(
            core.connect_get_namespaced_pod_exec,
            pod,
            namespace,
            command=cmd,
            container=TOOLING_CONTAINER,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
    except Exception:  # noqa: BLE001
        return []
    found: list[tuple[str, str, str]] = []
    for line in (out or "").splitlines():
        ext_id, version, publisher = parse_extension_dirname(line.strip())
        if ext_id:
            found.append(
                (
                    sanitize(ext_id, 120),
                    sanitize(version, 40),
                    sanitize(publisher, 63),
                )
            )
    return found


def collect(custom: client.CustomObjectsApi, core: client.CoreV1Api) -> list[str]:
    lines = [
        "# HELP devworkspace DevWorkspace inventory (1=present).",
        "# TYPE devworkspace gauge",
        "# HELP devworkspace_up DevWorkspace in Running phase (1=running).",
        "# TYPE devworkspace_up gauge",
        "# HELP devworkspace_vscode_extension Installed VS Code extension in Running workspace.",
        "# TYPE devworkspace_vscode_extension gauge",
        "# HELP scrape_ok Exporter scrape success.",
        "# TYPE scrape_ok gauge",
    ]
    try:
        obj = custom.list_cluster_custom_object(GROUP, VERSION, PLURAL)
        for item in obj.get("items") or []:
            md = item.get("metadata") or {}
            st = item.get("status") or {}
            ns = sanitize(md.get("namespace") or "", 63)
            name = sanitize(md.get("name") or "", 63)
            wid = sanitize(st.get("devworkspaceId") or name, 63)
            phase = sanitize(st.get("phase") or "Unknown", 32)
            reason = sanitize(st.get("message") or "", 220)
            labels = (
                f'dw_namespace="{ns}",dw_name="{name}",dw_id="{wid}",'
                f'dw_phase="{phase}",dw_reason="{reason}"'
            )
            lines.append(f"devworkspace{{{labels}}} 1")
            lines.append(
                f'devworkspace_up{{dw_namespace="{ns}",dw_name="{name}",dw_id="{wid}"}} '
                f'{1 if phase == "Running" else 0}'
            )
            if SCRAPE_EXTENSIONS and phase == "Running" and wid:
                pod = find_workspace_pod(core, ns, wid)
                if pod:
                    for ext_id, version, publisher in list_pod_extensions(
                        core, ns, pod
                    ):
                        lines.append(
                            "devworkspace_vscode_extension{"
                            f'dw_namespace="{ns}",dw_name="{name}",dw_id="{wid}",'
                            f'ext_id="{ext_id}",ext_version="{version}",'
                            f'ext_publisher="{publisher}"'
                            "} 1"
                        )
        lines.append("scrape_ok 1")
    except Exception as exc:  # noqa: BLE001
        lines.append(f'scrape_ok{{error="{sanitize(str(exc), 80)}"}} 0')
    return lines


class Handler(BaseHTTPRequestHandler):
    custom = None
    core = None

    def log_message(self, fmt, *args):
        return

    def do_GET(self):  # noqa: N802
        if self.path not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return
        body = ("\n".join(collect(self.custom, self.core)) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    custom, core = load_clients()
    Handler.custom = custom
    Handler.core = core
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
