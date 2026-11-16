"""Local-only mock of the Keycloak admin endpoints used by ``ocp_oidc_auth``.

Serves HTTPS (self-signed) on 127.0.0.1 and records every request, so the
scenario can prove the role only reads. Behaviour is chosen by user and client:

* user ``kcadmin`` with password ``GOOD``: login works, full permissions
* user ``noperm``  with password ``GOOD``: login works, admin API returns 403
* user ``restonly`` with password ``GOOD``: same rights as ``kcadmin``, but the first
  token request is refused. The role's module path fails on that login, so the REST
  fallback (second login) is the one that has to trust the certificate
* any other login: 401 on the token endpoint
* client ``existing-confidential``: exists and has a secret
* client ``existing-public``: exists, the secret endpoint returns no value
* any other client ID: not found
* realm ``corp`` exists; any other realm returns 404 Realm not found
"""

import json
import os
import ssl
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(sys.argv[1])
WORK = sys.argv[2]
LOG = open(f"{WORK}/requests.log", "a", encoding="utf-8")
LOGINS = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        form = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
        user = (form.get("username") or [""])[0]
        password = (form.get("password") or [""])[0]
        LOG.write(f"POST {urlparse(self.path).path}\n")
        LOG.flush()
        LOGINS[user] = LOGINS.get(user, 0) + 1
        if user == "restonly" and password == "GOOD":
            if LOGINS[user] == 1:
                return self._send(401, {"error": "invalid_grant"})
            return self._send(200, {"access_token": "tok-kcadmin", "expires_in": 60})
        if user in ("kcadmin", "noperm") and password == "GOOD":
            return self._send(200, {"access_token": f"tok-{user}", "expires_in": 60})
        return self._send(401, {"error": "invalid_grant"})

    def do_GET(self):
        url = urlparse(self.path)
        auth = self.headers.get("Authorization", "")
        LOG.write(f"GET {url.path}\n")
        LOG.flush()
        if auth == "Bearer tok-noperm":
            return self._send(403, {"error": "HTTP 403 Forbidden"})
        if auth != "Bearer tok-kcadmin":
            return self._send(401, {"error": "HTTP 401 Unauthorized"})
        parts = url.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "admin" and parts[1] == "realms" and parts[2] != "corp":
            return self._send(404, {"error": "Realm not found."})
        if len(parts) == 3 and parts[0] == "admin" and parts[1] == "realms":
            return self._send(200, {"realm": parts[2]})
        if parts[-1] == "clients":
            client = (parse_qs(url.query).get("clientId") or [""])[0]
            if client.startswith("existing-"):
                return self._send(200, [{"id": f"uuid-{client}", "clientId": client}])
            return self._send(200, [])
        if parts[-1] == "client-secret":
            if parts[-2] == "uuid-existing-confidential":
                return self._send(200, {"type": "secret", "value": "MOCK-SECRET"})
            return self._send(200, {})
        return self._send(404, {"error": "not found"})


server = HTTPServer(("127.0.0.1", PORT), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(f"{WORK}/cert.pem", f"{WORK}/key.pem")
server.socket = context.wrap_socket(server.socket, server_side=True)
with open(f"{WORK}/mock.pid", "w", encoding="utf-8") as handle:
    handle.write(str(os.getpid()))
server.serve_forever()
