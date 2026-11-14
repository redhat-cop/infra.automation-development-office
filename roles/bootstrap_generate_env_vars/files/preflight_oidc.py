"""Shared OIDC checks for preflight JSON (UI and CLI use the same rules).

Imported by ``overlay_preflight_component_values.py`` and run on its own, before
any component vars are generated, by the ``bootstrap_generate_env_vars`` role::

    ADO_PREFLIGHT_JSON=ado-preflight-<env>.json \\
    ADO_SELECTED_COMPONENTS='["openshift", ...]' python3 preflight_oidc.py

It mirrors ``ado-preflight-ui/src/rhbkClients.mjs`` so the UI is not the only
protection: a JSON file that bypasses the form is checked the same way.

Two OpenShift OIDC modes (``openshift.oauth_rhbk``):

* RHBK in this run: hostname, realm and admin credentials are inherited from the
  RHBK component. Leftover ``openshift.oauth_rhbk`` connection overrides are
  ignored so they cannot point OAuth at a different Keycloak.
* Existing / external Keycloak (RHBK not in this run): hostname, realm, client ID,
  admin user and admin password must all be set in ``openshift.oauth_rhbk``.

Neither mode creates or changes a Keycloak client. The ``ocp_oidc_auth`` role only
reads the client secret; the client must already exist in the realm. Client-only
and other existing-Keycloak RHBK operations still require
``component_config.rhbk.realm``; overlay does not invent ``Dev`` or ``rhlab``.

Rows in ``component_config.rhbk.clients`` may set ``create_client`` (default yes
when omitted). Only managed rows are copied into generated ``rhbk_clients`` for
``ADO | Deploy RHBK Client``, except:

* the MinIO OIDC client: ``ocp_minio`` provisions that client (and its policy
  mapper) so the shared workflow cannot double-create it;
* GitLab Keycloak clients: no GitLab OIDC role exists, so selecting GitLab must
  not put a client in ``rhbk_clients``. Existing rows stay in the preflight
  list and are not deleted;
* Grafana Keycloak clients when Grafana OIDC is explicitly disabled
  (``grafana.oidc.enabled: false``): the row stays in the preflight list and
  is not deleted, but it is omitted from ``rhbk_clients``. When Grafana OIDC
  is on and RHBK is in the run, the issuer is inherited from the same RHBK
  hostname/realm as Client/OAuth. Overlay does not invent ``Dev`` or ``rhlab``.

``create_client: false`` means ADO must not mutate that Keycloak client at all,
including mappers. Application OIDC configuration is independent of that flag.
Retrieving an existing client's secret (read-only) is allowed for unmanaged
clients. Satellite ``oidc.create_client`` and AAP Gateway OIDC are separate.
"""

from __future__ import annotations

import functools
import json
import os
import re
import sys
from pathlib import Path

MAPPING_METHODS = ("claim", "lookup", "add")
RHBK_EXISTING_CONNECTION_OPTIONS = (
    "client",
    "realm",
    "idp",
    "federation",
    "group_mapper",
    "client_scopes",
    "client_mappers",
)
_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?(:\d{1,5})?$")
CREATE_CLIENT_FALSE = ("0", "false", "no", "n", "off")
RHBK_EXISTING_REALM_MESSAGE = (
    "RHBK Client (and other existing-Keycloak operations) need "
    "component_config.rhbk.realm set to the existing realm name. "
    "Realm creation being unselected does not remove this field."
)
KEYCLOAK_HOSTNAME_SCHEME_MESSAGE = (
    "OpenShift OIDC: Keycloak hostname must be the route host only. "
    "Remove http:// or https:// (for example keycloak.example.com)."
)
KEYCLOAK_HOSTNAME_PATH_MESSAGE = (
    "OpenShift OIDC: Keycloak hostname must be the route host only. "
    "Remove any trailing / or path (for example keycloak.example.com)."
)


def text(value):
    return "" if value is None else str(value).strip()


def rhbk_client_is_managed(client):
    """True when ADO should create/update this Keycloak client.

    ``component_config.rhbk.clients[].create_client`` defaults to yes when the
    field is missing, null or blank so existing exports keep the automated
    install path. Explicit false / no / off / 0 means use an existing client:
    keep the row and app OIDC config, but do not put the id in ``rhbk_clients``.
    Mirrored by ``rhbkClientIsManaged`` in ado-preflight-ui ``rhbkClients.mjs``.
    """
    if not isinstance(client, dict):
        return True
    raw = client.get("create_client")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    if isinstance(raw, int):
        if raw == 1:
            return True
        if raw == 0:
            return False
        return True
    token = str(raw).strip().lower()
    if token == "":
        return True
    return token not in CREATE_CLIENT_FALSE


def first_text(*values):
    for value in values:
        if text(value):
            return text(value)
    return ""


def normalize_host(value):
    host = re.sub(r"^https?://", "", text(value), flags=re.I)
    return re.sub(r"/.*$", "", host).strip()


def hostname_has_scheme(value):
    return bool(re.match(r"^https?://", text(value).strip(), flags=re.I))


def component_config(preflight, key):
    cfg = (preflight.get("component_config") or {}).get(key)
    return cfg if isinstance(cfg, dict) else {}


def component_options(preflight, key):
    options = (preflight.get("component_options") or {}).get(key)
    return options if isinstance(options, list) else []


def oauth_config(preflight):
    cfg = (preflight.get("openshift") or {}).get("oauth_rhbk")
    return cfg if isinstance(cfg, dict) else {}


def rhbk_selected_in_preflight(preflight):
    components = {text(x).lower() for x in (preflight.get("components") or [])}
    apps = {
        text(x).lower() for x in ((preflight.get("component_apps") or {}).get("openshift") or [])
    }
    return "rhbk" in components or "rhbk" in apps or "all" in components


def is_selected(preflight, selected, key):
    if key == "rhbk":
        return "rhbk" in selected or rhbk_selected_in_preflight(preflight)
    return key in selected


def openshift_oidc_requested(preflight, selected):
    """True when the form asked for OpenShift OAuth against Keycloak/RHBK."""
    return "oauth_rhbk" in component_options(preflight, "openshift") and is_selected(
        preflight, selected, "openshift"
    )


