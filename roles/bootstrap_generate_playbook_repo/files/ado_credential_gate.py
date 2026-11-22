"""ADO credential gate: refuse to commit or push real credentials to Git.

Scans what Git will actually record: every file in the index (tracked files and
newly staged files), using the staged content rather than the working tree.
It fails closed on:

* known credential file names (.vault_pass, .vault-pass, plaintext
  ado-preflight-*.json, ado-extra-vars.json, ...)
* private keys, cloud/SCM/OpenShift tokens and other high-confidence secrets
* literal values for password/token/secret keys in JSON, YAML and env-style files
* internal hostnames, domains, API endpoints and IP addresses in plaintext group_vars and configs
  (``plaintext-topology``; the ``repo`` profile only). Bootstrap routes them into
  Ansible Vault; see ``ado_topology.py`` and ``ado_topology_rules.py``.

It allows Ansible Vault ciphertext (``$ANSIBLE_VAULT``), templated or variable
references, and clearly synthetic values. Fixture files named ``*.fixture.json`` /
``*.fixture.yml`` may carry synthetic passwords; high-confidence secrets are still
rejected inside them. A path listed in ``.credential-gate-allow`` (one glob per line) is a
reviewed synthetic fixture and is exempt from content rules, but never from the rule
against credential file names such as ``.vault_pass``.

Findings name the file, the rule and the key. They never print a value.
The same rules are implemented for the Preflight pod in
ado-preflight-init-ui ``src/credentialGate.mjs``; keep the two in step.

Exit status: 0 clean, 3 findings, 2 usage or git error.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

EXIT_FINDINGS = 3
ALLOW_FILE = ".credential-gate-allow"
MAX_BYTES = 2 * 1024 * 1024

# File names that must never be tracked, whatever they contain.
FORBIDDEN_NAMES = (
    re.compile(r"^\.?vault[_-]?pass(word)?(\..+)?$", re.I),
    re.compile(r"^.+\.vault[_-]?pass$", re.I),
    re.compile(r"^ado-extra-vars\.json$", re.I),
    re.compile(r"^tmp-ado-preflight-.*\.json$", re.I),
    re.compile(r"^ado-preflight-.*\.json$", re.I),
    re.compile(r"^\.env(\..+)?$", re.I),
)
# A plaintext preflight export is allowed only when it is an explicit fixture.
FIXTURE_NAME = re.compile(r"\.fixture\.(json|ya?ml)$", re.I)
ENCRYPTED_PREFLIGHT = re.compile(r"\.json\.vault\.yml$", re.I)

# High-confidence secrets. These are rejected even inside approved fixtures.
TOKEN_PATTERNS = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("openshift-token", re.compile(r"\bsha256~[A-Za-z0-9_-]{40,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\b")),
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----(?P<body>[\s\S]*?)-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----"
)

# Keys whose value is a credential. No leading word boundary, so camelCase names such as
# ``userPassword`` and ``DATABASE_SECRET_KEY`` are caught. Bare ``secret`` is a Kubernetes
# object name, not a credential, so it is not listed.
SECRET_KEY = re.compile(
    r"(?:password|passwd|passphrase|token|api[_-]?key|private[_-]?key|client[_-]?secret"
    r"|secret[_-]?key|secret[_-]?access[_-]?key|bind[_-]?credential|bearer)s?$",
    re.I,
)
KEY_VALUE = re.compile(
    r"""^\s*(?:-\s+)?["']?(?P<key>[A-Za-z0-9_.-]+)["']?\s*[:=]\s*(?P<value>.*?)\s*,?\s*$"""
)

# Values that are references or empty, not literals.
REFERENCE_VALUE = re.compile(
    r"""^(?:
        \{\{.*\}\}|\$\{.*\}|\$\(.*\)|\$[A-Za-z_][A-Za-z0-9_]*|<[^>]*>|%[sd]|\[redacted\]|\*{3,}
        |!vault.*|lookup\(.*|vault_[A-Za-z0-9_]+
        |true|false|null|none|~|\|[-+]?|>[-+]?|always|on_create|on_change|never
    )$""",
    re.I | re.X,
)
# Well-known weak passwords (changeme, password123, ...) are NOT markers: they are real values
# someone would try first, so the gate treats them as credentials.
SYNTHETIC_VALUE = re.compile(
    r"""(?:^|[^a-z])(?:example|fake|dummy|placeholder|synthetic|sample|redacted
        |yourpassword|your-|molecule|not-secret)(?:$|[^a-z])
        |^x{3,}$|^0{6,}$|^1234(56)?$""",
    re.I | re.X,
)
ANSIBLE_VAULT_HEADER = "$ANSIBLE_VAULT"
# A token-shaped string that says it is fake is a regression fixture, not a credential.
SYNTHETIC_TOKEN = re.compile(r"fake|example|dummy|synthetic|regression|do-not|placeholder|not-secret|test", re.I)

