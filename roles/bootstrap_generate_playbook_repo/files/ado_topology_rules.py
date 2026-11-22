"""What counts as internal infrastructure topology, without any dependency.

Shared by ``ado_topology.py`` (routes the values into Ansible Vault when bootstrap
generates group_vars) and ``ado_credential_gate.py`` (refuses to commit or push them
in plaintext). Pure standard library, because the gate also runs inside generated
bootstrap repositories on a workstation or in the Preflight pod, where PyYAML may
not be installed.

Internal hostnames, domains, API endpoints, SMTP relays, IP addresses and LDAP base
DNs show how an environment is built. They are not passwords, but they do not belong
in a plaintext Git repository.

The Preflight pod keeps a JavaScript port in ``src/topologyRules.mjs``; keep the two
in step. Detection never returns or prints a value.
"""

from __future__ import annotations

import ipaddress
import re

REF_PREFIX = "vault_topology_"
REF_RE = re.compile(r"^\{\{\s*(" + REF_PREFIX + r"[A-Za-z0-9_]+)\s*\}\}$")

# Key words that mean "this value names a place on the network".
KEY_TOKENS = frozenset(
    {
        "host", "hosts", "hostname", "hostnames", "fqdn", "fqdns", "domain", "domains",
        "server", "servers", "address", "addresses", "addr", "ip", "ips", "url", "urls",
        "uri", "uris", "endpoint", "endpoints", "issuer", "relay", "gateway", "nameserver",
        "nameservers", "dns", "cidr", "registry", "registries", "proxy", "mirror",
    }
)