def resolve_openshift_oidc_client_id(preflight, rhbk_config=None):
    """Return the OpenShift OIDC client id, or "" when none is configured.

    Only an explicit OpenShift client counts: openshift.oauth_rhbk.client_id,
    then component_config.rhbk.openshift_oidc_client_id, then an
    OpenShift-specific row in rhbk.clients (source "openshift" or an id that
    starts with "openshift"). The legacy single-client field ``client`` is the
    first row of the list and must never be used here: it can be Grafana's.
    """
    rhbk_config = rhbk_config if rhbk_config is not None else component_config(preflight, "rhbk")
    oauth = oauth_config(preflight)
    explicit = first_text(
        oauth.get("client_id"),
        oauth.get("keycloak_client_id"),
        rhbk_config.get("openshift_oidc_client_id"),
    )
    if explicit:
        return explicit
    for client in rhbk_config.get("clients") or []:
        if not isinstance(client, dict):
            continue
        client_id = first_text(client.get("id"), client.get("client_id"))
        if not client_id:
            continue
        source = text(client.get("source")).lower()
        if source == "openshift" or client_id.lower().startswith("openshift"):
            return client_id
    return ""


def openshift_oidc_client_missing_message():
    return (
        "OpenShift OIDC (openshift.oauth_rhbk) is selected but no OpenShift "
        "client ID is configured. Set openshift.oauth_rhbk.client_id (or "
        "component_config.rhbk.openshift_oidc_client_id), or add an "
        "OpenShift-specific client (id starting with 'openshift') to "
        "component_config.rhbk.clients. The first Keycloak client "
        "(component_config.rhbk.client) is intentionally not used."
    )


# ---------------------------------------------------------------------------
# Client references of active OIDC integrations
# ---------------------------------------------------------------------------


def _grafana_oidc(preflight):
    oidc = component_config(preflight, "grafana").get("oidc")
    return oidc if isinstance(oidc, dict) else {}


# Where each component keeps its default OIDC client ID inside
# ``components_defaults.yml`` (``components_defaults.<component>.<path>``). Only the
# *location* is declared here; the values are read from that file, which is the one
# place the framework's default client names live. A blank client ID in the preflight
# means "that default client". OpenShift and GitLab have no default: OpenShift never
# guesses which client OAuth uses, and GitLab OIDC is not consumed by any role, so
# both need an explicit client ID.
DEFAULT_CLIENT_ID_PATHS = {
    "grafana": ("oidc", "client_id"),
    "bookstack": ("bookstack_oidc_client_id",),
    "netbox": ("netbox_oidc_client_id",),
    "quay": ("quay_oidc_client_id",),
    "minio": ("minio_oidc_client_id",),
    "dev_hub": ("dev_hub_keycloak_client_id",),
}
COMPONENTS_DEFAULTS_ENV = "ADO_COMPONENTS_DEFAULTS"


def components_defaults_path():
    override = os.environ.get(COMPONENTS_DEFAULTS_ENV)
    if override:
        return Path(override)
    roles = Path(__file__).resolve().parents[2]
    return roles / "bootstrap_resolve_component" / "files" / "components_defaults.yml"


@functools.lru_cache(maxsize=None)
def _load_default_client_ids(path):
    import yaml  # PyYAML ships with Ansible; imported lazily so --help style use is cheap

    with open(path, encoding="utf-8") as handle:
        defaults = (yaml.safe_load(handle) or {}).get("components_defaults") or {}
    found = {}
    for component, keys in DEFAULT_CLIENT_ID_PATHS.items():
        node = defaults.get(component)
        for key in keys:
            node = node.get(key) if isinstance(node, dict) else None
        client_id = text(node)
        if not client_id or "{{" in client_id:
            raise SystemExit(
                f"{path}: components_defaults.{component}.{'.'.join(keys)} must be a literal "
                "client ID; the OIDC validators resolve a blank client ID to it."
            )
        found[component] = client_id
    return found


def load_default_client_ids():
    """Default OIDC client ID per component, read from ``components_defaults.yml``."""
    return dict(_load_default_client_ids(str(components_defaults_path())))


def resolve_minio_oidc_client_id_from_config(cfg):
    """Canonical MinIO client ID: ``oidc_client_id``, then nested ``oidc.client_id``.

    The Preflight form, presets and validator use ``oidc_client_id``. Nested
    ``oidc.client_id`` is accepted so older JSON still generates ``minio_oidc_client_id``.
    When both are set and differ, the top-level UI field wins. The first Keycloak
    client row is never used.
    """
    cfg = cfg if isinstance(cfg, dict) else {}
    nested = cfg.get("oidc") if isinstance(cfg.get("oidc"), dict) else {}
    canonical = text(cfg.get("oidc_client_id"))
    if canonical:
        return canonical
    return text(nested.get("client_id"))


def resolve_minio_oidc_client_id(preflight):
    return resolve_minio_oidc_client_id_from_config(component_config(preflight, "minio"))


def resolve_dev_hub_keycloak_client_id_from_config(cfg):
    """Canonical Developer Hub client ID: ``keycloak_client_id``.

    ``oidc_client_id`` is a pre-Phase-2 preset leftover. It is used only when
    ``keycloak_client_id`` is blank, or when the form still has the framework
    default and ``oidc_client_id`` is a different custom value (old exports).
    When both are set to different non-default values, ``keycloak_client_id`` wins.
    """
    cfg = cfg if isinstance(cfg, dict) else {}
    canonical = text(cfg.get("keycloak_client_id"))
    legacy = text(cfg.get("oidc_client_id"))
    default = load_default_client_ids().get("dev_hub", "rhdh")
    if canonical and legacy and canonical != legacy:
        if canonical == default and legacy != default:
            return legacy
        return canonical
    return canonical or legacy


def resolve_dev_hub_keycloak_client_id(preflight):
    return resolve_dev_hub_keycloak_client_id_from_config(
        component_config(preflight, "dev_hub")
    )


def matching_rhbk_client_row(preflight, client_id):
    """First ``rhbk.clients`` row whose id matches ``client_id``."""
    wanted = text(client_id)
    if not wanted:
        return None
    for row in component_config(preflight, "rhbk").get("clients") or []:
        if not isinstance(row, dict):
            continue
        if first_text(row.get("id"), row.get("client_id")) == wanted:
            return row
    return None


