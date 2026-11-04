#!/usr/bin/env python3
"""Serve a Prometheus textfile on :8080/metrics (from METRICS_FILE)."""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

METRICS_FILE = os.environ.get("METRICS_FILE", "/metrics/cve_ns.prom")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8080") or "8080")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return
        body = Path(METRICS_FILE).read_bytes() if Path(METRICS_FILE).is_file() else b""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # noqa: A003
        return


if __name__ == "__main__":
    ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler).serve_forever()