# "repo": a generated bootstrap repository or a Preflight checkout. Everything in it is data,
#   so every literal password/token/secret value is a finding.
# "source": the ADO collection source. YAML there is mostly task code (``password: "{{ x }}"``,
#   embedded scripts), so literal values are only checked in JSON data files; file names,
#   private keys and token patterns are checked everywhere.
PROFILES = ("repo", "source")

# Documentation shows example commands; only high-confidence patterns apply there.
PROSE_SUFFIXES = (".md", ".rst", ".txt", ".adoc")
# Data formats hold credentials as literal key/value pairs. Source code (.py, .sh,
# .j2) assigns variables, which is not a stored credential.
STRUCTURED_SUFFIXES = (".json", ".yml", ".yaml", ".env", ".cfg", ".ini", ".conf", ".toml", ".properties")
# Test scenarios legitimately carry throw-away values ("test", "GOOD", "unused").
# There only a value that looks like a real generated secret is rejected.
TEST_ZONE = re.compile(r"(^|/)(tests?|molecule|fixtures?|examples?)(/|$)", re.I)


# Generated group_vars and configs hold environment topology. Internal hostnames and endpoints belong in
# Ansible Vault ciphertext there; a plaintext value is a finding in the "repo" profile.
TOPOLOGY_PATH = re.compile(r"(^|/)(group_vars|configs)/")
_TOPOLOGY_RULES = None


def topology_rules():
    """Load ``ado_topology_rules`` from beside this file (``.githooks/`` in a generated repo)."""
    global _TOPOLOGY_RULES
    if _TOPOLOGY_RULES is None:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        try:
            import ado_topology_rules  # noqa: PLC0415
        except ImportError as exc:  # fail closed: without the rules the gate cannot judge topology
            raise RuntimeError("ado_topology_rules.py is missing next to the credential gate") from exc
        _TOPOLOGY_RULES = ado_topology_rules
    return _TOPOLOGY_RULES


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def is_literal_secret(value: str) -> bool:
    """True when ``value`` looks like a real credential rather than a reference."""
    text = str(value).strip().strip("\"'").strip()
    if not text or len(text) < 4:
        return False
    if REFERENCE_VALUE.match(text):
        return False
    if "{{" in text or "${" in text:
        return False
    # An expression (``(x | default(y))``, ``lookup(...)``) is code, not a literal.
    if text.startswith("(") or re.search(r"\s\|\s|\w\(.*\)", text):
        return False
    if SYNTHETIC_VALUE.search(text):
        return False
    return True


def looks_real(value: str) -> bool:
    """High-entropy value: long, with upper case, lower case and digits."""
    text = str(value).strip().strip("\"'")
    return (
        len(text) >= 20
        and re.search(r"[A-Z]", text) is not None
        and re.search(r"[a-z]", text) is not None
        and re.search(r"[0-9]", text) is not None
    )


def load_allow(read_text) -> list[str]:
    raw = read_text(ALLOW_FILE)
    if not raw:
        return []
    return [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def allowed_by_list(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, glob) for glob in globs)