def minio_effective_client_id(preflight, minio_cfg=None):
    cfg = minio_cfg if isinstance(minio_cfg, dict) else component_config(preflight, "minio")
    return resolve_minio_oidc_client_id_from_config(cfg) or load_default_client_ids().get(
        "minio", "minio"
    )


def minio_keycloak_is_managed(preflight, minio_cfg=None):
    """Whether ADO may create/update the MinIO Keycloak client and mapper.

    A matching ``rhbk.clients`` row is the source of truth (Phase 1
    ``create_client``). Otherwise ``minio_oidc_create_keycloak_client`` on the
    MinIO config is honored. Missing ownership still means managed.
    Mirrored by ``ocp_minio`` ``configure-keycloak-oidc.yml``.
    """
    cfg = minio_cfg if isinstance(minio_cfg, dict) else component_config(preflight, "minio")
    client_id = minio_effective_client_id(preflight, cfg)
    row = matching_rhbk_client_row(preflight, client_id)
    if row is not None:
        return rhbk_client_is_managed(row)
    if "minio_oidc_create_keycloak_client" in cfg:
        return rhbk_client_is_managed(
            {"create_client": cfg.get("minio_oidc_create_keycloak_client")}
        )
    if "create_client" in cfg:
        return rhbk_client_is_managed(cfg)
    return True


def minio_role_owns_keycloak_client_id(preflight, selected, client_id):
    """True when ``ocp_minio`` — not Deploy RHBK Client — provisions this id."""
    selected = {text(item).lower() for item in (selected or [])}
    if "minio" not in selected:
        return False
    wanted = text(client_id)
    return bool(wanted) and wanted == minio_effective_client_id(preflight)


def gitlab_keycloak_client_should_not_be_provisioned(
    preflight, selected, client_id, row=None
):
    """True when Deploy RHBK Client must not create or update this GitLab client.

    GitLab has no OIDC configuration role. Existing Keycloak clients and
    preflight rows are left in place; they are only omitted from generated
    ``rhbk_clients``. Rows with ``source: gitlab`` are always skipped. When
    GitLab is selected, the historical default id ``gitlab`` and
    ``component_config.gitlab.oidc_client_id`` are skipped as well.
    """
    if isinstance(row, dict) and text(row.get("source")).lower() == "gitlab":
        return True
    wanted = text(client_id)
    if not wanted:
        return False
    selected_l = {text(item).lower() for item in (selected or [])}
    if "gitlab" not in selected_l:
        return False
    gitlab_id = text(component_config(preflight, "gitlab").get("oidc_client_id"))
    if gitlab_id:
        return wanted == gitlab_id
    return wanted.lower() == "gitlab"


OPENSHIFT_OIDC_DEFAULT_IDP_NAME = "Keycloak"
# claim fails with "Could not create user" when that OpenShift username already
# exists from another IdP (htpasswd admin). add matches ocp_htpasswd_admin.
OPENSHIFT_OIDC_DEFAULT_MAPPING_METHOD = "add"
# OpenShift oauth-server redirects to this exact path (no extra segment):
# https://oauth-openshift.<apps_domain>/oauth2callback/<idp_name>
# A trailing /* does not match that URL in Keycloak.
_OPENSHIFT_OAUTH_CALLBACK_RE = re.compile(
    r"^https://oauth-openshift\.[^/]+/oauth2callback/[^/]+(?:/[*]?)?$",
    re.IGNORECASE,
)


def resolve_openshift_oidc_idp_name(preflight):
    """OpenShift OAuth IdP name. Default ``Keycloak`` when unset."""
    return first_text(
        oauth_config(preflight).get("idp_name"), OPENSHIFT_OIDC_DEFAULT_IDP_NAME
    )


def openshift_apps_domain(preflight):
    return normalize_host((preflight.get("openshift") or {}).get("apps_domain"))


def openshift_oauth_redirect_uri(preflight, idp_name=None):
    """``https://oauth-openshift.<apps_domain>/oauth2callback/<idp_name>``.

    OpenShift's oauth-server uses this exact callback. Keycloak must register
    the same URI; a trailing ``/*`` does not match the live redirect.
    """
    apps = openshift_apps_domain(preflight)
    idp = text(idp_name) or resolve_openshift_oidc_idp_name(preflight)
    if not apps or not idp:
        return ""
    return f"https://oauth-openshift.{apps}/oauth2callback/{idp}"


def is_openshift_oauth_callback_uri(value):
    return bool(_OPENSHIFT_OAUTH_CALLBACK_RE.match(text(value)))


def row_is_openshift_oidc_client(preflight, client_id, row=None):
    wanted = text(client_id)
    if isinstance(row, dict) and text(row.get("source")).lower() == "openshift":
        return True
    if wanted.lower().startswith("openshift"):
        return True
    resolved = resolve_openshift_oidc_client_id(preflight)
    return bool(wanted) and wanted == resolved


def rewrite_openshift_oauth_redirect_uris(uris, preflight):
    """Replace auto OpenShift callback URIs with the configured IdP path.

    Custom (non-callback) URIs are kept. Empty lists become the derived
    callback. Externally managed clients are not written to ``rhbk_clients``;
    this only shapes URIs that Deploy RHBK Client would send.
    """
    derived = openshift_oauth_redirect_uri(preflight)
    if not derived:
        return [text(item) for item in (uris or []) if text(item)]
    parts = [text(item) for item in (uris or []) if text(item)]
    if not parts:
        return [derived]
    custom = [item for item in parts if not is_openshift_oauth_callback_uri(item)]
    if custom and len(custom) == len(parts):
        return parts
    return custom + [derived]


def grafana_oidc_is_explicitly_disabled(preflight):
    """True only when Grafana OIDC ``enabled`` is an explicit off value."""
    raw = _grafana_oidc(preflight).get("enabled")
    if raw is None:
        return False
    if isinstance(raw, bool):
        return not raw
    token = str(raw).strip().lower()
    return token in CREATE_CLIENT_FALSE


def grafana_oidc_is_enabled(preflight):
    """Grafana OIDC on/off. Explicit false wins; missing follows the oidc option."""
    if grafana_oidc_is_explicitly_disabled(preflight):
        return False
    raw = _grafana_oidc(preflight).get("enabled")
    if raw is None:
        return "oidc" in component_options(preflight, "grafana")
    if isinstance(raw, bool):
        return raw
    token = str(raw).strip().lower()
    if token in ("1", "true", "yes", "y", "on"):
        return True
    return bool(raw)