URL_SCHEMES = (
    "http", "https", "ldap", "ldaps", "smtp", "smtps", "tcp", "ssh", "git", "redis", "rediss", "postgres",
    "postgresql", "mysql", "mongodb", "amqp", "amqps", "kafka", "nfs", "wss", "ws", "ftp", "sftp",
)
URL_RE = re.compile(
    r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?:[^/@\s]+@)?(?P<host>\[[0-9A-Fa-f:]+\]|[^/:?#\s]+)(?::\d+)?(?:[/?#]\S*)?$"
)
HOSTNAME_RE = re.compile(
    r"^(?=.{4,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?::\d{1,5})?$"
)
LDAP_DN_RE = re.compile(r"^(?:[A-Za-z]+=[^,]+,\s*)*dc=[^,]+(?:,\s*dc=[^,]+)+$", re.I)
IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?(?::\d{1,5})?$")

# Hosts that are neither private nor environment specific. They stay readable.
PUBLIC_SUFFIXES = (
    "redhat.com", "redhat.io", "openshift.com", "ansible.com", "quay.io", "docker.io",
    "github.com", "githubusercontent.com", "gitlab.com", "k8s.io", "kubernetes.io", "pypi.org",
)
# Reserved or generic names that carry no topology (RFC 2606 / 6761, Kubernetes in-cluster DNS).
PLACEHOLDER_SUFFIXES = (
    "example.com", "example.org", "example.net", "example.edu", "example.internal",
    ".example", ".test", ".invalid", ".localhost", ".svc", ".svc.cluster.local", ".cluster.local",
)
PLACEHOLDER_HOSTS = ("localhost", "localhost.localdomain")
# Ansible module and role names have the same shape as a host name (ansible.builtin.copy).
COLLECTION_NAMESPACES = frozenset({"ansible", "infra", "redhat", "community", "kubernetes", "containers", "amazon", "awx"})
COLLECTION_NAMES = frozenset(
    {"builtin", "posix", "utils", "netcommon", "windows", "controller", "hub", "eda", "platform", "general", "crypto",
     "docker", "podman", "core", "k8s", "openshift", "operator", "satellite", "aws", "cloud", "rhel", "ocp"}
)
# A dotted name ending in a file extension is a file name, not a host (release.yml, ca.crt).
FILE_EXTENSIONS = frozenset(
    {"yml", "yaml", "json", "txt", "conf", "cfg", "ini", "toml", "py", "sh", "j2", "jinja", "crt", "pem", "key",
     "cer", "csr", "md", "xml", "csv", "log", "tar", "gz", "tgz", "zip", "html", "js", "css", "rpm", "iso", "qcow2",
     "img", "sql", "service", "repo", "env", "pub", "p12", "jks", "der"}
)


def host_of(value: str) -> str:
    """Host part of ``value`` (URL or host[:port]), lower case, without brackets."""
    text = str(value).strip()
    match = URL_RE.match(text)
    host = match.group("host") if match else text
    if host.startswith("["):
        return host.strip("[]").lower()
    host = host.split(":", 1)[0] if host.count(":") == 1 else host
    return host.lower().rstrip(".")


def _in_suffixes(host: str, suffixes) -> bool:
    for suffix in suffixes:
        bare = suffix.lstrip(".")
        if host == bare or host.endswith("." + bare):
            return True
    return False


def is_placeholder_host(host: str) -> bool:
    if host in PLACEHOLDER_HOSTS or _in_suffixes(host, PLACEHOLDER_SUFFIXES):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def is_public_host(host: str) -> bool:
    return _in_suffixes(host, PUBLIC_SUFFIXES)


def key_words(key) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return {part for part in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if part}


def key_hints_topology(key) -> bool:
    return bool(key_words(key) & KEY_TOKENS)


def valid_ipv4(text: str) -> bool:
    core = text.split("/", 1)[0].split(":", 1)[0]
    try:
        ipaddress.IPv4Address(core)
    except ValueError:
        return False
    return True


def _ip_sequence(text: str) -> bool:
    """``10.0.0.1-10.0.0.9``, ``10.0.0.100-200`` or ``10.0.0.1, 10.0.0.2``: a range or list of addresses."""
    parts = [part for part in re.split(r"\s*[-,;]\s*|\s+", text) if part]
    if len(parts) < 2:
        return False
    addresses = [part for part in parts if "." in part]
    if not addresses or not all(valid_ipv4(part) and IPV4_RE.match(part) for part in addresses):
        return False
    if not all("." in part or re.fullmatch(r"\d{1,3}", part) for part in parts):
        return False
    return not all(is_placeholder_host(host_of(part)) for part in addresses)


def _host_list(text: str) -> bool:
    """``dns1.corp.example.net, dns2.corp.example.net``: a list of host names (host-like keys only)."""
    parts = [part for part in re.split(r"\s*[,;]\s*|\s+", text) if part]
    if len(parts) < 2 or not all(HOSTNAME_RE.match(part) for part in parts):
        return False
    return any(not is_placeholder_host(host_of(part)) and not is_public_host(host_of(part)) for part in parts)


def is_topology_value(value, key_hint: bool = False) -> bool:
    """True when ``value`` names internal infrastructure and belongs in Vault.

    URLs, IPv4 addresses and LDAP base DNs qualify under any key. A bare dotted
    host name qualifies only under a key that names a host, so module names such
    as ``ansible.builtin.copy`` and file names are never mistaken for hosts.
    References and templated values (``{{ ... }}``) are never routed again.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) > 2048 or "{{" in text or "{%" in text or "\n" in text:
        return False
    if LDAP_DN_RE.match(text):
        return not is_placeholder_host(text.lower().replace("dc=", "").replace(",", "."))
    url = URL_RE.match(text)
    if url and url.group("scheme").lower() in URL_SCHEMES:
        host = host_of(text)
        return bool(host) and not is_placeholder_host(host) and not is_public_host(host)
    if IPV4_RE.match(text) and valid_ipv4(text):
        return not is_placeholder_host(host_of(text))
    if _ip_sequence(text):
        return True
    if key_hint and _host_list(text):
        return True
    if key_hint and HOSTNAME_RE.match(text):
        host = host_of(text)
        labels = host.split(".")
        if labels[-1] in FILE_EXTENSIONS:
            return False
        if len(labels) == 3 and labels[0] in COLLECTION_NAMESPACES and labels[1] in COLLECTION_NAMES:
            return False
        return not is_placeholder_host(host) and not is_public_host(host)
    return False


# ----------------------------------------------------------------------------- plaintext scan


_KEY_LINE = re.compile(r"""^(?P<indent>\s*)(?P<dash>-\s+)?["']?(?P<key>[A-Za-z0-9_.-]+)["']?\s*:(?:\s+(?P<value>.*?))?\s*$""")
_ITEM_LINE = re.compile(r"^(?P<indent>\s*)-\s+(?P<value>.*?)\s*$")


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1]
    return text


def scan_yaml_topology(text: str) -> list[tuple[int, str]]:
    """Plaintext topology values in YAML ``text`` as ``(line number, key)``; values are never returned.

    A line-based reading of what ``ado_topology.py`` finds with a YAML parse: a scalar is topology
    when ``is_topology_value`` says so, with a host-like key (or ancestor key) as the hint.
    """
    found: list[tuple[int, str]] = []
    ancestors: list[tuple[int, str]] = []  # (indent of the key, key) for keys that open a block
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped in ("---", "..."):
            continue
        key_match = _KEY_LINE.match(line)
        if key_match:
            indent = len(key_match.group("indent")) + (len(key_match.group("dash")) if key_match.group("dash") else 0)
            key = key_match.group("key")
            while ancestors and ancestors[-1][0] >= indent:
                ancestors.pop()
            value = key_match.group("value")
            if value is None or value == "":
                ancestors.append((indent, key))
                continue
            if value[0] in "|>[{&*!":
                continue
            hint = key_hints_topology(key) or any(key_hints_topology(name) for _i, name in ancestors)
            if is_topology_value(_unquote(value), hint):
                found.append((number, key))
            continue
        item = _ITEM_LINE.match(line)
        if item:
            indent = len(item.group("indent"))
            while ancestors and ancestors[-1][0] > indent:
                ancestors.pop()
            value = item.group("value")
            if not value or value[0] in "|>[{&*!":
                continue
            hint = any(key_hints_topology(name) for _i, name in ancestors)
            if is_topology_value(_unquote(value), hint):
                found.append((number, ancestors[-1][1] if ancestors else "-"))
    return found