def walk_json(node, trail=""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else str(key)
            if isinstance(value, (dict, list)):
                yield from walk_json(value, here)
            else:
                yield here, str(key), value
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk_json(value, f"{trail}[{index}]")


def scan_text(path: str, text: str, fixture: bool, profile: str = "repo") -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    if text.lstrip().startswith(ANSIBLE_VAULT_HEADER):
        return findings

    for rule, pattern in TOKEN_PATTERNS:
        if any(not SYNTHETIC_TOKEN.search(match.group(0)) for match in pattern.finditer(text)):
            findings.append((path, rule, "token pattern"))

    for match in PRIVATE_KEY.finditer(text):
        body = match.group("body")
        # A real key body is hundreds of characters; a few characters is a test string.
        if len(re.sub(r"\s", "", body)) >= 64 and not re.search(r"fake|example|synthetic|placeholder|dummy", body, re.I):
            findings.append((path, "private-key", "private key block"))

    lowered = path.lower()
    if fixture or lowered.endswith(PROSE_SUFFIXES):
        return findings
    if not lowered.endswith(STRUCTURED_SUFFIXES):
        return findings
    in_test_zone = TEST_ZONE.search(lowered) is not None
    topology_scope = TOPOLOGY_PATH.search(lowered)
    # Only a test directory *above* group_vars/configs exempts a file. An environment that is
    # itself named ``test``, ``molecule`` or ``examples`` (group_vars/all/<env>/) is a real
    # environment and is not exempt.
    topology_exempt = bool(topology_scope) and TEST_ZONE.search(lowered[: topology_scope.start() + 1]) is not None
    if profile == "repo" and topology_scope and lowered.endswith((".yml", ".yaml")) and not topology_exempt:
        for line_number, key in topology_rules().scan_yaml_topology(text):
            findings.append((path, "plaintext-topology", f"{key} line {line_number}"))
    if profile == "source" and not lowered.endswith(".json"):
        return findings

    def is_secret(value) -> bool:
        if not is_literal_secret(value):
            return False
        return looks_real(value) if in_test_zone else True

    if lowered.endswith(".json"):
        try:
            document = json.loads(text)
        except ValueError:
            document = None
        if document is not None:
            for trail, key, value in walk_json(document):
                if SECRET_KEY.search(key) and isinstance(value, str) and is_secret(value):
                    findings.append((path, "literal-secret", f"{trail} (length {len(value.strip())})"))
            return findings

    for line_number, line in enumerate(text.splitlines(), 1):
        match = KEY_VALUE.match(line)
        if not match:
            continue
        key, value = match.group("key"), match.group("value")
        if SECRET_KEY.search(key) and is_secret(value):
            findings.append((path, "literal-secret", f"{key} line {line_number}"))
    return findings


# Dependency lock files list package names such as "react-tokens"; they hold no credentials.
LOCKFILES = re.compile(r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.ya?ml|poetry\.lock|Pipfile\.lock|Cargo\.lock|go\.sum)$")


def scan_entries(entries, read_blob, allow_globs=None, profile="repo"):
    """Scan ``(path, blob_id)`` pairs. ``read_blob`` returns bytes or None."""
    allow_globs = allow_globs or []
    findings: list[tuple[str, str, str]] = []
    for path, blob in entries:
        name = basename(path)
        if LOCKFILES.search(path):
            continue
        approved = allowed_by_list(path, allow_globs)
        fixture = bool(FIXTURE_NAME.search(name))
        forbidden = next((rule for rule in FORBIDDEN_NAMES if rule.match(name)), None)
        if forbidden and not ENCRYPTED_PREFLIGHT.search(name) and not ((fixture or approved) and name.lower().startswith("ado-preflight-")):
            findings.append((path, "forbidden-file", "credential file name"))
            continue
        if approved:
            continue  # a person listed this file in .credential-gate-allow as a synthetic fixture
        data = read_blob(blob)
        if data is None or len(data) > MAX_BYTES or b"\x00" in data[:4096]:
            continue
        findings.extend(scan_text(path, data.decode("utf-8", "replace"), fixture, profile))
    return findings


def git(repo: str, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(["git", *args], cwd=repo, input=data, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


def index_entries(repo: str):
    raw = git(repo, "ls-files", "-z", "--stage")
    entries = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, _sep, path = record.partition(b"\t")
        mode, blob, _stage = meta.decode().split()
        if mode == "160000":  # submodule
            continue
        entries.append((path.decode("utf-8", "replace"), blob))
    return entries


def tree_entries(repo: str, rev: str):
    """Files recorded by a commit (what a push would publish)."""
    raw = git(repo, "ls-tree", "-r", "-z", rev)
    entries = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, _sep, path = record.partition(b"\t")
        _mode, kind, blob = meta.decode().split()
        if kind == "blob":
            entries.append((path.decode("utf-8", "replace"), blob))
    return entries


def blob_reader(repo: str):
    cache: dict[str, bytes | None] = {}

    def read(blob: str):
        if blob not in cache:
            try:
                cache[blob] = git(repo, "cat-file", "blob", blob)
            except RuntimeError:
                cache[blob] = None
        return cache[blob]

    return read


def scan_repo(repo: str, profile: str = "repo", rev: str | None = None):
    read = blob_reader(repo)
    entries = tree_entries(repo, rev) if rev else index_entries(repo)
    allow_blob = next((blob for path, blob in entries if path == ALLOW_FILE), None)
    allow_text = (read(allow_blob) or b"").decode("utf-8", "replace") if allow_blob else ""
    allow = [l.strip() for l in allow_text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return scan_entries(entries, read, allow, profile)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--repo", default=".", help="Git working tree to scan (default: .)")
    parser.add_argument("--profile", choices=PROFILES, default="repo", help="repo (default, strict) or source (ADO collection)")
    parser.add_argument("--rev", action="append", default=[], help="scan this commit's tree instead of the index (repeatable; used by pre-push)")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args(argv)
    repo = os.path.abspath(args.repo)
    try:
        findings = []
        for rev in args.rev or [None]:
            findings.extend(scan_repo(repo, args.profile, rev))
    except (RuntimeError, OSError) as exc:
        print(f"credential gate could not read the repository: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([{"path": p, "rule": r, "detail": d} for p, r, d in findings], indent=2))
    elif findings:
        print("CREDENTIAL GATE: refusing to commit or push. Real credentials must not enter Git.", file=sys.stderr)
        for path, rule, detail in findings:
            print(f"  {path}: {rule}: {detail}", file=sys.stderr)
        print("Remove these files from the index (git rm --cached), keep secrets in Ansible Vault or the runtime, "
              "and list synthetic fixtures in .credential-gate-allow.", file=sys.stderr)
        if any(rule == "plaintext-topology" for _p, rule, _d in findings):
            print("plaintext-topology: internal hostnames and endpoints must be Vault-encrypted. Re-run Bootstrap with "
                  "vault encryption on (it routes them into the vault files), or run ado_topology.py migrate.", file=sys.stderr)
    else:
        print("credential gate: no credential files or literal secrets in the index")
    return EXIT_FINDINGS if findings else 0


if __name__ == "__main__":
    sys.exit(main())