def grafana_oidc_requested(preflight, selected):
    """True when Grafana OIDC should run (option or enabled, not standalone)."""
    if not is_selected(preflight, selected, "grafana"):
        return False
    if "standalone" in component_options(preflight, "grafana"):
        return False
    return grafana_oidc_is_enabled(preflight)


def grafana_keycloak_client_should_not_be_provisioned(
    preflight, selected, client_id, row=None
):
    """Skip Grafana's Keycloak client when Grafana OIDC is explicitly off."""
    if not grafana_oidc_is_explicitly_disabled(preflight):
        return False
    selected_l = {text(item).lower() for item in (selected or [])}
    if "grafana" not in selected_l:
        return False
    if isinstance(row, dict) and text(row.get("source")).lower() == "grafana":
        return True
    wanted = text(client_id)
    grafana_id = text(_grafana_oidc(preflight).get("client_id")) or load_default_client_ids().get(
        "grafana", "grafana-client"
    )
    return bool(wanted) and wanted == grafana_id


# `independent` uses only flags that already exist: the client is managed outside
# the Keycloak client list of this run (an existing realm client is legitimate).
OIDC_CONSUMERS = (
    {
        "key": "grafana",
        "label": "Grafana",
        "client": lambda p: _grafana_oidc(p).get("client_id"),
        "enabled": lambda p: _grafana_oidc(p).get("enabled"),
        "skip": lambda p: "standalone" in component_options(p, "grafana"),
        "independent": lambda p: _grafana_oidc(p).get("client_secret_manual") is True,
        "fix": "component_config.grafana.oidc.client_id",
    },
    {
        "key": "bookstack",
        "label": "BookStack",
        "client": lambda p: component_config(p, "bookstack").get("oidc_client_id"),
        "enabled": lambda p: component_config(p, "bookstack").get("oidc_enabled"),
        "fix": "component_config.bookstack.oidc_client_id",
    },
    {
        "key": "netbox",
        "label": "NetBox",
        "client": lambda p: component_config(p, "netbox").get("oidc_client_id"),
        "enabled": lambda p: component_config(p, "netbox").get("oidc_enabled"),
        "fix": "component_config.netbox.oidc_client_id",
    },
    {
        "key": "gitlab",
        "label": "GitLab",
        "client": lambda p: component_config(p, "gitlab").get("oidc_client_id"),
        "enabled": lambda p: component_config(p, "gitlab").get("oidc_enabled"),
        "fix": "component_config.gitlab.oidc_client_id",
    },
    {
        "key": "quay",
        "label": "Quay",
        "client": lambda p: component_config(p, "quay").get("oidc_client_id"),
        "enabled": lambda p: component_config(p, "quay").get("oidc_enabled"),
        "independent": lambda p: component_config(p, "quay").get("fetch_oidc_secret_from_rhbk")
        is False,
        "fix": "component_config.quay.oidc_client_id",
    },
    {
        "key": "minio",
        "label": "MinIO",
        "client": resolve_minio_oidc_client_id,
        "enabled": lambda p: component_config(p, "minio").get("oidc_enabled"),
        "independent": lambda p: component_config(p, "minio").get("fetch_oidc_secret_from_rhbk")
        is False,
        "fix": "component_config.minio.oidc_client_id",
    },
    {
        "key": "dev_hub",
        "label": "Developer Hub",
        "client": resolve_dev_hub_keycloak_client_id,
        "enabled": lambda p: None,
        "fix": "component_config.dev_hub.keycloak_client_id",
    },
)


def _error(component, label, kind, message, client_id=""):
    return {
        "component": component,
        "label": label,
        "kind": kind,
        "clientId": client_id,
        "message": message,
    }


def validate_client_references(preflight, selected):
    """Active OIDC integrations that point at a removed Keycloak client.

    Local mode (RHBK is part of this run): a reference to a client the operator
    removed (``clients_dismissed``) is an error, including a blank ID that falls
    back to the framework's default client when that default was removed.
    External mode (no RHBK in this run, or the component's own "client managed
    elsewhere" flag): the client list is not consulted, so an existing realm
    client is accepted. OpenShift OIDC has no default client: it needs an explicit
    one in either mode.
    """
    errors = []
    default_client_ids = load_default_client_ids()
    rhbk = component_config(preflight, "rhbk")
    local_mode = is_selected(preflight, selected, "rhbk")
    present = {
        first_text(row.get("id")) for row in (rhbk.get("clients") or []) if isinstance(row, dict)
    }
    present.discard("")
    dismissed = {text(x) for x in (rhbk.get("clients_dismissed") or []) if text(x)}

    def check(component, label, client_id, independent, fix, default=""):
        client_id = text(client_id) or default
        external = (not local_mode) or independent
        if not client_id:
            if external:
                message = (
                    f"{label} OIDC uses an externally managed Keycloak client but no "
                    f"client ID is set. Set {fix}, or disable {label} OIDC."
                )
            else:
                message = (
                    f"{label} OIDC is enabled but has no Keycloak client. Add a client "
                    f"to the Keycloak client list and set {fix} to it, or disable "
                    f"{label} OIDC."
                )
            errors.append(_error(component, label, "no-client", message))
            return
        if not external and client_id in dismissed and client_id not in present:
            errors.append(
                _error(
                    component,
                    label,
                    "removed-client",
                    f'{label} OIDC still uses Keycloak client "{client_id}", which was '
                    f"removed from the client list. Add a replacement client and set {fix} "
                    f'to it, add "{client_id}" back to component_config.rhbk.clients, or '
                    f"disable {label} OIDC.",
                    client_id,
                )
            )

    for consumer in OIDC_CONSUMERS:
        if not is_selected(preflight, selected, consumer["key"]):
            continue
        skip = consumer.get("skip")
        if skip and skip(preflight):
            continue
        enabled = consumer["enabled"](preflight)
        requested = "oidc" in component_options(preflight, consumer["key"])
        if enabled is False or not (enabled is True or requested):
            continue
        independent = consumer.get("independent")
        check(
            consumer["key"],
            consumer["label"],
            consumer["client"](preflight),
            bool(independent and independent(preflight)),
            consumer["fix"],
            default_client_ids.get(consumer["key"], ""),
        )

    if openshift_oidc_requested(preflight, selected):
        check(
            "openshift",
            "OpenShift",
            resolve_openshift_oidc_client_id(preflight),
            oauth_config(preflight).get("fetch_client_secret") is False,
            "openshift.oauth_rhbk.client_id",
        )
    return errors


# ---------------------------------------------------------------------------
# OpenShift OIDC connection settings (Keycloak host, realm, credentials)
# ---------------------------------------------------------------------------


VERIFY_SSL_TRUE = ("1", "true", "yes", "on")
VERIFY_SSL_FALSE = ("0", "false", "no", "off")


def parse_verify_ssl(value):
    """Strict parse of ``openshift.oauth_rhbk.verify_ssl`` -> ``(verify, valid, explicit)``.

    Missing, null and blank mean "verify" (``explicit`` is False). ``true / yes / on / 1``
    verify, ``false / no / off / 0`` turn verification off. Anything else is invalid and
    is never read as false: ``verify`` stays True so a caller that ignores ``valid``
    still verifies. Mirrored by ``parseVerifySsl`` in rhbkClients.mjs, ``verify-ssl.js``
    in the Preflight server and the first tasks of the ``ocp_oidc_auth`` role.
    """
    if value is None:
        return True, True, False
    if isinstance(value, bool):
        return value, True, True
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        if value == 1:
            return True, True, True
        if value == 0:
            return False, True, True
        return True, False, True
    if isinstance(value, str):
        token = value.strip().lower()
        if token == "":
            return True, True, False
        if token in VERIFY_SSL_TRUE:
            return True, True, True
        if token in VERIFY_SSL_FALSE:
            return False, True, True
    return True, False, True


def verify_ssl_error_message(value):
    shown = json.dumps(value, default=str)
    if len(shown) > 40:
        shown = shown[:37] + '..."'
    return (
        f"OpenShift OIDC: verify_ssl {shown} is not a recognized value. Use true, yes, on "
        "or 1 to verify the Keycloak TLS certificate, false, no, off or 0 to turn "
        "verification off, or leave it blank to verify. An unrecognized value is never "
        "read as false."
    )


def _scopes(raw):
    if isinstance(raw, list):
        scopes = [text(s) for s in raw if text(s)]
    else:
        scopes = [
            part.strip()
            for part in text(raw or "groups").replace("\n", ",").split(",")
            if part.strip()
        ]
    return scopes or ["groups"]


def resolve_openshift_oauth_settings(preflight, selected, rhbk_vars=None):
    """Effective OpenShift OIDC connection settings.

    ``rhbk_vars`` is the generated ``vars_rhbk.yml`` when available (it carries
    the final RHBK hostname/realm after route derivation); otherwise the RHBK form
    values and the OpenShift apps domain are used.
    """
    oauth = oauth_config(preflight)
    rhbk = component_config(preflight, "rhbk")
    rhbk_vars = rhbk_vars or {}
    rhbk_mode = is_selected(preflight, selected, "rhbk")
    apps_domain = text((preflight.get("openshift") or {}).get("apps_domain"))

    inherited_host = ""
    inherited_realm = ""
    inherited_user = ""
    if rhbk_mode:
        inherited_host = normalize_host(
            first_text(
                rhbk_vars.get("ocp_rhbk_hostname"),
                rhbk_vars.get("rhbk_hostname"),
                rhbk.get("hostname"),
                f"keycloak.{apps_domain}" if apps_domain else "",
            )
        )
        inherited_realm = first_text(
            rhbk_vars.get("rhbk_realm"),
            rhbk_vars.get("ocp_rhbk_realm"),
            rhbk.get("realm"),
        )
        inherited_user = first_text(
            rhbk_vars.get("rhbk_admin_user"),
            rhbk.get("admin_user"),
            "admin",
        )

    own_host = "" if rhbk_mode else normalize_host(oauth.get("keycloak_hostname"))
    own_realm = "" if rhbk_mode else text(oauth.get("realm"))
    own_user = "" if rhbk_mode else text(oauth.get("admin_user"))
    own_password = "" if rhbk_mode else text(oauth.get("admin_password"))
    rhbk_password = text(rhbk.get("admin_password")) or (
        "vault" if text(rhbk_vars.get("rhbk_admin_password")) else ""
    )
    if own_password:
        password_source = "openshift"
    elif rhbk_mode and rhbk_password:
        password_source = "rhbk"
    else:
        password_source = ""

    return {
        "mode": "rhbk" if rhbk_mode else "external",
        "hostname": own_host or inherited_host,
        "inheritedHostname": inherited_host,
        "hostnameExplicit": bool(own_host),
        "realm": own_realm or inherited_realm,
        "realmExplicit": bool(own_realm),
        "clientId": resolve_openshift_oidc_client_id(preflight),
        "idpName": first_text(oauth.get("idp_name"), OPENSHIFT_OIDC_DEFAULT_IDP_NAME),
        "mappingMethod": first_text(
            oauth.get("mapping_method"), OPENSHIFT_OIDC_DEFAULT_MAPPING_METHOD
        ),
        "extraScopes": _scopes(oauth.get("extra_scopes")),
        "verifySsl": parse_verify_ssl(oauth.get("verify_ssl"))[0],
        "verifySslValid": parse_verify_ssl(oauth.get("verify_ssl"))[1],
        "verifySslExplicit": parse_verify_ssl(oauth.get("verify_ssl"))[2],
        "adminUser": own_user or inherited_user,
        "adminUserExplicit": bool(own_user),
        "adminPassword": own_password,
        "adminPasswordSource": password_source,
    }


def validate_openshift_oauth_settings(preflight, selected, rhbk_vars=None):
    """Missing or conflicting OpenShift OIDC connection inputs (client id excluded;
    that is reported by ``validate_client_references``)."""
    if not openshift_oidc_requested(preflight, selected):
        return []
    s = resolve_openshift_oauth_settings(preflight, selected, rhbk_vars)
    external = s["mode"] == "external"
    where = "Existing Keycloak (RHBK is not part of this run)" if external else "OpenShift OIDC"
    errors = []

    def add(kind, message):
        errors.append(_error("openshift", "OpenShift", kind, message))

    if not s["verifySslValid"]:
        add(
            "invalid-verify-ssl",
            verify_ssl_error_message(oauth_config(preflight).get("verify_ssl")),
        )
    raw_oauth_host = text(oauth_config(preflight).get("keycloak_hostname")) if external else ""
    if hostname_has_scheme(raw_oauth_host):
        add("hostname-has-scheme", KEYCLOAK_HOSTNAME_SCHEME_MESSAGE)
    elif "/" in raw_oauth_host:
        add("hostname-has-path", KEYCLOAK_HOSTNAME_PATH_MESSAGE)
    elif not s["hostname"]:
        add(
            "missing-hostname",
            (
                f"{where}: set the Keycloak hostname (openshift.oauth_rhbk.keycloak_hostname)."
                if external
                else "OpenShift OIDC: no Keycloak hostname. Set the RHBK hostname."
            ),
        )
    elif not _HOST_RE.match(s["hostname"]):
        add(
            "invalid-hostname",
            (
                f'OpenShift OIDC: Keycloak hostname "{s["hostname"]}" is not a valid host '
                "name. Use the route host only (for example keycloak.example.com)."
            ),
        )
    if not s["realm"]:
        add(
            "missing-realm",
            (
                f"{where}: set the Keycloak realm (openshift.oauth_rhbk.realm)."
                if external
                else "OpenShift OIDC: no Keycloak realm. Set the RHBK realm."
            ),
        )
    if s["mappingMethod"] not in MAPPING_METHODS:
        add(
            "invalid-mapping-method",
            (
                f'OpenShift OIDC: mapping method "{s["mappingMethod"]}" is not one of '
                f"{', '.join(MAPPING_METHODS)}."
            ),
        )
    if not s["adminUser"]:
        add(
            "missing-admin-user",
            (
                f"{where}: set the Keycloak admin user (openshift.oauth_rhbk.admin_user). "
                "The job uses it only to read the client secret."
            ),
        )
    if not s["adminPasswordSource"]:
        add(
            "missing-admin-password",
            (
                f"{where}: set the Keycloak admin password "
                "(openshift.oauth_rhbk.admin_password). The job uses it only to read the "
                "client secret; the client is never created or changed."
                if external
                else "OpenShift OIDC: no Keycloak admin password. Set the RHBK admin password."
            ),
        )
    return errors


def rhbk_existing_connection_requested(preflight):
    opts = {text(x).lower() for x in component_options(preflight, "rhbk")}
    return bool(opts.intersection(RHBK_EXISTING_CONNECTION_OPTIONS))


def validate_rhbk_existing_connection(preflight, selected):
    """Client-only (and similar) operations need an existing realm name."""
    if not is_selected(preflight, selected, "rhbk"):
        return []
    if not rhbk_existing_connection_requested(preflight):
        return []
    if text(component_config(preflight, "rhbk").get("realm")):
        return []
    return [_error("rhbk", "RHBK", "missing-realm", RHBK_EXISTING_REALM_MESSAGE)]


def validate_grafana_oidc_settings(preflight, selected):
    """When Grafana OIDC is on and RHBK is in the run, require that connection.

    Grafana-only (no RHBK) uses the pasted issuer and secret. Mapping method is
    OpenShift-specific and is not applied here.
    """
    if not grafana_oidc_requested(preflight, selected):
        return []
    if not is_selected(preflight, selected, "rhbk"):
        return []
    rhbk = component_config(preflight, "rhbk")
    apps_domain = text((preflight.get("openshift") or {}).get("apps_domain"))
    host = normalize_host(
        first_text(
            rhbk.get("hostname"),
            rhbk.get("rhbk_hostname"),
            f"keycloak.{apps_domain}" if apps_domain else "",
        )
    )
    realm = first_text(rhbk.get("realm"), rhbk.get("rhbk_realm"))
    errors = []
    if not host:
        errors.append(
            _error(
                "grafana",
                "Grafana",
                "missing-hostname",
                "Grafana OIDC: no Keycloak hostname. Set the RHBK hostname.",
            )
        )
    if not realm:
        errors.append(
            _error(
                "grafana",
                "Grafana",
                "missing-realm",
                "Grafana OIDC: no Keycloak realm. Set the RHBK realm.",
            )
        )
    return errors


def _truthy_flag(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    token = str(value).strip().lower()
    if token == "":
        return default
    return token not in CREATE_CLIENT_FALSE


def minio_oidc_is_enabled(preflight):
    """Match Preflight MinIO form: oidc_enabled defaults to on."""
    cfg = component_config(preflight, "minio")
    nested = cfg.get("oidc") if isinstance(cfg.get("oidc"), dict) else {}
    raw = cfg.get("oidc_enabled")
    if raw is None:
        raw = nested.get("enabled")
    return _truthy_flag(raw, True)


def minio_oidc_requested(preflight, selected):
    """True when MinIO is in the run and console OIDC is enabled."""
    if not is_selected(preflight, selected, "minio"):
        return False
    return minio_oidc_is_enabled(preflight)


def minio_oidc_needs_keycloak_admin(preflight):
    """Admin password required to create/update the client or fetch its secret."""
    cfg = component_config(preflight, "minio")
    managed = minio_keycloak_is_managed(preflight, cfg)
    fetch_raw = cfg.get("fetch_oidc_secret_from_rhbk")
    nested = cfg.get("oidc") if isinstance(cfg.get("oidc"), dict) else {}
    if fetch_raw is None:
        fetch_raw = nested.get("fetch_secret_from_rhbk")
    fetch_secret = _truthy_flag(fetch_raw, True)
    return managed or fetch_secret


MINIO_OIDC_WELL_KNOWN = "/.well-known/openid-configuration"


def ensure_minio_oidc_discovery_url(issuer_or_discovery):
    """Append OpenID discovery path when given an issuer base URL."""
    raw = text(issuer_or_discovery).rstrip("/")
    if not raw:
        return ""
    if raw.endswith(MINIO_OIDC_WELL_KNOWN):
        return raw
    return f"{raw}{MINIO_OIDC_WELL_KNOWN}"


def build_minio_oidc_issuer_url(hostname, realm):
    host = normalize_host(hostname)
    realm_name = text(realm) or "rhlab"
    if not host:
        return ""
    return f"https://{host}/realms/{realm_name}"


def _minio_cfg_discovery_inputs(cfg):
    nested = cfg.get("oidc") if isinstance(cfg.get("oidc"), dict) else {}
    explicit = first_text(
        cfg.get("oidc_config_url"),
        cfg.get("minio_oidc_config_url"),
        nested.get("config_url"),
    )
    issuer = first_text(
        cfg.get("oidc_issuer"),
        cfg.get("minio_oidc_issuer"),
        nested.get("issuer"),
    )
    return explicit, issuer


def resolve_minio_oidc_discovery_url(preflight, selected, rhbk_vars=None):
    """Effective MinIO OpenID discovery URL from form / imported JSON.

    Preference: explicit ``oidc_config_url`` / ``minio_oidc_config_url``, then
    ``oidc_issuer`` / ``minio_oidc_issuer``, then hostname + realm from
    ``resolve_minio_keycloak_settings``. Empty strings are treated as unset so
    imported blanks do not wipe a derived URL.
    """
    cfg = component_config(preflight, "minio")
    explicit, issuer = _minio_cfg_discovery_inputs(cfg)
    if explicit:
        return ensure_minio_oidc_discovery_url(explicit)
    if issuer:
        return ensure_minio_oidc_discovery_url(issuer)
    settings = resolve_minio_keycloak_settings(preflight, selected, rhbk_vars)
    built = build_minio_oidc_issuer_url(settings["hostname"], settings["realm"])
    return ensure_minio_oidc_discovery_url(built) if built else ""


def resolve_minio_keycloak_settings(preflight, selected, rhbk_vars=None):
    """Effective Keycloak connection for MinIO OIDC (inherit RHBK or external).

    External fields live on ``component_config.minio`` (keycloak_hostname,
    keycloak_admin_user, keycloak_admin_password, keycloak_realm /
    keycloak_verify_ssl). When RHBK is selected those connection fields are
    ignored so operators are not asked twice.
    """
    cfg = component_config(preflight, "minio")
    rhbk = component_config(preflight, "rhbk")
    rhbk_vars = rhbk_vars or {}
    rhbk_mode = is_selected(preflight, selected, "rhbk")
    apps_domain = text((preflight.get("openshift") or {}).get("apps_domain"))

    inherited_host = ""
    inherited_realm = ""
    inherited_user = ""
    if rhbk_mode:
        inherited_host = normalize_host(
            first_text(
                rhbk_vars.get("ocp_rhbk_hostname"),
                rhbk_vars.get("rhbk_hostname"),
                rhbk.get("hostname"),
                f"keycloak.{apps_domain}" if apps_domain else "",
            )
        )
        inherited_realm = first_text(
            rhbk_vars.get("rhbk_realm"),
            rhbk_vars.get("ocp_rhbk_realm"),
            rhbk.get("realm"),
            cfg.get("keycloak_realm"),
        )
        inherited_user = first_text(
            rhbk_vars.get("rhbk_admin_user"),
            rhbk.get("admin_user"),
            "admin",
        )

    own_host = "" if rhbk_mode else normalize_host(
        first_text(cfg.get("keycloak_hostname"), cfg.get("rhbk_hostname"))
    )
    own_realm = "" if rhbk_mode else first_text(
        cfg.get("keycloak_realm"), cfg.get("rhbk_realm")
    )
    own_user = "" if rhbk_mode else first_text(
        cfg.get("keycloak_admin_user"), cfg.get("rhbk_admin_user"), "admin"
    )
    own_password = "" if rhbk_mode else first_text(
        cfg.get("keycloak_admin_password"),
        cfg.get("rhbk_admin_password"),
        cfg.get("admin_password"),
    )
    rhbk_password = text(rhbk.get("admin_password")) or (
        "vault" if text(rhbk_vars.get("rhbk_admin_password")) else ""
    )
    if own_password:
        password_source = "minio"
    elif rhbk_mode and rhbk_password:
        password_source = "rhbk"
    else:
        password_source = ""

    verify_raw = cfg.get("keycloak_verify_ssl")
    if verify_raw is None:
        verify_raw = cfg.get("rhbk_verify_ssl")
    # MinIO OIDC default (when unset): skip Keycloak TLS verify → rhbk_verify_ssl false.
    # OpenShift OIDC still defaults to verify-on via parse_verify_ssl(None).
    if verify_raw is None:
        verify, verify_valid, verify_explicit = False, True, True
    else:
        verify, verify_valid, verify_explicit = parse_verify_ssl(verify_raw)

    hostname = own_host or inherited_host
    realm = own_realm or inherited_realm or "rhlab"
    explicit_discovery, explicit_issuer = _minio_cfg_discovery_inputs(cfg)
    if explicit_discovery:
        discovery_url = ensure_minio_oidc_discovery_url(explicit_discovery)
        issuer = (
            discovery_url[: -len(MINIO_OIDC_WELL_KNOWN)]
            if discovery_url.endswith(MINIO_OIDC_WELL_KNOWN)
            else build_minio_oidc_issuer_url(hostname, realm)
        )
    elif explicit_issuer:
        issuer = text(explicit_issuer).rstrip("/")
        if issuer.endswith(MINIO_OIDC_WELL_KNOWN):
            issuer = issuer[: -len(MINIO_OIDC_WELL_KNOWN)]
        discovery_url = ensure_minio_oidc_discovery_url(issuer)
    else:
        issuer = build_minio_oidc_issuer_url(hostname, realm)
        discovery_url = ensure_minio_oidc_discovery_url(issuer) if issuer else ""

    return {
        "mode": "rhbk" if rhbk_mode else "external",
        "hostname": hostname,
        "inheritedHostname": inherited_host,
        "hostnameExplicit": bool(own_host),
        "realm": realm,
        "realmExplicit": bool(own_realm),
        "clientId": minio_effective_client_id(preflight, cfg),
        "adminUser": own_user or inherited_user or "admin",
        "adminUserExplicit": bool(own_user),
        "adminPassword": own_password,
        "adminPasswordSource": password_source,
        "needsAdmin": minio_oidc_needs_keycloak_admin(preflight),
        "managedClient": minio_keycloak_is_managed(preflight, cfg),
        "verifySsl": verify,
        "verifySslValid": verify_valid,
        "verifySslExplicit": verify_explicit,
        "fetchOidcSecret": _truthy_flag(cfg.get("fetch_oidc_secret_from_rhbk"), True),
        "oidcClientSecret": first_text(
            cfg.get("oidc_client_secret"),
            (cfg.get("oidc") or {}).get("client_secret")
            if isinstance(cfg.get("oidc"), dict)
            else "",
        ),
        "issuer": issuer,
        "discoveryUrl": discovery_url,
    }


def validate_minio_keycloak_settings(preflight, selected, rhbk_vars=None):
    """Missing MinIO OIDC Keycloak connection inputs (inherit or external)."""
    if not minio_oidc_requested(preflight, selected):
        return []
    s = resolve_minio_keycloak_settings(preflight, selected, rhbk_vars)
    external = s["mode"] == "external"
    where = (
        "MinIO OIDC → Existing Keycloak (RHBK is not part of this run)"
        if external
        else "MinIO OIDC"
    )
    errors = []

    def add(kind, message):
        errors.append(_error("minio", "MinIO", kind, message))

    if not s["verifySslValid"]:
        cfg = component_config(preflight, "minio")
        add(
            "invalid-verify-ssl",
            verify_ssl_error_message(
                cfg.get("keycloak_verify_ssl", cfg.get("rhbk_verify_ssl"))
            ).replace("OpenShift OIDC", "MinIO OIDC"),
        )

    cfg = component_config(preflight, "minio")
    raw_host = (
        first_text(cfg.get("keycloak_hostname"), cfg.get("rhbk_hostname"))
        if external
        else ""
    )
    if hostname_has_scheme(raw_host):
        add(
            "hostname-has-scheme",
            KEYCLOAK_HOSTNAME_SCHEME_MESSAGE.replace("OpenShift OIDC", "MinIO OIDC"),
        )
    elif "/" in raw_host:
        add(
            "hostname-has-path",
            KEYCLOAK_HOSTNAME_PATH_MESSAGE.replace("OpenShift OIDC", "MinIO OIDC"),
        )
    elif not s["hostname"]:
        add(
            "missing-hostname",
            (
                f"{where}: set Keycloak hostname on the MinIO form "
                "(component_config.minio.keycloak_hostname)."
                if external
                else "MinIO OIDC: no Keycloak hostname. Set the RHBK hostname "
                "or select RHBK in this run."
            ),
        )
    elif not _HOST_RE.match(s["hostname"]):
        add(
            "invalid-hostname",
            f'MinIO OIDC: Keycloak hostname "{s["hostname"]}" is not a valid host name.',
        )

    if not s["realm"]:
        add(
            "missing-realm",
            (
                f"{where}: set the Keycloak realm "
                "(component_config.minio.keycloak_realm)."
                if external
                else "MinIO OIDC: no Keycloak realm. Set the RHBK realm."
            ),
        )

    discovery = text(s.get("discoveryUrl")) or resolve_minio_oidc_discovery_url(
        preflight, selected, rhbk_vars
    )
    if s["hostname"] and s["realm"] and not discovery:
        add(
            "missing-discovery-url",
            f"{where}: OpenID discovery URL is empty. Set "
            "component_config.minio.oidc_config_url, oidc_issuer, or Keycloak "
            "hostname + realm so Bootstrap can write "
            "minio_oidc_config_url / MINIO_IDENTITY_OPENID_CONFIG_URL.",
        )
    elif discovery and not discovery.startswith(("http://", "https://")):
        add(
            "invalid-discovery-url",
            f"{where}: OpenID discovery URL must start with http:// or https:// "
            "(empty values cause MinIO 'unexpected scheme found').",
        )
    elif discovery and MINIO_OIDC_WELL_KNOWN not in discovery:
        add(
            "invalid-discovery-url",
            f"{where}: OpenID discovery URL must include "
            f"{MINIO_OIDC_WELL_KNOWN}.",
        )

    if s["needsAdmin"] and not s["adminUser"]:
        add(
            "missing-admin-user",
            f"{where}: set the Keycloak admin user used to create the MinIO "
            "client or fetch its secret.",
        )
    if s["needsAdmin"] and not s["adminPasswordSource"]:
        add(
            "missing-admin-password",
            (
                f"{where}: set Keycloak admin password on the MinIO form "
                "(component_config.minio.keycloak_admin_password). "
                "RHBK does not need to be selected when using an existing Keycloak."
                if external
                else "MinIO OIDC: no Keycloak admin password. Set the RHBK admin password."
            ),
        )
    if (
        external
        and not s["fetchOidcSecret"]
        and not s["oidcClientSecret"]
        and not s["managedClient"]
    ):
        add(
            "missing-client-secret",
            f"{where}: provide the OIDC client secret, or enable "
            "Fetch OIDC client secret from Keycloak.",
        )
    return errors


def validate_preflight_oidc(preflight, selected, rhbk_vars=None):
    return (
        validate_rhbk_existing_connection(preflight, selected)
        + validate_client_references(preflight, selected)
        + validate_openshift_oauth_settings(preflight, selected, rhbk_vars)
        + validate_grafana_oidc_settings(preflight, selected)
        + validate_minio_keycloak_settings(preflight, selected, rhbk_vars)
    )


def format_errors(errors):
    return "\n".join(f"- {error['message']}" for error in errors)


def main():
    if "--print-default-client-ids" in sys.argv[1:]:
        # Used by ado-preflight-ui/scripts/sync-oidc-client-defaults.py so the form
        # resolves blank client IDs from the same file as the collection.
        print(json.dumps(load_default_client_ids(), indent=2, sort_keys=True))
        return
    preflight_file = os.environ.get("ADO_PREFLIGHT_JSON") or (
        sys.argv[1] if len(sys.argv) > 1 else ""
    )
    if not preflight_file:
        raise SystemExit("ADO_PREFLIGHT_JSON is required")
    with open(preflight_file, encoding="utf-8") as handle:
        preflight = json.load(handle)
    selected = set(json.loads(os.environ.get("ADO_SELECTED_COMPONENTS") or "[]"))
    errors = validate_preflight_oidc(preflight, selected)
    if errors:
        raise SystemExit(
            "Preflight OIDC validation failed; nothing was generated.\n" + format_errors(errors)
        )
    print("Preflight OIDC validation passed.")


if __name__ == "__main__":
    main()
