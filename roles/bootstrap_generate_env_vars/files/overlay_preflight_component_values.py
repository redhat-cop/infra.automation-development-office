"""Overlay preflight component_config into generated group_vars (invoked by Ansible)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from pathlib import Path
import base64
import binascii
import copy
import json
import re
import shutil
import yaml


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


class QuotedString(str):
    pass


def quoted_string_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


NoAliasDumper.add_representer(QuotedString, quoted_string_representer)

preflight_file = Path(os.environ["ADO_PREFLIGHT_JSON"])
env_dir = Path(os.environ["ADO_ENV_DIR"])
selected_components = set(json.loads(os.environ["ADO_SELECTED_COMPONENTS"]))

preflight = json.loads(preflight_file.read_text())

# Pre-Flight provision app aws_instance aliases to collection app ec2_instance.
if "aws_instance" in selected_components:
    selected_components.discard("aws_instance")
    selected_components.add("ec2_instance")

_preflight_cfg = preflight.setdefault("component_config", {})
_aws_instance_cfg = _preflight_cfg.get("aws_instance")
_ec2_instance_cfg = _preflight_cfg.get("ec2_instance")
if isinstance(_aws_instance_cfg, dict) or isinstance(_ec2_instance_cfg, dict):
    _merged_ec2 = {}
    if isinstance(_aws_instance_cfg, dict):
        _merged_ec2.update(_aws_instance_cfg)
    if isinstance(_ec2_instance_cfg, dict):
        _merged_ec2.update(_ec2_instance_cfg)
    _preflight_cfg["ec2_instance"] = _merged_ec2

APP_ROUTE_NAMESPACES = {
    "grafana": ["grafana"],
    "gitlab": ["gitlab-system"],
    "rhbk": ["rhbk"],
    "quay": ["quay-enterprise"],
    "kafka": ["amq-streams", "kafka"],
    "elastic": ["elastic-system"],
    "bookstack": ["bookstack"],
    "netbox": ["netbox"],
    "dev_hub": ["backstage"],
    "zabbix": ["zabbix"],
    "acs": ["stackrox"],
    "aap": ["aap"],
    "minio": ["minio"],
    "pega": ["pega"],
    "devspaces": ["openshift-devspaces"],
    "acm": ["open-cluster-management"],
    "389ds": ["dirsrv"],
    "gitops": ["openshift-gitops"],
}

# Ingress UI lives under component_config.cert_manager; ensure overlay + JTs run.
_cm = (preflight.get("component_config") or {}).get("cert_manager") or {}
if str(_cm.get("update_default_ingress", "")).lower() in ("1", "true", "yes", "on"):
    selected_components.add("cert_manager")


def is_secret_key(key):
    k = str(key or "").lower()
    if k in {"hub_s3_secret", "hub_azure_secret"}:
        return False
    return any(
        x in k
        for x in [
            "password",
            "token",
            "api_key",
            "secret",
            "vault",
            "credential",
            "tls_key",
            "tls_crt",
            "activation_key",
            "manifest_content",
        ]
    )


def load_yaml(path):
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return data if isinstance(data, dict) else {}


def write_yaml(path, data, mode="0644"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.dump(data, Dumper=NoAliasDumper, sort_keys=False, width=1000))
    path.chmod(int(mode, 8))


def first_present(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def merge_shared_aws_vault(values):
    aws_path = env_dir / "vault_aws.yml"
    aws_data = load_yaml(aws_path)
    changed = False
    combined = {
        str(key): value
        for key, value in (values or {}).items()
        if value is not None
    }
    access_key = first_present(
        combined.get("access_key_id"),
        combined.get("awspca_access_key_id"),
    )
    secret_key = first_present(
        combined.get("secret_access_key"),
        combined.get("awspca_secret_access_key"),
    )
    session_token = combined.get("session_token")
    if access_key is not None:
        aws_data["vault_aws_access_key_id"] = str(access_key)
        changed = True
    if secret_key is not None:
        aws_data["vault_aws_secret_access_key"] = str(secret_key)
        changed = True
    if session_token is not None:
        aws_data["vault_aws_session_token"] = str(session_token)
        changed = True
    if changed:
        write_yaml(aws_path, aws_data, "0600")


def strip_host(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return (
        raw.replace("https://", "")
        .replace("http://", "")
        .split("/", maxsplit=1)[0]
        .strip()
    )


# Standalone / RHEL-install-only keys that must never land in OpenShift group_vars.
_STANDALONE_DERIVED_KEYS = {
    "grafana": (
        "install_grafana_hostname",
        "install_grafana_standalone_hostname",
        "install_grafana_rpm_path",
        "install_grafana_rpm_url",
        "install_grafana_rhn_org_id",
        "install_grafana_rhn_activation_key",
        "grafana_rpm_path",
        "grafana_rpm_url",
    ),
    "gitlab": (
        "install_gitlab_hostname",
        "install_gitlab_standalone_hostname",
        "install_gitlab_external_url",
        "gitlab_external_url",
        "install_gitlab_edition",
        "gitlab_edition",
        "install_gitlab_rpm_path",
        "gitlab_rpm_path",
        "install_gitlab_rpm_url",
        "gitlab_rpm_url",
        "install_gitlab_rhn_org_id",
        "gitlab_rhn_org_id",
        "install_gitlab_rhn_activation_key",
        "gitlab_tls_crt",
        "gitlab_tls_key",
    ),
    "rhbk": (
        "rhbk_standalone_hostname",
        "install_rhbk_standalone_hostname",
        "rhbk_standalone_zip",
        "rhbk_standalone_zip_url",
        "rhbk_standalone_zip_source",
        "rhbk_standalone_zip_git_repo",
        "rhbk_standalone_zip_git_path",
        "rhbk_standalone_zip_git_branch",
        "install_rhbk_standalone_zip_source",
        "install_rhbk_standalone_zip_git_repo",
        "install_rhbk_standalone_zip_git_path",
        "install_rhbk_standalone_zip_git_branch",
        "rhbk_standalone_tls_crt",
        "rhbk_standalone_tls_key",
        "rhbk_standalone_https_enabled",
        "install_rhbk_standalone_https_enabled",
        "install_rhbk_standalone_http_port",
        "install_rhbk_standalone_https_port",
        "install_rhbk_standalone_http_enabled",
    ),
}


def pop_all_standalone_keys(mapping):
    """Remove every standalone_* key from a dict (in place)."""
    if not isinstance(mapping, dict):
        return
    for key in list(mapping.keys()):
        if str(key).startswith("standalone_"):
            mapping.pop(key, None)


def purge_standalone_install_vars(vars_data, component):
    """
    OpenShift installs must not carry RHEL/standalone install fields.
    Purge top-level, components_env, and component_config.
    """
    pop_all_standalone_keys(vars_data)
    for key in _STANDALONE_DERIVED_KEYS.get(component, ()):
        vars_data.pop(key, None)
    env_block = (vars_data.get("components_env") or {}).get(component)
    if isinstance(env_block, dict):
        pop_all_standalone_keys(env_block)
        for key in _STANDALONE_DERIVED_KEYS.get(component, ()):
            env_block.pop(key, None)
    cfg_block = (vars_data.get("component_config") or {}).get(component)
    if isinstance(cfg_block, dict):
        pop_all_standalone_keys(cfg_block)
        for key in _STANDALONE_DERIVED_KEYS.get(component, ()):
            cfg_block.pop(key, None)


def openshift_cluster_hint(preflight):
    openshift = preflight.get("openshift") or {}
    return " ".join(
        str(openshift.get(key) or "").strip()
        for key in ("apps_domain", "api_host", "cluster_url")
    ).lower()


def is_dev_openshift_cluster(preflight):
    hint = openshift_cluster_hint(preflight)
    return "ocp-dev" in hint or ".dev.rhlab" in hint


def effective_storage_class(preflight, storage_value):
    """Return the StorageClass the user set in preflight (trimmed).

    Do not remap or drop values based on cluster name or CSI brand — customers
    set the class that exists in *their* cluster. Returning empty here used to
    wipe ``storage`` from group_vars and break ACS/Quay PVC applies.
    """
    del preflight  # API kept for call sites; unused on purpose.
    return str(storage_value or "").strip()


def rhbk_selected_in_preflight(preflight):
    components = {str(x).strip().lower() for x in (preflight.get("components") or [])}
    openshift_apps = {
        str(x).strip().lower()
        for x in ((preflight.get("component_apps") or {}).get("openshift") or [])
    }
    return "rhbk" in components or "rhbk" in openshift_apps or "all" in components


def apply_storage_var(vars_data, component, preflight, storage_value, vars_data_changed):
    storage = effective_storage_class(preflight, storage_value)
    if not storage:
        return vars_data_changed
    vars_data["storage"] = storage
    vars_data.setdefault("components_env", {}).setdefault(component, {})
    vars_data["components_env"][component]["storage"] = storage
    if component == "gitlab":
        vars_data["gitlab_install_storage_class"] = storage
        vars_data["storage_class"] = storage
        vars_data["components_env"][component]["storage_class"] = storage
    return True


def rhbk_oidc_issuer_url(preflight, vars_data=None):
    """Build https://<keycloak-host>/realms/<realm> from preflight RHBK + generated vars."""
    vars_data = vars_data or {}
    rhbk_cfg = (preflight.get("component_config") or {}).get("rhbk") or {}
    apps_domain = str(((preflight.get("openshift") or {}).get("apps_domain")) or "").strip()
    host = first_present(
        vars_data.get("ocp_rhbk_hostname"),
        vars_data.get("rhbk_hostname"),
        rhbk_cfg.get("hostname"),
        rhbk_cfg.get("rhbk_hostname"),
        f"keycloak.{apps_domain}" if apps_domain else None,
    )
    realm = first_present(
        vars_data.get("ocp_rhbk_realm"),
        vars_data.get("rhbk_realm"),
        rhbk_cfg.get("realm"),
        rhbk_cfg.get("rhbk_realm"),
        env_label_suffix(preflight.get("environment")),
        "rhlab",
    )
    host_clean = strip_host(host)
    if not host_clean or not realm:
        return None, str(realm or "")
    return f"https://{host_clean}/realms/{realm}", str(realm)


def env_label_suffix(env):
    e = str(env or "").strip().lower()
    if e == "dev":
        return "Dev"
    if e == "prod":
        return "Prod"
    if e:
        return e[0].upper() + e[1:]
    return "Lab"


def as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


install_aap = as_bool(
    (preflight.get("pre_installs") or {}).get("install_aap"),
    False,
)
attach_aap_license = as_bool(
    (preflight.get("pre_installs") or {}).get("attach_aap_license"),
    False,
) or as_bool(
    ((preflight.get("pre_installs") or {}).get("aap") or {}).get("license_only"),
    False,
) or as_bool(
    ((preflight.get("component_config") or {}).get("aap") or {}).get("license_only"),
    False,
)
# install_during_bootstrap alone must not mean full operator install when
# attach/license_only is set (UI sets both for license-only attach).
if (
    not install_aap
    and not attach_aap_license
    and as_bool(
        ((preflight.get("component_config") or {}).get("aap") or {}).get(
            "install_during_bootstrap"
        ),
        False,
    )
):
    install_aap = True
if install_aap or attach_aap_license:
    selected_components.add("aap")
    # License-only / attach must still have a component_config.aap block so
    # merge_component runs (hostname, RHN, license_mode).
    preflight.setdefault("component_config", {})
    aap_cfg = preflight["component_config"].setdefault("aap", {})
    pre_aap = ((preflight.get("pre_installs") or {}).get("aap") or {})
    preflight_aap = preflight.get("aap") or {}
    if install_aap:
        aap_cfg["install_during_bootstrap"] = True
    if attach_aap_license and not install_aap:
        aap_cfg["install_during_bootstrap"] = True
        aap_cfg["license_only"] = True
    for key in (
        "license_mode",
        "subscription_manifest_file",
        "subscription_manifest_content_base64",
        "subscription_manifest_encoding",
        "rhn_username",
        "rhn_password",
        "rhn_subscription_id",
        "rhn_client_id",
        "rhn_client_secret",
        "admin_password",
        "hostname",
        "namespace",
    ):
        if not aap_cfg.get(key) and pre_aap.get(key):
            aap_cfg[key] = pre_aap.get(key)
    # Attach/license-only: General tab aap.hostname / admin_password win over
    # stale Install AAP component_config host fields.
    if attach_aap_license and not install_aap:
        if preflight_aap.get("hostname"):
            aap_cfg["hostname"] = preflight_aap.get("hostname")
        if preflight_aap.get("admin_password"):
            aap_cfg["admin_password"] = preflight_aap.get("admin_password")
    else:
        if not aap_cfg.get("hostname") and preflight_aap.get("hostname"):
            aap_cfg["hostname"] = preflight_aap.get("hostname")
        if not aap_cfg.get("admin_password") and preflight_aap.get("admin_password"):
            aap_cfg["admin_password"] = preflight_aap.get("admin_password")

aap_version_dotted = {"24": "2.4", "25": "2.5", "26": "2.6", "27": "2.7"}
aap_version_number = {"2.4": "24", "2.5": "25", "2.6": "26", "2.7": "27"}


def aap_dotted_version(*values, default="2.7"):
    for value in values:
        if value is None or value == "":
            continue
        text = str(value).strip()
        if text in aap_version_dotted:
            return aap_version_dotted[text]
        if text in aap_version_number:
            return text
    return default


jinja_open = "{" + "{"
jinja_close = "}" + "}"


def vault_ref(name):
    return QuotedString(jinja_open + " " + name + " " + jinja_close)


def playbook_file_ref(filename):
    return (
        jinja_open
        + " playbook_dir "
        + jinja_close
        + "/../../files/"
        + filename
    )


def safe_upload_filename(name, default_name):
    candidate = Path(str(name or default_name)).name
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip(".-")
    return candidate or default_name


def write_repo_file_from_preflight(filename, content, default_name, encoding="base64"):
    project_dir = env_dir.parents[2] if len(env_dir.parents) >= 3 else env_dir
    files_dir = project_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    target = files_dir / safe_upload_filename(filename, default_name)
    if str(encoding or "base64").lower() in ("base64", "b64"):
        try:
            raw = base64.b64decode(str(content), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SystemExit(f"Invalid base64 upload content for {target.name}: {exc}") from exc
        target.write_bytes(raw)
    else:
        target.write_text(str(content), encoding="utf-8")
    target.chmod(0o600)
    return target


def copy_repo_file_from_path(src, filename, default_name):
    project_dir = env_dir.parents[2] if len(env_dir.parents) >= 3 else env_dir
    files_dir = project_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    target = files_dir / safe_upload_filename(filename, default_name)
    shutil.copy2(str(src), target)
    target.chmod(0o600)
    return target


def merge_component(component, cfg):
    if not isinstance(cfg, dict):
        return

    # Playbooks historically load vault_dirsrv.yml / vars_dirsrv.yml
    # while the registry component key is "389ds". Pre-Flight provision
    # aws_instance writes vars_ec2_instance.yml.
    if component in ("389ds", "dirsrv"):
        file_component = "dirsrv"
    elif component == "aws_instance":
        file_component = "ec2_instance"
    else:
        file_component = component
    vars_path = env_dir / f"vars_{file_component}.yml"
    vault_path = env_dir / f"vault_{file_component}.yml"

    vars_data = load_yaml(vars_path)
    vault_data = load_yaml(vault_path)
    vars_data_changed = False
    vault_data_changed = False

    public_values = {k: v for k, v in cfg.items() if not is_secret_key(k)}
    secret_values = {k: v for k, v in cfg.items() if is_secret_key(k)}
    passthrough_public_values = copy.deepcopy(public_values)

    quoted_public_keys = {
        "activation_key",
        "admin_activation_key",
        "admin_rhn_activation_key",
        "rhn_activation_key",
        "rhn_org_id",
        "org_id",
        "redhat_org_id",
        "satellite_install_rhn_activation_key",
        "satellite_install_rhn_org_id",
        "satellite_admin_rhn_activation_key",
        "satellite_rhn_org_id",
    }
    for quoted_key in quoted_public_keys:
        if quoted_key in public_values and public_values[quoted_key] is not None:
            public_values[quoted_key] = QuotedString(str(public_values[quoted_key]))

    if component == "satellite":
        satellite_role_only_keys = {
            "activation_key",
            "admin_activation_key",
            "admin_rhn_activation_key",
            "rhn_activation_key",
            "rhn_org_id",
            "org_id",
            "redhat_org_id",
            "satellite_install_rhn_activation_key",
            "satellite_install_rhn_org_id",
            "satellite_install_rhn_connected",
            "satellite_install_size",
            "satellite_install_size_profile",
            "satellite_install_min_memory_size",
            "satellite_install_min_cpu_count",
            "satellite_install_vg_name",
            "satellite_install_req_dirs",
            "satellite_install_data_device",
            "satellite_install_data_device_name",
            "satellite_install_data_disk_min_size",
            "satellite_config_manifest_file",
            "satellite_config_manifest_src",
            "satellite_config_manifest_path",
            "satellite_config_manifest_organization",
            "satellite_config_upload_manifest",
            "satellite_config_rhn_connected",
            "rhn_connected",
            "satellite_install_manifest_file",
            "satellite_install_manifest_path",
            "satellite_install_manifest_organization",
            "satellite_rhn_org_id",
            "satellite_manifest_file",
            "satellite_manifest_path",
            "satellite_manifest_organization",
            "manifest_file",
            "manifest_path",
            "manifest_filename",
            "manifest_organization",
            "manifest_encoding",
            "satellite_data_device",
            "satellite_data_device_name",
            "satellite_data_disk_min_size",
            "satellite_vg_name",
            "data_device",
            "data_device_name",
            "data_disk_min_size",
            "size",
            "req_dirs",
            "vg_name",
            "vgname",
            "oidc",
            "oidc_client_id",
            "oidc_realm",
            "oidc_keycloak_url",
            "oidc_issuer",
            "keycloak_url",
            "keycloak_admin_user",
            "capsule_hostname",
            "capsule_install_deployment_version",
            "capsule_install_location",
            "capsule_install_org_id",
            "capsule_install_activation_key",
            "capsule_install_satellite_fqdn",
            "capsule_install_min_memory_size",
            "capsule_install_min_cpu_count",
            "capsule_install_data_disk_min_size",
            "capsule_install_pulp_size",
            "capsule_install_pgsql_size",
            "capsule_install_data_device",
            "capsule_install_data_device_name",
            "capsule_install_vg_name",
            "capsule_install_req_dirs",
            "capsule_install_lifecycle_environments",
            "capsule_install_sync_wait_time",
            "capsule_install_setup_insights",
            "capsule_install_satellite_haproxy",
            "capsule_install_loadbalancer_fqdn",
            "capsule_install_loadbalancer_activation_key",
            "capsule_activation_key",
            "capsule_org_id",
            "capsule_location",
            "capsule_vg_name",
            "capsule_data_device",
            "capsule_data_device_name",
            "capsule_data_disk_min_size",
            "capsule_pulp_size",
            "capsule_pgsql_size",
            "loadbalancer_fqdn",
            "loadbalancer_activation_key",
            "satellite_haproxy",
            "lifecycle_environments",
        }
        satellite_stale_raw_keys = {
            "activation_key",
            "admin_activation_key",
            "admin_rhn_activation_key",
            "rhn_activation_key",
            "rhn_org_id",
            "org_id",
            "redhat_org_id",
            "satellite_install_rhn_activation_key",
            "satellite_install_rhn_org_id",
            "satellite_install_rhn_connected",
            "satellite_install_size",
            "satellite_install_size_profile",
            "satellite_install_min_memory_size",
            "satellite_install_min_cpu_count",
            "satellite_install_vg_name",
            "satellite_install_req_dirs",
            "satellite_install_data_device",
            "satellite_install_data_device_name",
            "satellite_install_data_disk_min_size",
            "satellite_config_manifest_file",
            "satellite_config_manifest_src",
            "satellite_config_manifest_path",
            "satellite_config_manifest_organization",
            "satellite_config_upload_manifest",
            "satellite_config_rhn_connected",
            "rhn_connected",
            "satellite_install_manifest_file",
            "satellite_install_manifest_path",
            "satellite_install_manifest_organization",
            "satellite_rhn_org_id",
            "satellite_manifest_file",
            "satellite_manifest_path",
            "satellite_manifest_organization",
            "manifest_file",
            "manifest_path",
            "manifest_filename",
            "manifest_organization",
            "manifest_encoding",
            "satellite_data_device",
            "satellite_data_device_name",
            "satellite_data_disk_min_size",
            "satellite_vg_name",
            "data_device",
            "data_device_name",
            "data_disk_min_size",
            "size",
            "req_dirs",
            "vg_name",
            "vgname",
            "oidc",
            "oidc_client_id",
            "oidc_realm",
            "oidc_keycloak_url",
            "oidc_issuer",
            "keycloak_url",
            "keycloak_admin_user",
            "capsule_hostname",
            "capsule_install_deployment_version",
            "capsule_install_location",
            "capsule_install_org_id",
            "capsule_install_activation_key",
            "capsule_install_satellite_fqdn",
            "capsule_install_min_memory_size",
            "capsule_install_min_cpu_count",
            "capsule_install_data_disk_min_size",
            "capsule_install_pulp_size",
            "capsule_install_pgsql_size",
            "capsule_install_data_device",
            "capsule_install_data_device_name",
            "capsule_install_vg_name",
            "capsule_install_req_dirs",
            "capsule_install_lifecycle_environments",
            "capsule_install_sync_wait_time",
            "capsule_install_setup_insights",
            "capsule_install_satellite_haproxy",
            "capsule_install_loadbalancer_fqdn",
            "capsule_install_loadbalancer_activation_key",
            "capsule_activation_key",
            "capsule_org_id",
            "capsule_location",
            "capsule_vg_name",
            "capsule_data_device",
            "capsule_data_device_name",
            "capsule_data_disk_min_size",
            "capsule_pulp_size",
            "capsule_pgsql_size",
            "loadbalancer_fqdn",
            "loadbalancer_activation_key",
            "satellite_haproxy",
            "lifecycle_environments",
        }
        for satellite_key in satellite_role_only_keys:
            passthrough_public_values.pop(satellite_key, None)
        for satellite_key in satellite_stale_raw_keys:
            vars_data.pop(satellite_key, None)
            vault_data.pop(satellite_key, None)
        existing_satellite_config = copy.deepcopy(
            vars_data.get("component_config", {}).get(component, {})
        )
        for satellite_key in satellite_stale_raw_keys:
            existing_satellite_config.pop(satellite_key, None)
        satellite_manifest_payload_keys = {
            "satellite_manifest_content",
            "satellite_manifest_content_base64",
            "satellite_manifest_b64",
            "manifest_content",
            "manifest_content_base64",
            "manifest_b64",
        }
    elif component == "aap":
        aap_role_only_keys = {
            "deployment_version",
            "version",
            "namespace",
            "create_namespace",
            "operator_channel",
            "operator_approval",
            "operator_scope",
            "instance_name",
            "component_deployment",
            "minimal_footprint",
            "admin_username",
            "install_controller",
            "install_hub",
            "install_eda",
            "install_lightspeed",
            "controller_replicas",
            "hub_storage_type",
            "hub_storage_class",
            "hub_storage_size",
            "hub_s3_secret",
            "hub_azure_secret",
            "platform_manifest_overrides",
            "controller_manifest_overrides",
            "hub_manifest_overrides",
            "eda_manifest_overrides",
            "license_mode",
            "subscription_manifest_file",
            "subscription_manifest_content_base64",
            "subscription_manifest_encoding",
            "rhn_username",
            "rhn_password",
            "rhn_subscription_id",
            "rhn_client_id",
            "rhn_client_secret",
        }
        for aap_key in aap_role_only_keys:
            passthrough_public_values.pop(aap_key, None)
            vars_data.pop(aap_key, None)
        existing_satellite_config = {}
    elif component == "rhbk":
        for rhbk_key in (
            "standalone_zip_upload_path",
            "standalone_zip_content_base64",
        ):
            passthrough_public_values.pop(rhbk_key, None)
            vars_data.pop(rhbk_key, None)
        _rhbk_opts = [
            str(x).strip().lower()
            for x in ((preflight.get("component_options") or {}).get("rhbk") or [])
        ]
        if "standalone" not in _rhbk_opts:
            pop_all_standalone_keys(passthrough_public_values)
            pop_all_standalone_keys(vars_data)
        existing_satellite_config = {}
    elif component == "grafana":
        _grafana_opts = [
            str(x).strip().lower()
            for x in ((preflight.get("component_options") or {}).get("grafana") or [])
        ]
        if "standalone" not in _grafana_opts:
            pop_all_standalone_keys(passthrough_public_values)
            pop_all_standalone_keys(vars_data)
        existing_satellite_config = {}
    elif component == "gitlab":
        _gitlab_opts = [
            str(x).strip().lower()
            for x in ((preflight.get("component_options") or {}).get("gitlab") or [])
        ]
        if "standalone" not in _gitlab_opts:
            pop_all_standalone_keys(passthrough_public_values)
            pop_all_standalone_keys(vars_data)
        existing_satellite_config = {}
    elif component == "ec2_ami_copy":
        for ec2_key in (
            "source_region",
            "dest_region",
            "source_image_id",
            "name",
            "description",
            "kms_key_id",
            "wait",
            "wait_timeout",
            "encrypted",
            "copy_image_tags",
            "tag_equality",
            "tags",
        ):
            passthrough_public_values.pop(ec2_key, None)
        existing_satellite_config = {}
    elif component in ("ec2_instance", "aws_instance"):
        for ec2_key in (
            "name",
            "image_id",
            "instance_type",
            "region",
            "vpc_subnet_id",
            "security_group",
            "key_name",
            "state",
            "wait",
            "wait_timeout",
        ):
            passthrough_public_values.pop(ec2_key, None)
        existing_satellite_config = {}
    elif component == "aws":
        for aws_key in (
            "profile",
            "default_region",
            "access_key_id",
            "secret_access_key",
            "session_token",
            "awspca_access_key_id",
            "awspca_secret_access_key",
        ):
            passthrough_public_values.pop(aws_key, None)
        existing_satellite_config = {}
    else:
        existing_satellite_config = {}

    if public_values:
        vars_data.setdefault("component_config", {})
        existing_component_config = (
            existing_satellite_config
            if component == "satellite"
            else copy.deepcopy(vars_data["component_config"].get(component, {}))
        )
        vars_data["component_config"][component] = {
            **existing_component_config,
            **copy.deepcopy(
                public_values
                if component in ("aws", "ec2_ami_copy", "ec2_instance", "aws_instance")
                else passthrough_public_values
            ),
        }

        for k, v in passthrough_public_values.items():
            vars_data[k] = copy.deepcopy(v)

        if component == "grafana":
            vars_data.setdefault("components_env", {}).setdefault("grafana", {})
            if public_values.get("storage"):
                if apply_storage_var(
                    vars_data,
                    "grafana",
                    preflight,
                    public_values["storage"],
                    vars_data_changed,
                ):
                    vars_data_changed = True
            if public_values.get("folder_name"):
                vars_data["components_env"]["grafana"]["grafana_folder"] = public_values["folder_name"]
            if public_values.get("hostname"):
                vars_data["components_env"]["grafana"]["hostname"] = public_values["hostname"]
            folders = public_values.get("folders")
            if isinstance(folders, list):
                vars_data["grafana_folders"] = copy.deepcopy(folders)
                vars_data["components_env"]["grafana"]["grafana_folders"] = copy.deepcopy(folders)
            datasources = public_values.get("datasources")
            if isinstance(datasources, list):
                normalized_ds = []
                for idx, ds_item in enumerate(datasources):
                    if not isinstance(ds_item, dict):
                        continue
                    ds_copy = copy.deepcopy(ds_item)
                    bearer = ds_copy.pop("bearer_token", None)
                    if not bearer:
                        secret_ds = secret_values.get("datasources")
                        if (
                            isinstance(secret_ds, list)
                            and idx < len(secret_ds)
                            and isinstance(secret_ds[idx], dict)
                        ):
                            bearer = secret_ds[idx].get("bearer_token")
                    if bearer:
                        vault_key = f"vault_grafana_ds_{idx}_bearer_token"
                        vault_data[vault_key] = QuotedString(str(bearer))
                        ds_copy["bearer_token"] = vault_ref(vault_key)
                        vault_data_changed = True
                    normalized_ds.append(ds_copy)
                vars_data["grafana_datasources"] = copy.deepcopy(normalized_ds)
                vars_data["components_env"]["grafana"]["grafana_datasources"] = (
                    copy.deepcopy(normalized_ds)
                )
            datasource_sources = public_values.get("datasource_sources")
            if isinstance(datasource_sources, list):
                vars_data["grafana_datasource_sources"] = copy.deepcopy(
                    datasource_sources
                )
                vars_data["components_env"]["grafana"][
                    "grafana_datasource_sources"
                ] = copy.deepcopy(datasource_sources)
            email = public_values.get("email") or public_values.get("grafana_email")
            if isinstance(email, dict):
                normalized_email = {
                    "enabled": email.get("enabled"),
                    "host": first_present(email.get("host"), email.get("smtp_host")),
                    "port": first_present(email.get("port"), email.get("smtp_port"), 587),
                    "user": first_present(email.get("user"), email.get("smtp_user")),
                    "password": first_present(
                        email.get("password"), email.get("smtp_password")
                    ),
                    "from_address": email.get("from_address"),
                    "from_name": email.get("from_name", "Grafana"),
                }
                vars_data["grafana_email"] = copy.deepcopy(normalized_email)
                vars_data["components_env"]["grafana"]["grafana_email"] = copy.deepcopy(
                    normalized_email
                )
            oidc = public_values.get("oidc")
            if isinstance(oidc, dict):
                vars_data["oidc"] = copy.deepcopy(oidc)
                vars_data["components_env"]["grafana"]["oidc"] = copy.deepcopy(oidc)
            grafana_opts = (
                (preflight.get("component_options") or {}).get("grafana") or []
            )
            grafana_opts_lower = [str(x).strip().lower() for x in grafana_opts]
            grafana_standalone = "standalone" in grafana_opts_lower
            if (
                rhbk_selected_in_preflight(preflight)
                and not grafana_standalone
                and "oidc" in grafana_opts_lower
            ):
                oidc_cfg = vars_data.get("oidc")
                if not isinstance(oidc_cfg, dict):
                    oidc_cfg = {}
                if oidc_cfg.get("enabled") is not True:
                    oidc_cfg = {
                        **oidc_cfg,
                        "enabled": True,
                        "client_id": oidc_cfg.get("client_id") or "grafana-client",
                        "client_secret": oidc_cfg.get("client_secret") or "",
                        "scopes": oidc_cfg.get("scopes")
                        or ["openid", "profile", "email", "groups"],
                        "default_role": oidc_cfg.get("default_role") or "Viewer",
                        "role_map": oidc_cfg.get("role_map")
                        or [
                            {"group": "ocp-cluster-admin", "role": "GrafanaAdmin"},
                            {"group": "ocp-cluster-devel", "role": "Viewer"},
                            {"group": "ocp-cluster-ops", "role": "Editor"},
                            {"group": "ocp-cluster-readonly", "role": "Viewer"},
                        ],
                    }
                    issuer, _realm = rhbk_oidc_issuer_url(preflight, vars_data)
                    if issuer and not oidc_cfg.get("issuer"):
                        oidc_cfg["issuer"] = issuer
                    vars_data["oidc"] = copy.deepcopy(oidc_cfg)
                    vars_data["components_env"]["grafana"]["oidc"] = copy.deepcopy(
                        oidc_cfg
                    )
                    vars_data_changed = True
            if "alerts_enabled" in public_values:
                vars_data["grafana_alerts_enabled"] = as_bool(public_values.get("alerts_enabled"), False)
                vars_data["components_env"]["grafana"]["grafana_alerts_enabled"] = vars_data["grafana_alerts_enabled"]
            elif "alerts" in grafana_opts_lower:
                vars_data["grafana_alerts_enabled"] = True
                vars_data["components_env"]["grafana"]["grafana_alerts_enabled"] = True
            grafana_api_key = first_present(
                secret_values.get("api_key"),
                secret_values.get("grafana_api_key"),
            )
            if grafana_api_key:
                vars_data["grafana_api_key"] = vault_ref("vault_grafana_api_key")
                vault_data["vault_grafana_api_key"] = QuotedString(str(grafana_api_key))
                vault_data_changed = True
            if "group_cluster_dashboards" in public_values:
                vars_data["grafana_group_cluster_dashboards"] = as_bool(
                    public_values.get("group_cluster_dashboards"), True
                )
                vars_data["components_env"]["grafana"]["grafana_group_cluster_dashboards"] = (
                    vars_data["grafana_group_cluster_dashboards"]
                )
            # OpenShift route hostname wins. Standalone VM hostname only when option selected.
            ocp_grafana_host = first_present(public_values.get("hostname"))
            if ocp_grafana_host:
                host_clean = re.sub(
                    r"^https?://", "", str(ocp_grafana_host)
                ).split("/")[0].strip()
                if host_clean:
                    vars_data["grafana_hostname"] = host_clean
                    vars_data["grafana_install_hostname"] = host_clean
                    vars_data["components_env"]["grafana"]["hostname"] = host_clean
                    vars_data["hostname"] = host_clean
            if grafana_standalone:
                standalone_hostname = first_present(public_values.get("standalone_hostname"))
                if standalone_hostname:
                    vars_data["install_grafana_hostname"] = str(standalone_hostname)
                    if not vars_data.get("grafana_hostname"):
                        vars_data["grafana_hostname"] = str(standalone_hostname)
                rpm_path = first_present(public_values.get("standalone_rpm_path"))
                if rpm_path:
                    vars_data["grafana_rpm_path"] = str(rpm_path)
                    vars_data["install_grafana_rpm_path"] = str(rpm_path)
                rpm_url = first_present(public_values.get("standalone_rpm_url"))
                if rpm_url:
                    vars_data["grafana_rpm_url"] = str(rpm_url)
                    vars_data["install_grafana_rpm_url"] = str(rpm_url)
            # Community catalog channel is "v5" — version strings like 5.20.0 never resolve.
            vars_data["operator_channel"] = "v5"
            vars_data["operator_name"] = "grafana-operator"
            vars_data["operator_source"] = "community-operators"
            vars_data["operator_source_namespace"] = "openshift-marketplace"
            vars_data["operator_csv_contains"] = "grafana-operator"
            vars_data["operator_name_substring"] = "grafana-operator"
            vars_data.setdefault("components_env", {}).setdefault("grafana", {})
            vars_data["components_env"]["grafana"]["operator_channel"] = "v5"
            vars_data.setdefault("component_config", {}).setdefault("grafana", {})
            vars_data["component_config"]["grafana"]["operator_channel"] = "v5"
            vars_data_changed = True
            if grafana_standalone:
                rhn_org = first_present(public_values.get("standalone_rhn_org_id"))
                if rhn_org:
                    vars_data["install_grafana_rhn_org_id"] = str(rhn_org)
                rhn_key = first_present(secret_values.get("standalone_rhn_activation_key"))
                if rhn_key:
                    vars_data["install_grafana_rhn_activation_key"] = vault_ref(
                        "vault_grafana_rhn_activation_key"
                    )
                    vault_data["vault_grafana_rhn_activation_key"] = QuotedString(str(rhn_key))
                    vault_data_changed = True
            # OCP Grafana admin (UI admin_password; standalone_admin_password only if standalone).
            grafana_admin_user = first_present(
                public_values.get("admin_user"),
                public_values.get("standalone_admin_user") if grafana_standalone else None,
                "admin",
            )
            if grafana_admin_user:
                vars_data["grafana_admin_user"] = str(grafana_admin_user)
                vars_data["grafana_install_admin_user"] = str(grafana_admin_user)
            grafana_admin_password = first_present(
                secret_values.get("admin_password"),
                secret_values.get("grafana_admin_password"),
                secret_values.get("standalone_admin_password") if grafana_standalone else None,
            )
            if grafana_admin_password:
                vars_data["grafana_admin_password"] = vault_ref(
                    "vault_grafana_admin_password"
                )
                vars_data["grafana_install_admin_password"] = vault_ref(
                    "vault_grafana_admin_password"
                )
                vault_data["vault_grafana_admin_password"] = QuotedString(
                    str(grafana_admin_password)
                )
                vault_data["grafana_admin_password"] = QuotedString(
                    str(grafana_admin_password)
                )
                vault_data_changed = True
            elif not first_present(
                vars_data.get("grafana_admin_password"),
                vault_data.get("vault_grafana_admin_password"),
                vault_data.get("grafana_admin_password"),
            ):
                # Match components_defaults lab password so datasource assert passes.
                vars_data["grafana_admin_password"] = "redhat123"
                vars_data["grafana_install_admin_password"] = "redhat123"
                vars_data_changed = True
            if not grafana_standalone:
                purge_standalone_install_vars(vars_data, "grafana")
                vars_data_changed = True

        if component == "gitlab":
            gitlab_opts = (
                (preflight.get("component_options") or {}).get("gitlab") or []
            )
            gitlab_standalone = "standalone" in [
                str(x).strip().lower() for x in gitlab_opts
            ]
            ocp_gitlab_host = first_present(public_values.get("hostname"))
            if ocp_gitlab_host:
                host_clean = strip_host(ocp_gitlab_host)
                if host_clean:
                    vars_data["gitlab_hostname"] = host_clean
                    vars_data["gitlab_install_hostname"] = host_clean
                    vars_data["hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("gitlab", {})
                    vars_data["components_env"]["gitlab"]["hostname"] = host_clean
                    vars_data_changed = True
            if public_values.get("storage"):
                if apply_storage_var(
                    vars_data,
                    "gitlab",
                    preflight,
                    public_values["storage"],
                    vars_data_changed,
                ):
                    vars_data_changed = True
            standalone_hostname = first_present(public_values.get("standalone_hostname"))
            if gitlab_standalone and standalone_hostname:
                vars_data["gitlab_hostname"] = str(standalone_hostname)
                vars_data["install_gitlab_hostname"] = str(standalone_hostname)
            external_url = (
                first_present(public_values.get("standalone_external_url"))
                if gitlab_standalone
                else None
            )
            if external_url:
                vars_data["gitlab_external_url"] = str(external_url)
                vars_data["install_gitlab_external_url"] = str(external_url)
            edition = (
                first_present(public_values.get("standalone_edition"))
                if gitlab_standalone
                else None
            )
            if edition:
                vars_data["gitlab_edition"] = str(edition)
                vars_data["install_gitlab_edition"] = str(edition)
            rpm_path = first_present(public_values.get("standalone_rpm_path")) if gitlab_standalone else None
            if rpm_path:
                vars_data["gitlab_rpm_path"] = str(rpm_path)
                vars_data["install_gitlab_rpm_path"] = str(rpm_path)
            rpm_url = first_present(public_values.get("standalone_rpm_url")) if gitlab_standalone else None
            if rpm_url:
                vars_data["gitlab_rpm_url"] = str(rpm_url)
                vars_data["install_gitlab_rpm_url"] = str(rpm_url)
            if gitlab_standalone and secret_values.get("standalone_root_password"):
                vars_data["gitlab_root_password"] = vault_ref("vault_gitlab_root_password")
                vault_data["vault_gitlab_root_password"] = QuotedString(
                    str(secret_values.get("standalone_root_password"))
                )
                vault_data["gitlab_root_password"] = QuotedString(
                    str(secret_values.get("standalone_root_password"))
                )
                vault_data_changed = True
            tls_crt = (
                first_present(
                    secret_values.get("standalone_tls_crt"),
                    public_values.get("standalone_tls_crt"),
                )
                if gitlab_standalone
                else None
            )
            tls_key = (
                first_present(secret_values.get("standalone_tls_key"))
                if gitlab_standalone
                else None
            )
            if tls_crt:
                vars_data["gitlab_tls_crt"] = vault_ref("vault_gitlab_tls_crt")
                vault_data["vault_gitlab_tls_crt"] = QuotedString(str(tls_crt))
                vault_data["gitlab_tls_crt"] = QuotedString(str(tls_crt))
                vault_data_changed = True
            if tls_key:
                vars_data["gitlab_tls_key"] = vault_ref("vault_gitlab_tls_key")
                vault_data["vault_gitlab_tls_key"] = QuotedString(str(tls_key))
                vault_data["gitlab_tls_key"] = QuotedString(str(tls_key))
                vault_data_changed = True
            rhn_org = first_present(public_values.get("standalone_rhn_org_id")) if gitlab_standalone else None
            if rhn_org:
                vars_data["install_gitlab_rhn_org_id"] = str(rhn_org)
                vars_data["gitlab_rhn_org_id"] = str(rhn_org)
            rhn_key = (
                first_present(secret_values.get("standalone_rhn_activation_key"))
                if gitlab_standalone
                else None
            )
            if rhn_key:
                vars_data["install_gitlab_rhn_activation_key"] = vault_ref(
                    "vault_gitlab_rhn_activation_key"
                )
                vault_data["vault_gitlab_rhn_activation_key"] = QuotedString(str(rhn_key))
                vault_data_changed = True

            if not gitlab_standalone:
                purge_standalone_install_vars(vars_data, "gitlab")
                vars_data_changed = True

        if component == "zabbix":
            ocp_host = first_present(public_values.get("hostname"))
            if ocp_host:
                host_clean = re.sub(
                    r"^https?://", "", str(ocp_host)
                ).split("/")[0].strip()
                if host_clean:
                    vars_data["zabbix_hostname"] = host_clean
                    vars_data["hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("zabbix", {})
                    vars_data["components_env"]["zabbix"]["hostname"] = host_clean
                    vars_data_changed = True
            if public_values.get("storage"):
                if apply_storage_var(
                    vars_data,
                    "zabbix",
                    preflight,
                    public_values["storage"],
                    vars_data_changed,
                ):
                    vars_data_changed = True
            if rhbk_selected_in_preflight(preflight):
                zabbix_issuer, zabbix_realm = rhbk_oidc_issuer_url(preflight, vars_data)
                if zabbix_issuer:
                    vars_data["zabbix_saml_idp_metadata_url"] = (
                        f"{zabbix_issuer}/protocol/saml/descriptor"
                    )
                    vars_data["zabbix_saml_sp_entity_id"] = (
                        f"https://{strip_host(ocp_host or vars_data.get('zabbix_hostname') or 'zabbix')}/"
                    )
                if public_values.get("saml_enabled") is not None:
                    vars_data["zabbix_saml_enabled"] = as_bool(
                        public_values.get("saml_enabled"), True
                    )
                elif public_values.get("oidc_enabled") is not None:
                    vars_data["zabbix_saml_enabled"] = as_bool(
                        public_values.get("oidc_enabled"), True
                    )
                else:
                    vars_data["zabbix_saml_enabled"] = True
                vars_data.setdefault("components_env", {}).setdefault("zabbix", {})
                vars_data["components_env"]["zabbix"]["saml_enabled"] = vars_data[
                    "zabbix_saml_enabled"
                ]
                vars_data_changed = True

        if component == "dev_hub":
            ocp_host = first_present(public_values.get("hostname"))
            if ocp_host:
                host_clean = re.sub(
                    r"^https?://", "", str(ocp_host)
                ).split("/")[0].strip()
                if host_clean:
                    vars_data["dev_hub_hostname"] = host_clean
                    vars_data["hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("dev_hub", {})
                    vars_data["components_env"]["dev_hub"]["hostname"] = host_clean
                    vars_data_changed = True
            gitlab_host = first_present(public_values.get("gitlab_host"))
            if gitlab_host:
                gitlab_clean = re.sub(
                    r"^https?://", "", str(gitlab_host)
                ).split("/")[0].strip()
                if gitlab_clean:
                    vars_data.setdefault("components_env", {}).setdefault("dev_hub", {})
                    vars_data["components_env"]["dev_hub"]["gitlab_host"] = gitlab_clean
                    vars_data_changed = True
            rhbk_cfg = (preflight.get("component_config") or {}).get("rhbk") or {}
            dev_realm = first_present(
                rhbk_cfg.get("realm"),
                public_values.get("keycloak_realm"),
                env_label_suffix(preflight.get("environment")),
                "rhlab",
            )
            rhbk_host = strip_host(
                first_present(
                    rhbk_cfg.get("hostname"),
                    ((preflight.get("openshift") or {}).get("apps_domain") and f"keycloak.{((preflight.get('openshift') or {}).get('apps_domain'))}"),
                )
            )
            if rhbk_host:
                vars_data["keycloak_hostname"] = rhbk_host
                vars_data["rhbk_hostname"] = rhbk_host
                vars_data["ocp_rhbk_hostname"] = rhbk_host
                vars_data.setdefault("components_env", {}).setdefault("dev_hub", {})
                vars_data["components_env"]["dev_hub"]["keycloak_hostname"] = rhbk_host
                vars_data_changed = True
            dev_client = first_present(
                public_values.get("keycloak_client_id"),
                "rhdh",
            )
            dev_instance = first_present(public_values.get("instance_name"), "chad-lab")
            if dev_realm:
                vars_data["dev_hub_keycloak_realm"] = str(dev_realm)
                vars_data.setdefault("components_env", {}).setdefault("dev_hub", {})
                vars_data["components_env"]["dev_hub"]["keycloak_realm"] = str(dev_realm)
                vars_data_changed = True
            if dev_client:
                vars_data["dev_hub_keycloak_client_id"] = str(dev_client)
                vars_data["components_env"]["dev_hub"]["keycloak_client_id"] = str(dev_client)
                vars_data_changed = True
            if dev_instance:
                vars_data["dev_hub_instance_name"] = str(dev_instance)
                vars_data["components_env"]["dev_hub"]["instance_name"] = str(dev_instance)
                vars_data_changed = True
            catalog_url = first_present(public_values.get("catalog_url"))
            if catalog_url:
                vars_data["dev_hub_catalog_url"] = str(catalog_url)
                vars_data["components_env"]["dev_hub"]["catalog_url"] = str(catalog_url)
                vars_data_changed = True
            oidc_secret = first_present(public_values.get("oidc_client_secret"))
            if oidc_secret:
                vars_data["dev_hub_oidc_client_secret"] = vault_ref("vault_dev_hub_oidc_client_secret")
                vault_data["vault_dev_hub_oidc_client_secret"] = QuotedString(str(oidc_secret))
                vars_data_changed = True
            gitlab_token = first_present(
                public_values.get("gitlab_token"),
                ((preflight.get("component_config") or {}).get("dev_hub") or {}).get(
                    "gitlab_token"
                ),
                (preflight.get("git") or {}).get("token"),
            )
            if gitlab_token:
                vars_data["dev_hub_gitlab_token"] = vault_ref("vault_dev_hub_gitlab_token")
                vault_data["vault_dev_hub_gitlab_token"] = QuotedString(str(gitlab_token))
                vars_data_changed = True

        if component == "quay":
            quay_host = first_present(public_values.get("hostname"))
            if quay_host:
                host_clean = re.sub(
                    r"^https?://", "", str(quay_host)
                ).split("/")[0].strip()
                if host_clean:
                    vars_data["ocp_quay_hostname"] = host_clean
                    vars_data["quay_hostname"] = host_clean
                    vars_data["hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("quay", {})
                    vars_data["components_env"]["quay"]["hostname"] = host_clean
                    vars_data_changed = True
            if public_values.get("oidc_enabled") is not None:
                vars_data["quay_oidc_enabled"] = as_bool(
                    public_values.get("oidc_enabled"), True
                )
                vars_data_changed = True
            if public_values.get("oidc_client_id"):
                vars_data["quay_oidc_client_id"] = str(public_values.get("oidc_client_id"))
                vars_data_changed = True
            if public_values.get("keycloak_realm"):
                vars_data["quay_keycloak_realm"] = str(public_values.get("keycloak_realm"))
                vars_data_changed = True
            oidc_secret = first_present(
                secret_values.get("oidc_client_secret"),
                public_values.get("oidc_client_secret"),
            )
            if oidc_secret and not as_bool(
                public_values.get("fetch_oidc_secret_from_rhbk"), True
            ):
                vars_data["quay_oidc_client_secret"] = vault_ref(
                    "vault_quay_oidc_client_secret"
                )
                vault_data["vault_quay_oidc_client_secret"] = QuotedString(str(oidc_secret))
                vault_data_changed = True
            quay_issuer, quay_realm = rhbk_oidc_issuer_url(preflight, vars_data)
            if quay_issuer:
                vars_data["quay_oidc_issuer_url"] = quay_issuer
                vars_data.setdefault("components_env", {}).setdefault("quay", {})
                vars_data["components_env"]["quay"]["oidc_issuer_url"] = quay_issuer
                vars_data_changed = True
            if str(vars_data.get("quay_oidc_issuer_url", "")).strip() == "":
                vars_data.pop("quay_oidc_issuer_url", None)
                if "quay" in vars_data.get("components_env", {}):
                    vars_data["components_env"]["quay"].pop("oidc_issuer_url", None)

        if component == "minio":
            console_host = first_present(
                public_values.get("console_hostname"),
                public_values.get("hostname"),
            )
            api_host = first_present(public_values.get("api_hostname"))
            if console_host:
                host_clean = re.sub(
                    r"^https?://", "", str(console_host)
                ).split("/")[0].strip()
                if host_clean:
                    vars_data["minio_console_hostname"] = host_clean
                    vars_data["hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("minio", {})
                    vars_data["components_env"]["minio"]["console_hostname"] = host_clean
                    vars_data["components_env"]["minio"]["hostname"] = host_clean
                    vars_data_changed = True
            if api_host:
                api_clean = re.sub(
                    r"^https?://", "", str(api_host)
                ).split("/")[0].strip()
                if api_clean:
                    vars_data["minio_api_hostname"] = api_clean
                    vars_data.setdefault("components_env", {}).setdefault("minio", {})
                    vars_data["components_env"]["minio"]["api_hostname"] = api_clean
                    vars_data_changed = True
            if public_values.get("storage"):
                if apply_storage_var(
                    vars_data,
                    "minio",
                    preflight,
                    public_values["storage"],
                    vars_data_changed,
                ):
                    vars_data_changed = True
            rhbk_cfg = (preflight.get("component_config") or {}).get("rhbk") or {}
            minio_realm = first_present(
                public_values.get("keycloak_realm"),
                rhbk_cfg.get("realm"),
                rhbk_cfg.get("rhbk_realm"),
                vars_data.get("ocp_rhbk_realm"),
                vars_data.get("rhbk_realm"),
                env_label_suffix(preflight.get("environment")),
                "rhlab",
            )
            if minio_realm:
                vars_data["minio_keycloak_realm"] = str(minio_realm)
                vars_data.setdefault("components_env", {}).setdefault("minio", {})
                vars_data["components_env"]["minio"]["keycloak_realm"] = str(minio_realm)
                vars_data_changed = True
            minio_issuer, _minio_realm_from_rhbk = rhbk_oidc_issuer_url(preflight, vars_data)
            if minio_issuer:
                vars_data["minio_oidc_issuer"] = minio_issuer
                vars_data.setdefault("components_env", {}).setdefault("minio", {})
                vars_data["components_env"]["minio"]["oidc_issuer"] = minio_issuer
                vars_data.setdefault("component_config", {}).setdefault("minio", {})
                vars_data["component_config"]["minio"]["oidc_issuer"] = minio_issuer
                vars_data_changed = True
            oidc = public_values.get("oidc") or {}
            if oidc:
                vars_data.setdefault("components_env", {}).setdefault("minio", {})
                vars_data["components_env"]["minio"]["oidc"] = copy.deepcopy(oidc)
                if oidc.get("enabled") is not None:
                    vars_data["minio_oidc_enabled"] = as_bool(oidc.get("enabled"), True)
                if oidc.get("client_id"):
                    vars_data["minio_oidc_client_id"] = str(oidc.get("client_id"))
                vars_data_changed = True
            elif public_values.get("oidc_enabled") is not None:
                vars_data["minio_oidc_enabled"] = as_bool(public_values.get("oidc_enabled"), True)
                vars_data_changed = True
            root_user = first_present(public_values.get("root_user"))
            root_password = first_present(public_values.get("root_password"))
            if root_user:
                vars_data["minio_root_user"] = str(root_user)
                vars_data_changed = True
            if root_password:
                vars_data["minio_root_password"] = vault_ref("vault_minio_root_password")
                vault_data["vault_minio_root_password"] = QuotedString(str(root_password))
                vars_data_changed = True
            oidc_secret = first_present(
                public_values.get("oidc_client_secret"),
                (oidc or {}).get("client_secret"),
            )
            if oidc_secret:
                vars_data["minio_oidc_client_secret"] = vault_ref("vault_minio_oidc_client_secret")
                vault_data["vault_minio_oidc_client_secret"] = QuotedString(str(oidc_secret))
                vars_data_changed = True

        if component == "bookstack":
            route_host = first_present(
                public_values.get("route_host"),
                public_values.get("hostname"),
            )
            if route_host:
                route_clean = re.sub(
                    r"^https?://", "", str(route_host)
                ).split("/")[0].strip()
                if route_clean:
                    vars_data["bookstack_route_host"] = route_clean
                    vars_data["hostname"] = route_clean
                    vars_data.setdefault("components_env", {}).setdefault("bookstack", {})
                    vars_data["components_env"]["bookstack"]["route_host"] = route_clean
                    vars_data["components_env"]["bookstack"]["hostname"] = route_clean
                    vars_data_changed = True
            bookstack_issuer, _bookstack_realm = rhbk_oidc_issuer_url(preflight, vars_data)
            if bookstack_issuer:
                vars_data["bookstack_oidc_issuer"] = bookstack_issuer
                vars_data["oidc_issuer"] = bookstack_issuer
                vars_data.setdefault("components_env", {}).setdefault("bookstack", {})
                vars_data["components_env"]["bookstack"]["oidc_issuer"] = bookstack_issuer
                vars_data.setdefault("component_config", {}).setdefault("bookstack", {})
                vars_data["component_config"]["bookstack"]["oidc_issuer"] = bookstack_issuer
                vars_data_changed = True
            if public_values.get("oidc_client_id"):
                vars_data["bookstack_oidc_client_id"] = str(public_values["oidc_client_id"])
                vars_data_changed = True
            if public_values.get("oidc_enabled") is not None:
                vars_data["bookstack_oidc_enabled"] = as_bool(public_values.get("oidc_enabled"), True)
                vars_data_changed = True
            bookstack_oidc_secret = first_present(
                secret_values.get("oidc_client_secret"),
                public_values.get("oidc_client_secret"),
            )
            if bookstack_oidc_secret:
                vars_data["bookstack_oidc_client_secret"] = vault_ref("vault_bookstack_oidc_client_secret")
                vault_data["vault_bookstack_oidc_client_secret"] = QuotedString(str(bookstack_oidc_secret))
                vault_data_changed = True

        if component == "netbox":
            ocp_host = first_present(public_values.get("hostname"))
            if ocp_host:
                host_clean = re.sub(
                    r"^https?://", "", str(ocp_host)
                ).split("/")[0].strip()
                if host_clean:
                    vars_data["hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("netbox", {})
                    vars_data["components_env"]["netbox"]["hostname"] = host_clean
                    vars_data_changed = True
            netbox_issuer, _netbox_realm = rhbk_oidc_issuer_url(preflight, vars_data)
            if netbox_issuer:
                vars_data["netbox_oidc_issuer"] = netbox_issuer
                vars_data["oidc_issuer"] = netbox_issuer
                vars_data.setdefault("components_env", {}).setdefault("netbox", {})
                vars_data["components_env"]["netbox"]["oidc_issuer"] = netbox_issuer
                vars_data.setdefault("component_config", {}).setdefault("netbox", {})
                vars_data["component_config"]["netbox"]["oidc_issuer"] = netbox_issuer
                vars_data_changed = True
            if public_values.get("oidc_client_id"):
                vars_data["netbox_oidc_client_id"] = str(public_values["oidc_client_id"])
                vars_data_changed = True
            if public_values.get("oidc_enabled") is not None:
                vars_data["netbox_oidc_enabled"] = as_bool(public_values.get("oidc_enabled"), True)
                vars_data_changed = True
            netbox_oidc_secret = first_present(
                secret_values.get("oidc_client_secret"),
                public_values.get("oidc_client_secret"),
            )
            if netbox_oidc_secret:
                vars_data["netbox_oidc_client_secret"] = vault_ref("vault_netbox_oidc_client_secret")
                vault_data["vault_netbox_oidc_client_secret"] = QuotedString(str(netbox_oidc_secret))
                vault_data_changed = True

        if component == "rhbk":
            vars_data.setdefault("components_env", {}).setdefault("rhbk", {})
            rhbk_options = (preflight.get("component_options") or {}).get("rhbk", [])
            rhbk_opts_lower = [str(x).strip().lower() for x in (rhbk_options or [])]
            # UI always ships standalone_* form defaults — only honor them when
            # the standalone option is explicitly selected (same as Grafana/GitLab).
            rhbk_standalone_selected = "standalone" in rhbk_opts_lower
            if rhbk_standalone_selected:
                vars_data["install_rhbk_platform"] = "rhel"
                vars_data["rhbk_platform"] = "rhel"
                vars_data["components_env"]["rhbk"]["install_rhbk_platform"] = "rhel"
                vars_data["components_env"]["rhbk"]["rhbk_platform"] = "rhel"
                vars_data_changed = True
            else:
                purge_standalone_install_vars(vars_data, "rhbk")
                vars_data["install_rhbk_platform"] = "openshift"
                vars_data["rhbk_platform"] = "openshift"
                vars_data["components_env"]["rhbk"]["install_rhbk_platform"] = "openshift"
                vars_data["components_env"]["rhbk"]["rhbk_platform"] = "openshift"
                vars_data_changed = True
            env_suffix = env_label_suffix(preflight.get("environment"))
            apps_domain = str(
                ((preflight.get("openshift") or {}).get("apps_domain")) or ""
            ).strip()
            if public_values.get("storage"):
                vars_data["components_env"]["rhbk"]["storage"] = public_values["storage"]
            _realm = str(
                first_present(
                    public_values.get("realm"),
                    env_suffix if preflight.get("environment") else None,
                    "rhlab",
                )
                or "rhlab"
            )
            vars_data["rhbk_realm"] = _realm
            vars_data["ocp_rhbk_realm"] = _realm
            vars_data["components_env"]["rhbk"]["rhbk_realm"] = _realm
            vars_data["components_env"]["rhbk"]["ocp_rhbk_realm"] = _realm
            vars_data["components_env"]["rhbk"]["realm"] = _realm
            # Always enable realms by default (OIDC apps fail with "Realm not enabled").
            _realm_enabled = as_bool(
                first_present(
                    public_values.get("realm_enabled"),
                    public_values.get("rhbk_enabled"),
                    True,
                ),
                True,
            )
            vars_data["rhbk_enabled"] = _realm_enabled
            vars_data["components_env"]["rhbk"]["rhbk_enabled"] = _realm_enabled
            vars_data["components_env"]["rhbk"]["realm_enabled"] = _realm_enabled
            vars_data_changed = True
            _rhbk_host = strip_host(
                first_present(
                    public_values.get("standalone_hostname")
                    if rhbk_standalone_selected
                    else None,
                    public_values.get("hostname"),
                    f"keycloak.{apps_domain}" if apps_domain else None,
                )
            )
            if _rhbk_host:
                vars_data["components_env"]["rhbk"]["hostname"] = _rhbk_host
                # Federation / IdP / mapper / OIDC roles share this host.
                vars_data["rhbk_hostname"] = _rhbk_host
                vars_data["rhbk_host"] = _rhbk_host
                vars_data["ocp_rhbk_hostname"] = _rhbk_host
                vars_data["components_env"]["rhbk"]["rhbk_hostname"] = _rhbk_host
                vars_data["components_env"]["rhbk"]["rhbk_host"] = _rhbk_host
                vars_data["components_env"]["rhbk"]["ocp_rhbk_hostname"] = _rhbk_host
                vars_data_changed = True
            # Native RHBK user-event metrics (keycloak_user_events_total).
            _event_metrics = as_bool(
                first_present(
                    public_values.get("event_metrics_user_enabled"),
                    public_values.get("rhbk_event_metrics_user_enabled"),
                    False,
                ),
                False,
            )
            vars_data["install_rhbk_event_metrics_user_enabled"] = _event_metrics
            vars_data["rhbk_event_metrics_user_enabled"] = _event_metrics
            vars_data["event_metrics_user_enabled"] = _event_metrics
            vars_data["components_env"]["rhbk"][
                "event_metrics_user_enabled"
            ] = _event_metrics
            vars_data["components_env"]["rhbk"][
                "rhbk_event_metrics_user_enabled"
            ] = _event_metrics
            vars_data["install_rhbk_metrics_enabled"] = True
            vars_data["rhbk_metrics_enabled"] = True
            vars_data_changed = True
            _admin_user = str(
                first_present(
                    public_values.get("admin_user"),
                    public_values.get("standalone_admin_user"),
                    "admin",
                )
                or "admin"
            )
            vars_data["rhbk_admin_user"] = _admin_user
            vars_data["ocp_rhbk_admin_user"] = _admin_user
            vars_data["components_env"]["rhbk"]["rhbk_admin_user"] = _admin_user
            vars_data["components_env"]["rhbk"]["ocp_rhbk_admin_user"] = _admin_user
            _admin_password = first_present(
                secret_values.get("admin_password"),
                secret_values.get("standalone_admin_password"),
            )
            if _admin_password is not None and str(_admin_password).strip():
                vars_data["rhbk_admin_password"] = vault_ref("vault_rhbk_admin_password")
                vars_data["ocp_rhbk_admin_password"] = vault_ref("vault_rhbk_admin_password")
                vault_data["vault_rhbk_admin_password"] = QuotedString(str(_admin_password))
                vault_data["rhbk_admin_password"] = QuotedString(str(_admin_password))
                vault_data["ocp_rhbk_admin_password"] = QuotedString(str(_admin_password))
                vault_data_changed = True
            # TLS mode from preflight (edge default; cert-manager or manual PEM opt-in).
            tls_mode = str(
                first_present(public_values.get("tls_mode"), "edge")
            ).strip().lower()
            if tls_mode not in ("edge", "cert_manager", "ingress_copy", "manual"):
                tls_mode = "edge"
            use_cm = as_bool(public_values.get("cert_manager"), tls_mode == "cert_manager")
            use_ingress = as_bool(
                public_values.get("ocp_rhbk_use_default_ingress_cert"),
                tls_mode == "ingress_copy",
            )
            _ocp_tls_crt = first_present(
                secret_values.get("tls_crt"),
                public_values.get("tls_crt"),
            )
            _ocp_tls_key = first_present(
                secret_values.get("tls_key"),
                public_values.get("tls_key"),
            )
            use_manual = tls_mode == "manual" or (
                not use_cm
                and not use_ingress
                and _ocp_tls_crt
                and _ocp_tls_key
                and str(_ocp_tls_crt).strip()
                and str(_ocp_tls_key).strip()
            )
            use_edge = as_bool(
                public_values.get("ocp_rhbk_http_edge"),
                tls_mode == "edge" or (not use_cm and not use_ingress and not use_manual),
            )
            if use_cm:
                tls_mode = "cert_manager"
                use_ingress = False
                use_edge = False
                use_manual = False
            elif use_ingress:
                tls_mode = "ingress_copy"
                use_cm = False
                use_edge = False
                use_manual = False
            elif use_manual:
                tls_mode = "manual"
                use_cm = False
                use_ingress = False
                use_edge = False
            else:
                tls_mode = "edge"
                use_cm = False
                use_ingress = False
                use_manual = False
                use_edge = True
            vars_data["tls_mode"] = tls_mode
            vars_data["cert_manager"] = use_cm
            vars_data["ocp_rhbk_http_edge"] = use_edge
            vars_data["ocp_rhbk_use_default_ingress_cert"] = use_ingress
            vars_data["components_env"]["rhbk"]["tls_mode"] = tls_mode
            vars_data["components_env"]["rhbk"]["cert_manager"] = use_cm
            vars_data["components_env"]["rhbk"]["ocp_rhbk_http_edge"] = use_edge
            vars_data["components_env"]["rhbk"]["ocp_rhbk_use_default_ingress_cert"] = use_ingress
            if use_manual and _ocp_tls_crt and _ocp_tls_key:
                vars_data["tls_crt"] = vault_ref("vault_rhbk_tls_crt")
                vars_data["tls_key"] = vault_ref("vault_rhbk_tls_key")
                vault_data["vault_rhbk_tls_crt"] = QuotedString(str(_ocp_tls_crt))
                vault_data["vault_rhbk_tls_key"] = QuotedString(str(_ocp_tls_key))
                vault_data["tls_crt"] = QuotedString(str(_ocp_tls_crt))
                vault_data["tls_key"] = QuotedString(str(_ocp_tls_key))
                vault_data_changed = True
            issuer_kind = first_present(
                public_values.get("ocp_rhbk_issuer_kind"),
                public_values.get("issuer_kind"),
                "ClusterIssuer",
            )
            issuer_name = first_present(
                public_values.get("ocp_rhbk_issuer_name"),
                public_values.get("issuer_name"),
                "idm-acme",
            )
            if issuer_kind:
                vars_data["ocp_rhbk_issuer_kind"] = str(issuer_kind)
            if issuer_name:
                vars_data["ocp_rhbk_issuer_name"] = str(issuer_name)
            clients = public_values.get("clients")
            if isinstance(clients, list) and clients:
                rhbk_clients = {}
                for client in clients:
                    if not isinstance(client, dict):
                        continue
                    client_id = str(client.get("id") or client.get("client_id") or "").strip()
                    if not client_id:
                        continue

                    def _split(value):
                        if isinstance(value, list):
                            return [str(v).strip() for v in value if str(v).strip()]
                        return [part.strip() for part in str(value or "").replace("\n", ",").split(",") if part.strip()]
                    rhbk_clients[client_id] = {
                        "rhbk_client_name": str(client.get("name") or client_id),
                        "rhbk_redirect_uris": _split(client.get("redirect_uris")),
                        "rhbk_web_origins": _split(client.get("web_origins")),
                        "rhbk_default_client_scopes": ["groups"],
                        "rhbk_attach_default_client_scopes": True,
                    }
                if rhbk_clients:
                    vars_data["rhbk_clients"] = rhbk_clients
                    vars_data["components_env"]["rhbk"]["rhbk_clients"] = copy.deepcopy(rhbk_clients)
            if public_values.get("client"):
                vars_data["rhbk_client"] = str(public_values.get("client"))
            _oidc_client = first_present(
                public_values.get("openshift_oidc_client_id"),
                public_values.get("client"),
                vars_data.get("rhbk_client"),
            )
            clients = public_values.get("clients")
            if not _oidc_client and isinstance(clients, list):
                for client in clients:
                    if not isinstance(client, dict):
                        continue
                    client_id = str(client.get("id") or client.get("client_id") or "").strip()
                    if not client_id:
                        continue
                    source = str(client.get("source") or "").strip().lower()
                    if source == "openshift" or "openshift" in client_id.lower():
                        _oidc_client = client_id
                        break
                if not _oidc_client:
                    for client in clients:
                        if not isinstance(client, dict):
                            continue
                        client_id = str(client.get("id") or client.get("client_id") or "").strip()
                        if client_id:
                            _oidc_client = client_id
                            break
            if not _oidc_client:
                _oidc_client = f"Openshift{env_suffix}"
            _oidc_idp = str(
                first_present(
                    public_values.get("openshift_oidc_idp_name"),
                    ((preflight.get("openshift") or {}).get("oauth_rhbk") or {}).get(
                        "idp_name"
                    ),
                    "Keycloak",
                )
                or "Keycloak"
            )
            _issuer_host = _rhbk_host or strip_host(vars_data.get("ocp_rhbk_hostname"))
            oidc_auth = {
                "enabled": True,
                "keycloak_client_id": str(_oidc_client),
                "openshift_oidc_idp_name": _oidc_idp,
                "openshift_oidc_mapping_method": "claim",
                "openshift_oauth_resource_name": "cluster",
                "extra_scopes": ["groups"],
            }
            if _issuer_host:
                oidc_auth["issuer"] = f"https://{_issuer_host}/realms/{_realm}"
            if not rhbk_standalone_selected:
                vars_data["openshift_oidc_auth"] = oidc_auth
                vars_data["components_env"]["rhbk"]["openshift_oidc_auth"] = copy.deepcopy(oidc_auth)
                vars_data_changed = True
            # Standalone ZIP / hostname / TLS only when option is selected.
            # Do not let UI default standalone_hostname force platform=rhel on OCP.
            if rhbk_standalone_selected:
                standalone_hostname = first_present(public_values.get("standalone_hostname"))
                if standalone_hostname:
                    _standalone_host = str(standalone_hostname)
                    vars_data["rhbk_standalone_hostname"] = _standalone_host
                    vars_data["install_rhbk_standalone_hostname"] = _standalone_host
                    vars_data["rhbk_hostname"] = _standalone_host
                    vars_data["rhbk_host"] = _standalone_host
                    vars_data["install_rhbk_platform"] = "rhel"
                    vars_data["rhbk_platform"] = "rhel"
                    vars_data.setdefault("components_env", {}).setdefault("rhbk", {})
                    vars_data["components_env"]["rhbk"]["rhbk_hostname"] = _standalone_host
                    vars_data["components_env"]["rhbk"]["rhbk_host"] = _standalone_host
                    vars_data["components_env"]["rhbk"]["install_rhbk_platform"] = "rhel"
                    vars_data["components_env"]["rhbk"]["rhbk_platform"] = "rhel"
                    vars_data_changed = True
                zip_url = first_present(public_values.get("standalone_zip_url"))
                zip_filename = first_present(
                    public_values.get("standalone_zip_file"),
                    Path(str(public_values.get("standalone_zip") or "")).name
                    if public_values.get("standalone_zip")
                    else None,
                )
                zip_upload = first_present(public_values.get("standalone_zip_upload_path"))
                zip_content = first_present(secret_values.get("standalone_zip_content_base64"))
                zip_git_repo = first_present(public_values.get("standalone_zip_git_repo"))
                zip_git_path = first_present(public_values.get("standalone_zip_git_path"))
                zip_git_branch = first_present(public_values.get("standalone_zip_git_branch"))
                zip_source = str(
                    first_present(public_values.get("standalone_zip_source")) or ""
                ).strip().lower()
                if zip_source not in ("url", "git", "upload"):
                    if zip_git_repo:
                        zip_source = "git"
                    elif zip_url:
                        zip_source = "url"
                    elif zip_content or zip_upload or zip_filename:
                        zip_source = "upload"
                    else:
                        zip_source = ""
                if zip_source:
                    vars_data["rhbk_standalone_zip_source"] = zip_source
                    vars_data["install_rhbk_standalone_zip_source"] = zip_source
                    vars_data_changed = True
                if zip_source in ("", "url") and zip_url:
                    vars_data["rhbk_standalone_zip_url"] = str(zip_url)
                    vars_data_changed = True
                if zip_source == "git":
                    if zip_git_repo:
                        vars_data["rhbk_standalone_zip_git_repo"] = str(zip_git_repo)
                        vars_data["install_rhbk_standalone_zip_git_repo"] = str(zip_git_repo)
                        vars_data_changed = True
                    if zip_git_path:
                        vars_data["rhbk_standalone_zip_git_path"] = str(zip_git_path)
                        vars_data["install_rhbk_standalone_zip_git_path"] = str(zip_git_path)
                        vars_data_changed = True
                    if zip_git_branch:
                        vars_data["rhbk_standalone_zip_git_branch"] = str(zip_git_branch)
                        vars_data["install_rhbk_standalone_zip_git_branch"] = str(
                            zip_git_branch
                        )
                        vars_data_changed = True
                if zip_source in ("", "upload"):
                    if zip_content:
                        zip_target = write_repo_file_from_preflight(
                            zip_filename,
                            zip_content,
                            "rhbk.zip",
                            "base64",
                        )
                        vars_data["rhbk_standalone_zip"] = QuotedString(
                            playbook_file_ref(zip_target.name)
                        )
                        vars_data_changed = True
                    elif zip_upload and Path(str(zip_upload)).is_file():
                        zip_target = copy_repo_file_from_path(
                            zip_upload,
                            zip_filename,
                            "rhbk.zip",
                        )
                        vars_data["rhbk_standalone_zip"] = QuotedString(
                            playbook_file_ref(zip_target.name)
                        )
                        vars_data_changed = True
                    elif zip_filename and str(zip_filename).lower().endswith(".zip"):
                        typed_zip = str(public_values.get("standalone_zip") or "")
                        if typed_zip.startswith("/"):
                            vars_data["rhbk_standalone_zip"] = typed_zip
                        else:
                            vars_data["rhbk_standalone_zip"] = QuotedString(
                                playbook_file_ref(Path(str(zip_filename)).name)
                            )
                        vars_data_changed = True
                if public_values.get("standalone_admin_user"):
                    vars_data["rhbk_admin_user"] = str(public_values.get("standalone_admin_user"))
                if secret_values.get("standalone_admin_password"):
                    vars_data["rhbk_admin_password"] = vault_ref("vault_rhbk_admin_password")
                    vault_data["vault_rhbk_admin_password"] = QuotedString(
                        str(secret_values.get("standalone_admin_password"))
                    )
                    vault_data_changed = True
                tls_crt = first_present(
                    secret_values.get("standalone_tls_crt"),
                    public_values.get("standalone_tls_crt"),
                )
                tls_key = first_present(secret_values.get("standalone_tls_key"))
                if tls_crt:
                    vars_data["rhbk_standalone_tls_crt"] = vault_ref("vault_rhbk_standalone_tls_crt")
                    vars_data["tls_crt"] = vault_ref("vault_rhbk_standalone_tls_crt")
                    vault_data["vault_rhbk_standalone_tls_crt"] = QuotedString(str(tls_crt))
                    vault_data_changed = True
                if tls_key:
                    vars_data["rhbk_standalone_tls_key"] = vault_ref("vault_rhbk_standalone_tls_key")
                    vars_data["tls_key"] = vault_ref("vault_rhbk_standalone_tls_key")
                    vault_data["vault_rhbk_standalone_tls_key"] = QuotedString(str(tls_key))
                    vault_data_changed = True
                if tls_crt and tls_key:
                    vars_data["rhbk_standalone_https_enabled"] = True
                    vars_data["install_rhbk_standalone_https_enabled"] = True
            for mapper_key in (
                "group_mapper_name",
                "group_mapper_claim",
                "group_mapper_group_path",
                "group_mapper_sync_mode",
                "federation_name",
                "federation_provider",
                "federation_ldap_url",
                "federation_bind_dn",
                "federation_users_dn",
            ):
                if public_values.get(mapper_key) is not None:
                    vars_data[mapper_key] = public_values.get(mapper_key)
                    if mapper_key == "federation_name":
                        vars_data["rhbk_federation_name"] = str(public_values.get(mapper_key))
            scope_name = first_present(public_values.get("client_scope_name"))
            if scope_name is not None:
                normalized_scope = str(scope_name).strip()
                if normalized_scope.lower() in ("group", ""):
                    normalized_scope = "groups"
                vars_data["client_scope_name"] = normalized_scope
                vars_data["rhbk_client_scope_name"] = normalized_scope
            elif "client_scopes" in (preflight.get("component_options") or {}).get("rhbk", []):
                vars_data["client_scope_name"] = "groups"
                vars_data["rhbk_client_scope_name"] = "groups"
            bind_password = first_present(secret_values.get("federation_bind_password"))
            ldap_updates = {}
            if public_values.get("federation_ldap_url") is not None:
                ldap_updates["connectionUrl"] = str(public_values.get("federation_ldap_url"))
            if public_values.get("federation_bind_dn") is not None:
                ldap_updates["bindDn"] = str(public_values.get("federation_bind_dn"))
            if bind_password is not None:
                ldap_updates["bindCredential"] = str(bind_password)
            if public_values.get("federation_users_dn") is not None:
                ldap_updates["usersDn"] = str(public_values.get("federation_users_dn"))
            if ldap_updates:
                existing_ldap = vault_data.get("ldap_config")
                if isinstance(existing_ldap, dict):
                    merged_ldap = dict(existing_ldap)
                    merged_ldap.update(ldap_updates)
                    vault_data["ldap_config"] = merged_ldap
                    vault_data_changed = True
            fed_name = first_present(public_values.get("federation_name"))
            if fed_name is not None:
                vault_data["rhbk_federation_name"] = str(fed_name)
                vault_data_changed = True
            elif "federation" in (preflight.get("component_options") or {}).get("rhbk", []):
                default_fed = "LDAP"
                vars_data["federation_name"] = default_fed
                vars_data["rhbk_federation_name"] = default_fed
                vault_data["rhbk_federation_name"] = default_fed
                vault_data_changed = True

            if not rhbk_standalone_selected:
                purge_standalone_install_vars(vars_data, "rhbk")
                vars_data_changed = True

        if component == "aap":
            preflight_aap = preflight.get("aap") or {}
            deployment_version = aap_dotted_version(
                public_values.get("deployment_version"),
                public_values.get("version"),
                preflight_aap.get("version"),
                default="2.7",
            )
            namespace = str(public_values.get("namespace") or "aap")
            instance_name = str(
                public_values.get("instance_name") or namespace
            )
            admin_password_secret = f"{instance_name}-admin-password"
            admin_username = str(
                first_present(
                    public_values.get("admin_username"),
                    preflight_aap.get("admin_username"),
                    "admin",
                )
                or "admin"
            )
            # license_only may not be finalized until later in this block;
            # detect attach early so General-tab password wins.
            _attach_early = (
                isinstance(preflight.get("pre_installs"), dict)
                and as_bool(
                    (preflight.get("pre_installs") or {}).get("attach_aap_license"),
                    False,
                )
                and not as_bool(
                    (preflight.get("pre_installs") or {}).get("install_aap"),
                    False,
                )
            ) or as_bool(public_values.get("license_only"), False)
            if _attach_early:
                admin_password = first_present(
                    preflight_aap.get("admin_password"),
                    secret_values.get("admin_password"),
                )
            else:
                admin_password = first_present(
                    secret_values.get("admin_password"),
                    preflight_aap.get("admin_password"),
                )
            if admin_password is not None:
                vault_data["aap_admin_password"] = admin_password
                vault_data["vault_controller_password"] = admin_password
                vault_data_changed = True
                vars_data["aap_ocp_install_admin_password"] = vault_ref("aap_admin_password")
                vars_data["aap_ocp_install_admin_user"] = admin_username
            vault_data["aap_admin_user"] = admin_username
            vault_data_changed = True
            minimal_footprint = as_bool(
                public_values.get("minimal_footprint"),
                False,
            )
            install_controller = as_bool(
                public_values.get("install_controller"),
                True,
            )
            install_hub = as_bool(public_values.get("install_hub"), True)
            install_eda = as_bool(public_values.get("install_eda"), True)
            install_lightspeed = as_bool(
                public_values.get("install_lightspeed"),
                False,
            )
            if minimal_footprint:
                install_hub = False
                install_eda = False
                install_lightspeed = False
            openshift_values = preflight.get("openshift") or {}
            api_host = first_present(
                openshift_values.get("api_host"),
                openshift_values.get("host"),
                preflight.get("api_host"),
            )
            skip_tls_verify = as_bool(
                openshift_values.get("skip_tls_verify"),
                True,
            )
            if openshift_values.get("token") is not None:
                vault_data["token"] = openshift_values["token"]
                vault_data_changed = True
            vars_data["aap_ocp_install_namespace"] = namespace
            vars_data["aap_ocp_install_create_namespace"] = as_bool(
                public_values.get("create_namespace"),
                True,
            )
            vars_data["aap_ocp_install_connection"] = {
                "host": str(api_host or ""),
                "api_key": vault_ref("token"),
                "validate_certs": not skip_tls_verify,
            }
            operator_scope_raw = str(
                public_values.get("operator_scope") or "all_namespaces"
            ).strip().lower().replace("-", "_")
            if operator_scope_raw in (
                "namespaced",
                "namespace",
                "single_namespace",
            ):
                operator_scope = "namespaced"
                default_operator_channel = f"stable-{deployment_version}"
            else:
                operator_scope = "all_namespaces"
                default_operator_channel = (
                    f"stable-{deployment_version}-cluster-scoped"
                )
            operator_channel = str(
                public_values.get("operator_channel")
                or default_operator_channel
            )
            vars_data["aap_operator_scope"] = operator_scope
            vars_data.setdefault("component_config", {}).setdefault("aap", {})
            vars_data["component_config"]["aap"]["operator_scope"] = operator_scope
            vars_data["component_config"]["aap"]["operator_channel"] = (
                operator_channel
            )
            vars_data["aap_ocp_install_operator"] = {
                "channel": operator_channel,
                "approval": str(
                    public_values.get("operator_approval") or "automatic"
                ),
            }
            vars_data["aap_ocp_install_platform"] = {
                "instance_name": instance_name,
                "namespace": namespace,
                "component_deployment": str(
                    public_values.get("component_deployment") or "unified"
                ),
                "admin_user": admin_username,
                "admin_password_secret": admin_password_secret,
                "platform_manifest_overrides": copy.deepcopy(
                    public_values.get("platform_manifest_overrides") or {}
                ),
            }
            vars_data["aap_ocp_install_controller"] = {
                "instance_name": f"{instance_name}-controller",
                "namespace": namespace,
                "install": install_controller,
                "admin_user": admin_username,
                "replicas": int(
                    public_values.get("controller_replicas")
                    or public_values.get("replicas")
                    or 1
                ),
                "controller_manifest_overrides": copy.deepcopy(
                    public_values.get("controller_manifest_overrides") or {}
                ),
            }
            vars_data["aap_ocp_install_hub"] = {
                "instance_name": f"{instance_name}-hub",
                "namespace": namespace,
                "install": install_hub,
                "storage_type": str(
                    public_values.get("hub_storage_type") or "file"
                ),
                "file_storage_storage_class": str(
                    public_values.get("hub_storage_class") or ""
                ),
                "file_storage_size": str(
                    public_values.get("hub_storage_size") or "20Gi"
                ),
                "object_storage_s3_secret": str(
                    public_values.get("hub_s3_secret") or ""
                ),
                "object_storage_azure_secret": str(
                    public_values.get("hub_azure_secret") or ""
                ),
                "hub_manifest_overrides": copy.deepcopy(
                    public_values.get("hub_manifest_overrides") or {}
                ),
            }
            vars_data["aap_ocp_install_eda"] = {
                "instance_name": f"{instance_name}-eda",
                "namespace": namespace,
                "install": install_eda,
                "eda_manifest_overrides": copy.deepcopy(
                    public_values.get("eda_manifest_overrides") or {}
                ),
            }
            vars_data["aap_ocp_install_lightspeed"] = {
                "install": install_lightspeed
            }
            vars_data["aap_minimal_footprint"] = minimal_footprint
            pre_installs = preflight.get("pre_installs") or {}
            if not isinstance(pre_installs, dict):
                pre_installs = {}
            pre_aap = pre_installs.get("aap") if isinstance(pre_installs, dict) else {}
            if not isinstance(pre_aap, dict):
                pre_aap = {}
            # Preflight is SSOT for install/attach — never keep stale group_vars
            # license_only / install_during_bootstrap from a prior attach run.
            want_install = as_bool(pre_installs.get("install_aap"), False)
            want_attach = as_bool(pre_installs.get("attach_aap_license"), False) or as_bool(
                pre_aap.get("license_only"), False
            )
            if want_install:
                vars_data["aap_install_during_bootstrap"] = True
                public_values["install_during_bootstrap"] = True
            elif want_attach:
                vars_data["aap_install_during_bootstrap"] = True
                public_values["install_during_bootstrap"] = True
            else:
                vars_data["aap_install_during_bootstrap"] = False
                public_values["install_during_bootstrap"] = False
            license_mode = str(
                first_present(
                    pre_aap.get("license_mode"),
                    public_values.get("license_mode"),
                    "none",
                )
                or "none"
            ).lower()
            if not want_install and not want_attach:
                license_mode = str(pre_aap.get("license_mode") or "none").lower()
            vars_data["aap_ocp_install_license_mode"] = license_mode
            license_only = bool(want_attach and not want_install)
            vars_data["aap_ocp_install_license_only"] = license_only
            public_values["license_only"] = license_only
            public_values["install_during_bootstrap"] = bool(
                vars_data.get("aap_install_during_bootstrap")
            )
            manifest_file = first_present(
                public_values.get("subscription_manifest_file"),
                pre_aap.get("subscription_manifest_file"),
            )
            if manifest_file:
                vars_data["aap_ocp_install_subscription_manifest_filename"] = str(manifest_file)
            manifest_b64 = first_present(
                public_values.get("subscription_manifest_content_base64"),
                pre_aap.get("subscription_manifest_content_base64"),
                secret_values.get("subscription_manifest_content_base64"),
            )
            if manifest_b64:
                vault_data["aap_ocp_install_subscription_manifest_content_base64"] = manifest_b64
                vault_data_changed = True
            rhn_user = first_present(
                public_values.get("rhn_username"),
                pre_aap.get("rhn_username"),
            )
            rhn_pass = first_present(
                secret_values.get("rhn_password"),
                public_values.get("rhn_password"),
                pre_aap.get("rhn_password"),
            )
            if rhn_user:
                vars_data["aap_ocp_install_rhn_username"] = str(rhn_user)
            if rhn_pass:
                vault_data["aap_ocp_install_rhn_password"] = rhn_pass
                vars_data["aap_ocp_install_rhn_password"] = vault_ref(
                    "aap_ocp_install_rhn_password"
                )
                vault_data_changed = True
            rhn_subscription_id = first_present(
                public_values.get("rhn_subscription_id"),
                pre_aap.get("rhn_subscription_id"),
            )
            if rhn_subscription_id:
                vars_data["aap_ocp_install_rhn_subscription_id"] = str(
                    rhn_subscription_id
                )
            rhn_client_id = first_present(
                public_values.get("rhn_client_id"),
                pre_aap.get("rhn_client_id"),
            )
            rhn_client_secret = first_present(
                secret_values.get("rhn_client_secret"),
                public_values.get("rhn_client_secret"),
                pre_aap.get("rhn_client_secret"),
            )
            if rhn_client_id:
                vars_data["aap_ocp_install_rhn_client_id"] = str(rhn_client_id)
            if rhn_client_secret:
                vault_data["aap_ocp_install_rhn_client_secret"] = rhn_client_secret
                vars_data["aap_ocp_install_rhn_client_secret"] = vault_ref(
                    "aap_ocp_install_rhn_client_secret"
                )
                vault_data_changed = True
            # License-only attach: prefer General tab aap.hostname over stale
            # component_config.aap.hostname (e.g. default aap-aap.apps...).
            if license_only:
                hostname_value = first_present(
                    preflight_aap.get("hostname"),
                    public_values.get("hostname"),
                )
            else:
                hostname_value = first_present(
                    public_values.get("hostname"),
                    preflight_aap.get("hostname"),
                )
            if hostname_value:
                host_clean = re.sub(
                    r"^https?://", "", str(hostname_value)
                ).rstrip("/")
                vars_data["hostname"] = host_clean
                vars_data["aap_hostname"] = host_clean
                vars_data["aap_ocp_install_controller_route_host"] = host_clean
            # Manifest base64 must be available to the license task as a var.
            if manifest_b64:
                vars_data[
                    "aap_ocp_install_subscription_manifest_content_base64"
                ] = vault_ref(
                    "aap_ocp_install_subscription_manifest_content_base64"
                )

        if component == "devspaces":
            vars_data.setdefault("components_env", {}).setdefault("devspaces", {})
            mapping = {
                "hostname": "hostname",
                "storage": "storage",
                "namespace": "app_namespace",
                "disable_default_samples": "disable_default_samples",
                "customize_workspace": "customize_workspace",
                "default_devfile_url": "default_devfile_url",
                "default_workspace_image": "default_workspace_image",
                "dashboard_image": "dashboard_image",
                "che_image_tag": "che_image_tag",
            }
            for src_key, dest_key in mapping.items():
                if public_values.get(src_key) is not None and public_values.get(src_key) != "":
                    vars_data[dest_key] = public_values.get(src_key)
                    vars_data["components_env"]["devspaces"][dest_key] = public_values.get(src_key)
            host = strip_host(public_values.get("hostname"))
            if host:
                vars_data["hostname"] = host
                vars_data["ocp_devspaces_hostname"] = host
                vars_data["components_env"]["devspaces"]["hostname"] = host
                vars_data_changed = True
            # Role-prefixed aliases
            for role_key in (
                "ocp_devspaces_disable_default_samples",
                "ocp_devspaces_customize_workspace",
                "ocp_devspaces_default_devfile_url",
                "ocp_devspaces_default_workspace_image",
                "ocp_devspaces_dashboard_image",
            ):
                plain = role_key.replace("ocp_devspaces_", "", 1)
                if plain in public_values and public_values.get(plain) not in (None, ""):
                    vars_data[role_key] = public_values.get(plain)
            if "disable_default_samples" in public_values:
                vars_data["ocp_devspaces_disable_default_samples"] = as_bool(
                    public_values.get("disable_default_samples"), True
                )
            if "customize_workspace" in public_values:
                vars_data["ocp_devspaces_customize_workspace"] = as_bool(
                    public_values.get("customize_workspace"), False
                )
            if public_values.get("default_devfile_url"):
                vars_data["ocp_devspaces_default_devfile_url"] = public_values.get("default_devfile_url")
            if public_values.get("default_workspace_image"):
                vars_data["ocp_devspaces_default_workspace_image"] = public_values.get("default_workspace_image")
            if public_values.get("dashboard_image"):
                vars_data["ocp_devspaces_dashboard_image"] = public_values.get("dashboard_image")

            # Optional DevWorkspace status metrics exporter (Grafana).
            status_exporter_enabled = as_bool(
                public_values.get("status_exporter_enabled"), False
            )
            vars_data["ocp_devspaces_status_exporter_enabled"] = status_exporter_enabled
            vars_data["components_env"]["devspaces"][
                "status_exporter_enabled"
            ] = status_exporter_enabled
            vars_data["status_exporter_enabled"] = status_exporter_enabled
            if status_exporter_enabled:
                vars_data_changed = True

            # Custom getting-started sample (display name + git URL + icon).
            custom_enabled = as_bool(public_values.get("custom_sample_enabled"), False)
            vars_data["ocp_devspaces_custom_sample_enabled"] = custom_enabled
            vars_data["components_env"]["devspaces"]["custom_sample_enabled"] = custom_enabled
            if custom_enabled:
                display_name = str(
                    public_values.get("custom_sample_display_name") or "ADO"
                ).strip() or "ADO"
                description = str(
                    public_values.get("custom_sample_description")
                    or "ADO default Dev Spaces workspace"
                ).strip()
                tags_raw = public_values.get("custom_sample_tags") or "ado"
                if isinstance(tags_raw, list):
                    tags = [str(t).strip() for t in tags_raw if str(t).strip()]
                else:
                    tags = [
                        t.strip()
                        for t in str(tags_raw).split(",")
                        if t.strip()
                    ] or ["ado"]
                sample_url = str(public_values.get("custom_sample_url") or "").strip()
                # Fall back to default_devfile_url when sample URL blank.
                if not sample_url:
                    sample_url = str(
                        public_values.get("default_devfile_url") or ""
                    ).strip()
                icon_source = str(
                    public_values.get("custom_sample_icon_source") or "bundled"
                ).strip().lower()
                icon_b64 = str(
                    public_values.get("custom_sample_icon_base64") or ""
                ).strip()
                icon_media = str(
                    public_values.get("custom_sample_icon_mediatype") or "image/png"
                ).strip() or "image/png"
                sample = {
                    "displayName": display_name,
                    "description": description,
                    "tags": tags,
                    "url": sample_url,
                }
                if icon_source == "upload" and icon_b64:
                    sample["icon"] = {
                        "base64data": icon_b64,
                        "mediatype": icon_media,
                    }
                    vars_data["ocp_devspaces_custom_sample_icon_source"] = "upload"
                else:
                    # Role loads roles/ocp_devspaces/files/ado-sample-icon.png
                    vars_data["ocp_devspaces_custom_sample_icon_source"] = "bundled"
                    sample["icon_source"] = "bundled"
                vars_data["ocp_devspaces_custom_samples"] = [sample]
                vars_data["components_env"]["devspaces"]["custom_samples"] = [sample]
                vars_data_changed = True
            elif isinstance(public_values.get("custom_samples"), list) and public_values.get(
                "custom_samples"
            ):
                vars_data["ocp_devspaces_custom_samples"] = public_values.get("custom_samples")
                vars_data["components_env"]["devspaces"]["custom_samples"] = public_values.get(
                    "custom_samples"
                )
                vars_data_changed = True

        if component == "acs":
            for src_key in (
                "policies_source_type",
                "policies_source",
                "reports_source_type",
                "reports_source",
            ):
                if public_values.get(src_key) is not None:
                    vars_data[f"acs_{src_key}"] = public_values.get(src_key)
            if public_values.get("namespace"):
                vars_data["acs_namespace"] = public_values.get("namespace")
                vars_data["ocp_acs_namespace"] = public_values.get("namespace")
            if public_values.get("storage"):
                if apply_storage_var(
                    vars_data,
                    "acs",
                    preflight,
                    public_values["storage"],
                    vars_data_changed,
                ):
                    vars_data_changed = True
                    vars_data["ocp_acs_storage_class"] = vars_data.get("storage")
                    vars_data.setdefault("components_env", {}).setdefault("acs", {})
                    vars_data["components_env"]["acs"]["storage"] = vars_data.get(
                        "storage"
                    )
            acs_host = first_present(public_values.get("hostname"))
            apps_domain = str(
                ((preflight.get("openshift") or {}).get("apps_domain")) or ""
            ).strip()
            if not acs_host and apps_domain:
                acs_host = f"central.{apps_domain}"
            if acs_host:
                host_clean = strip_host(str(acs_host))
                if host_clean:
                    vars_data["ocp_acs_hostname"] = host_clean
                    vars_data.setdefault("components_env", {}).setdefault("acs", {})
                    vars_data["components_env"]["acs"]["hostname"] = host_clean
                    vars_data_changed = True

        if component == "acm":
            if public_values.get("namespace"):
                vars_data["name_space"] = public_values.get("namespace")
            channel = str(
                first_present(
                    public_values.get("channel"),
                    vars_data.get("operator_channel"),
                    "release-2.17",
                )
            ).strip()
            # Catalog no longer ships release-2.14 (ResolutionFailed on OLM).
            if (not channel) or channel in (
                "release-2.14",
                "release-2.13",
                "release-2.12",
                "release-2.11",
            ):
                channel = "release-2.17"
            vars_data["operator_channel"] = channel
            vars_data.setdefault("component_config", {}).setdefault("acm", {})
            vars_data["component_config"]["acm"]["channel"] = channel
            vars_data_changed = True
            if public_values.get("storage"):
                vars_data["storage_class"] = public_values.get("storage")

        if component == "openshift_virt":
            openshift_values = preflight.get("openshift") or {}
            openshift_skip_tls = as_bool(
                openshift_values.get("skip_tls_verify"),
                True,
            )
            virt_skip_tls = as_bool(
                first_present(
                    public_values.get("skip_tls_verify"),
                    public_values.get("provision_openshift_virt_skip_tls_verify"),
                ),
                openshift_skip_tls,
            )
            vars_data["provision_openshift_virt_skip_tls_verify"] = virt_skip_tls
            vars_data["skip_tls_verify"] = openshift_skip_tls
            vars_data["verify_ssl"] = not openshift_skip_tls
            vars_data["validate_certs"] = not virt_skip_tls

            api_host = first_present(
                public_values.get("api_host"),
                public_values.get("provision_openshift_virt_api_host"),
                openshift_values.get("api_host"),
                openshift_values.get("host"),
            )
            if api_host is not None:
                vars_data["provision_openshift_virt_api_host"] = str(api_host)

            api_token = first_present(
                secret_values.get("api_token"),
                openshift_values.get("token"),
            )
            if api_token is not None:
                vault_data["provision_openshift_virt_api_token"] = api_token
                vault_data_changed = True
                secret_values.pop("api_token", None)

            if "prefix_length" in public_values:
                try:
                    vars_data["provision_openshift_virt_prefix_length"] = int(
                        public_values.get("prefix_length") or 24
                    )
                except (TypeError, ValueError):
                    vars_data["provision_openshift_virt_prefix_length"] = 24

            if "gateway" in public_values:
                vars_data["provision_openshift_virt_gateway"] = str(
                    public_values.get("gateway") or ""
                )

            if "dns_servers" in public_values:
                dns_servers = public_values.get("dns_servers")
                if isinstance(dns_servers, list):
                    vars_data["provision_openshift_virt_dns_servers"] = [
                        str(item).strip() for item in dns_servers if str(item).strip()
                    ]
                else:
                    vars_data["provision_openshift_virt_dns_servers"] = str(
                        dns_servers or ""
                    )

            if "ip_range" in public_values:
                vars_data["openshift_virt_ip_range"] = str(
                    public_values.get("ip_range") or ""
                )

            # Static IP is chosen at job launch; preflight only seeds shared network defaults.
            vars_data["provision_openshift_virt_static_ip"] = ""
            vars_data["openshift_virt_network_defaults"] = {
                "ip_range": str(
                    vars_data.get("openshift_virt_ip_range")
                    or public_values.get("ip_range")
                    or ""
                ),
                "static_ip": "",
                "prefix_length": int(
                    vars_data.get("provision_openshift_virt_prefix_length") or 24
                ),
                "gateway": str(
                    vars_data.get("provision_openshift_virt_gateway") or ""
                ),
                "dns_servers": vars_data.get(
                    "provision_openshift_virt_dns_servers",
                    "",
                ),
            }

        if component == "ec2_ami_copy":
            ec2_ami_copy_mapping = {
                "source_region": "ec2_ami_copy_source_region",
                "dest_region": "ec2_ami_copy_dest_region",
                "source_image_id": "ec2_ami_copy_source_image_id",
                "name": "ec2_ami_copy_name",
                "description": "ec2_ami_copy_description",
                "kms_key_id": "ec2_ami_copy_kms_key_id",
            }
            for source_key, target_key in ec2_ami_copy_mapping.items():
                if source_key in public_values:
                    vars_data[target_key] = str(public_values.get(source_key) or "")
                    vars_data_changed = True

            for flag_key, target_key in (
                ("wait", "ec2_ami_copy_wait"),
                ("encrypted", "ec2_ami_copy_encrypted"),
                ("copy_image_tags", "ec2_ami_copy_copy_image_tags"),
                ("tag_equality", "ec2_ami_copy_tag_equality"),
            ):
                if flag_key in public_values:
                    vars_data[target_key] = as_bool(public_values.get(flag_key), False)
                    vars_data_changed = True

            if "wait_timeout" in public_values:
                try:
                    vars_data["ec2_ami_copy_wait_timeout"] = int(
                        public_values.get("wait_timeout") or 600
                    )
                except (TypeError, ValueError):
                    vars_data["ec2_ami_copy_wait_timeout"] = 600
                vars_data_changed = True

            if "tags" in public_values and isinstance(public_values.get("tags"), dict):
                vars_data["ec2_ami_copy_tags"] = public_values["tags"]
                vars_data_changed = True

        if component in ("ec2_instance", "aws_instance"):
            ec2_instance_mapping = {
                "name": "ec2_instance_name",
                "image_id": "ec2_instance_image_id",
                "instance_type": "ec2_instance_instance_type",
                "region": "ec2_instance_region",
                "vpc_subnet_id": "ec2_instance_vpc_subnet_id",
                "security_group": "ec2_instance_security_group",
                "key_name": "ec2_instance_key_name",
                "state": "ec2_instance_state",
            }
            for source_key, target_key in ec2_instance_mapping.items():
                if source_key in public_values:
                    vars_data[target_key] = str(public_values.get(source_key) or "")
                    vars_data_changed = True

            if "wait" in public_values:
                vars_data["ec2_instance_wait"] = as_bool(public_values.get("wait"), True)
                vars_data_changed = True

            if "wait_timeout" in public_values:
                try:
                    vars_data["ec2_instance_wait_timeout"] = int(
                        public_values.get("wait_timeout") or 600
                    )
                except (TypeError, ValueError):
                    vars_data["ec2_instance_wait_timeout"] = 600
                vars_data_changed = True

        if component == "aws":
            if public_values.get("profile") is not None:
                vars_data["aws_profile"] = str(public_values.get("profile") or "")
                vars_data_changed = True
            if public_values.get("default_region") is not None:
                vars_data["aws_default_region"] = str(
                    public_values.get("default_region") or ""
                )
                vars_data_changed = True

        if component == "satellite":
            vars_data.setdefault("components_env", {}).setdefault("satellite", {})
            vars_data["components_env"]["satellite"].pop("storage", None)
            if public_values.get("hostname"):
                satellite_url = str(public_values["hostname"])
                if not satellite_url.startswith(("http://", "https://")):
                    satellite_url = "https://" + satellite_url
                vars_data["components_env"]["satellite"]["hostname"] = public_values["hostname"]
                vars_data["satellite_config_server_url"] = satellite_url
                vars_data["rhel_sat_reg_satellite_host"] = satellite_url
            if public_values.get("organization"):
                vars_data["satellite_config_organization"] = public_values["organization"]
                vars_data["rhel_sat_reg_satellite_org_name"] = public_values["organization"]
            if public_values.get("service_account_username"):
                vars_data["satellite_config_username"] = public_values["service_account_username"]
                vars_data["satellite_service_account_username"] = public_values["service_account_username"]
                vars_data["rhel_sat_reg_org_admin_account"] = public_values["service_account_username"]
                vault_data["vault_satellite_service_account_username"] = public_values["service_account_username"]
                vault_data_changed = True
            if "validate_certs" in public_values:
                vars_data["satellite_config_validate_certs"] = public_values["validate_certs"]
                vars_data["rhel_sat_reg_validate_certs"] = public_values["validate_certs"]
                vars_data["rhel_sat_reg_insecure"] = not bool(public_values["validate_certs"])
            if public_values.get("deployment_version"):
                vars_data["satellite_config_satellite_deployment_version"] = public_values["deployment_version"]
                vars_data["satellite_install_deployment_version"] = public_values["deployment_version"]
            if public_values.get("location"):
                vars_data["satellite_install_location"] = public_values["location"]

            rhn_connected = as_bool(
                first_present(
                    public_values.get("satellite_config_rhn_connected"),
                    public_values.get("rhn_connected"),
                    public_values.get("satellite_install_rhn_connected"),
                ),
                True,
            )
            vars_data["satellite_config_rhn_connected"] = rhn_connected

            manifest_organization = first_present(
                public_values.get("satellite_config_manifest_organization"),
                public_values.get("satellite_install_manifest_organization"),
                public_values.get("satellite_manifest_organization"),
                public_values.get("manifest_organization"),
                public_values.get("organization"),
            )
            if manifest_organization is not None:
                vars_data["satellite_config_organization"] = str(manifest_organization)
                vars_data["rhel_sat_reg_satellite_org_name"] = str(manifest_organization)
            manifest_file = first_present(
                public_values.get("satellite_config_manifest_file"),
                public_values.get("satellite_install_manifest_file"),
                public_values.get("satellite_manifest_file"),
                public_values.get("manifest_file"),
                public_values.get("manifest_filename"),
            )
            manifest_src = first_present(
                public_values.get("satellite_config_manifest_src"),
                public_values.get("satellite_install_manifest_path"),
                public_values.get("satellite_manifest_path"),
                public_values.get("manifest_path"),
            )
            manifest_dest = public_values.get("satellite_config_manifest_path")
            manifest_content = first_present(
                secret_values.get("satellite_manifest_content_base64"),
                secret_values.get("manifest_content_base64"),
                secret_values.get("satellite_manifest_b64"),
                secret_values.get("manifest_b64"),
                secret_values.get("satellite_manifest_content"),
                secret_values.get("manifest_content"),
            )
            if manifest_content is not None:
                manifest_filename = first_present(
                    manifest_file,
                    "satellite-manifest.zip",
                )
                manifest_encoding = first_present(
                    public_values.get("manifest_encoding"),
                    "base64",
                )
                manifest_target = write_repo_file_from_preflight(
                    manifest_filename,
                    manifest_content,
                    "satellite-manifest.zip",
                    manifest_encoding,
                )
                vars_data["satellite_config_manifest_file"] = manifest_target.name
                vars_data["satellite_config_manifest_src"] = QuotedString(
                    playbook_file_ref(manifest_target.name)
                )
                vars_data["satellite_config_manifest_path"] = str(
                    first_present(
                        manifest_dest,
                        "/root/" + manifest_target.name,
                    )
                )
                vars_data["satellite_config_upload_manifest"] = True
            elif manifest_file is not None or manifest_src is not None:
                if manifest_file is not None:
                    manifest_filename = Path(str(manifest_file)).name
                    resolved_src = first_present(
                        manifest_src,
                        playbook_file_ref(manifest_filename),
                    )
                else:
                    manifest_filename = Path(str(manifest_src)).name
                    resolved_src = str(manifest_src)
                vars_data["satellite_config_manifest_file"] = manifest_filename
                if jinja_open in str(resolved_src):
                    vars_data["satellite_config_manifest_src"] = QuotedString(
                        str(resolved_src)
                    )
                else:
                    vars_data["satellite_config_manifest_src"] = str(resolved_src)
                vars_data["satellite_config_manifest_path"] = str(
                    first_present(
                        manifest_dest,
                        "/root/" + manifest_filename,
                    )
                )
                vars_data["satellite_config_upload_manifest"] = True
            for manifest_payload_key in satellite_manifest_payload_keys:
                secret_values.pop(manifest_payload_key, None)
            vg_name = first_present(
                public_values.get("satellite_install_vg_name"),
                public_values.get("satellite_vg_name"),
                public_values.get("vg_name"),
                public_values.get("vgname"),
            )
            if vg_name is not None:
                vars_data["satellite_install_vg_name"] = vg_name
            data_disk_min_size = first_present(
                public_values.get("satellite_install_data_disk_min_size"),
                public_values.get("satellite_data_disk_min_size"),
                public_values.get("data_disk_min_size"),
            )
            if data_disk_min_size is not None:
                vars_data["satellite_install_data_disk_min_size"] = QuotedString(str(data_disk_min_size))
            data_device_name = first_present(
                public_values.get("satellite_install_data_device_name"),
                public_values.get("satellite_data_device_name"),
                public_values.get("data_device_name"),
            )
            if data_device_name is not None:
                vars_data["satellite_install_data_device_name"] = str(data_device_name)
            data_device = first_present(
                public_values.get("satellite_install_data_device"),
                public_values.get("satellite_data_device"),
                public_values.get("data_device"),
            )
            if data_device is not None:
                vars_data["satellite_install_data_device"] = str(data_device)
            rhn_org_id = first_present(
                public_values.get("satellite_install_rhn_org_id"),
                public_values.get("rhn_org_id"),
                public_values.get("org_id"),
                public_values.get("redhat_org_id"),
                public_values.get("satellite_rhn_org_id"),
            )
            if rhn_org_id is not None:
                vault_data["vault_satellite_rhn_org_id"] = QuotedString(str(rhn_org_id))
                vault_data["satellite_install_rhn_org_id"] = QuotedString(str(rhn_org_id))
                vars_data["satellite_install_rhn_org_id"] = vault_ref("vault_satellite_rhn_org_id")
                vars_data["satellite_install_rhn_connected"] = True
                vault_data_changed = True
            rhn_activation_key = first_present(
                public_values.get("satellite_install_rhn_activation_key"),
                public_values.get("admin_rhn_activation_key"),
                public_values.get("satellite_admin_rhn_activation_key"),
                public_values.get("rhn_activation_key"),
                public_values.get("admin_activation_key"),
            )
            if rhn_activation_key is not None:
                vault_data["vault_satellite_rhn_activation_key"] = QuotedString(str(rhn_activation_key))
                vault_data["satellite_install_rhn_activation_key"] = QuotedString(str(rhn_activation_key))
                vars_data["satellite_install_rhn_activation_key"] = vault_ref("vault_satellite_rhn_activation_key")
                vars_data["satellite_install_rhn_connected"] = True
                vault_data_changed = True
            client_activation_key = first_present(
                public_values.get("activation_key"),
                public_values.get("satellite_activation_key"),
                public_values.get("client_activation_key"),
                public_values.get("rhel_sat_reg_activation_key_name"),
            )
            if client_activation_key is not None:
                vars_data["satellite_activation_key"] = QuotedString(str(client_activation_key))
                vars_data["rhel_sat_reg_activation_key_name"] = QuotedString(str(client_activation_key))
                vars_data_changed = True
            req_dirs = first_present(
                public_values.get("satellite_install_req_dirs"),
                public_values.get("req_dirs"),
            )
            if req_dirs:
                vars_data["satellite_install_req_dirs"] = copy.deepcopy(req_dirs)
            if public_values.get("size"):
                vars_data["satellite_install_size"] = copy.deepcopy(public_values["size"])
            if public_values.get("size_profile"):
                vars_data["satellite_install_size_profile"] = public_values["size_profile"]
                satellite_sizes = vars_data.get("satellite_install_size") or []
                selected_size = next(
                    (
                        item for item in satellite_sizes
                        if isinstance(item, dict) and item.get("name") == public_values["size_profile"]
                    ),
                    {},
                )
                if selected_size.get("min_ram") is not None:
                    vars_data["satellite_install_min_memory_size"] = int(selected_size["min_ram"]) * 1024
                if selected_size.get("min_cpu") is not None:
                    vars_data["satellite_install_min_cpu_count"] = int(selected_size["min_cpu"])

            oidc_cfg = public_values.get("oidc") if isinstance(public_values.get("oidc"), dict) else {}
            oidc_client_id = first_present(
                oidc_cfg.get("client_id"),
                public_values.get("oidc_client_id"),
                public_values.get("satellite_oidc_client_id"),
                "ado-satellite",
            )
            oidc_realm = first_present(
                oidc_cfg.get("realm"),
                public_values.get("oidc_realm"),
                public_values.get("satellite_oidc_realm"),
                "rhlab",
            )
            oidc_keycloak_url = first_present(
                oidc_cfg.get("keycloak_url"),
                public_values.get("keycloak_url"),
                public_values.get("satellite_oidc_keycloak_url"),
            )
            oidc_issuer = first_present(
                oidc_cfg.get("issuer"),
                public_values.get("oidc_issuer"),
                public_values.get("satellite_oidc_issuer"),
            )
            if oidc_issuer is None and oidc_keycloak_url and oidc_realm:
                oidc_issuer = str(oidc_keycloak_url).rstrip("/") + "/realms/" + str(oidc_realm)
            oidc_hostname = str(oidc_keycloak_url or "").strip()
            oidc_hostname = oidc_hostname.replace("https://", "").replace("http://", "")
            oidc_hostname = oidc_hostname.split("/", maxsplit=1)[0]
            if oidc_client_id:
                vars_data["satellite_oidc_client_id"] = str(oidc_client_id)
                vars_data["rhbk_client"] = str(oidc_client_id)
            if oidc_realm:
                vars_data["satellite_oidc_realm"] = str(oidc_realm)
                vars_data["rhbk_realm"] = str(oidc_realm)
            if oidc_keycloak_url:
                vars_data["satellite_oidc_keycloak_url"] = str(oidc_keycloak_url)
            if oidc_hostname:
                vars_data["satellite_oidc_keycloak_hostname"] = oidc_hostname
                vars_data["rhbk_hostname"] = oidc_hostname
            if oidc_issuer:
                vars_data["satellite_oidc_issuer"] = str(oidc_issuer)
            vars_data["satellite_oidc_create_client"] = as_bool(
                first_present(
                    oidc_cfg.get("create_client"),
                    public_values.get("satellite_oidc_create_client"),
                    True,
                ),
                True,
            )
            vars_data["satellite_oidc_keycloak_validate_certs"] = as_bool(
                first_present(
                    oidc_cfg.get("validate_certs"),
                    public_values.get("oidc_validate_certs"),
                    False,
                ),
                False,
            )
            vars_data["rhbk_verify_ssl"] = vars_data["satellite_oidc_keycloak_validate_certs"]
            if vars_data.get("satellite_config_server_url"):
                vars_data["satellite_oidc_server_url"] = vars_data["satellite_config_server_url"]
            vars_data["satellite_oidc_validate_certs"] = vars_data.get(
                "satellite_config_validate_certs", False
            )
            oidc_client_secret = first_present(
                oidc_cfg.get("client_secret"),
                secret_values.get("oidc_client_secret"),
                secret_values.get("client_secret"),
                secret_values.get("satellite_oidc_client_secret"),
            )
            oidc_admin_user = first_present(
                oidc_cfg.get("admin_user"),
                oidc_cfg.get("keycloak_admin_user"),
                public_values.get("keycloak_admin_user"),
                "admin",
            )
            oidc_admin_password = first_present(
                oidc_cfg.get("admin_password"),
                oidc_cfg.get("keycloak_admin_password"),
                secret_values.get("keycloak_admin_password"),
                secret_values.get("rhbk_admin_password"),
                secret_values.get("oidc_admin_password"),
            )
            if oidc_admin_user:
                vars_data["satellite_oidc_admin_user"] = vault_ref("vault_rhbk_admin_user")
                vars_data["rhbk_admin_user"] = vault_ref("vault_rhbk_admin_user")
                vault_data["vault_rhbk_admin_user"] = QuotedString(str(oidc_admin_user))
                vault_data_changed = True
            if oidc_admin_password is not None:
                vars_data["satellite_oidc_admin_password"] = vault_ref("vault_rhbk_admin_password")
                vars_data["rhbk_admin_password"] = vault_ref("vault_rhbk_admin_password")
                vault_data["vault_rhbk_admin_password"] = QuotedString(str(oidc_admin_password))
                vault_data_changed = True
            if oidc_client_secret is not None:
                vars_data["satellite_oidc_client_secret"] = vault_ref(
                    "vault_satellite_oidc_client_secret"
                )
                vault_data["vault_satellite_oidc_client_secret"] = QuotedString(
                    str(oidc_client_secret)
                )
                vault_data_changed = True
            capsule_hostname = first_present(
                public_values.get("capsule_hostname"),
                public_values.get("capsule_host"),
            )
            if capsule_hostname is not None:
                vars_data["capsule_hostname"] = str(capsule_hostname)
                vars_data_changed = True
            if public_values.get("capsule_install_deployment_version") or public_values.get(
                "capsule_deployment_version"
            ):
                vars_data["capsule_install_deployment_version"] = str(
                    first_present(
                        public_values.get("capsule_install_deployment_version"),
                        public_values.get("capsule_deployment_version"),
                        public_values.get("deployment_version"),
                    )
                )
                vars_data_changed = True
            capsule_location = first_present(
                public_values.get("capsule_install_location"),
                public_values.get("capsule_location"),
                public_values.get("location"),
            )
            if capsule_location is not None:
                vars_data["capsule_install_location"] = str(capsule_location)
                vars_data_changed = True
            capsule_org_id = first_present(
                public_values.get("capsule_install_org_id"),
                public_values.get("capsule_org_id"),
                public_values.get("organization"),
            )
            if capsule_org_id is not None:
                vars_data["capsule_install_org_id"] = str(capsule_org_id)
                vars_data_changed = True
            capsule_satellite_fqdn = first_present(
                public_values.get("capsule_install_satellite_fqdn"),
                public_values.get("capsule_satellite_fqdn"),
            )
            if capsule_satellite_fqdn is not None:
                vars_data["capsule_install_satellite_fqdn"] = str(capsule_satellite_fqdn)
                vars_data_changed = True
            capsule_activation_key = first_present(
                public_values.get("capsule_install_activation_key"),
                public_values.get("capsule_activation_key"),
                secret_values.get("capsule_activation_key"),
                secret_values.get("capsule_install_activation_key"),
            )
            if capsule_activation_key is not None:
                vault_data["vault_capsule_activation_key"] = QuotedString(
                    str(capsule_activation_key)
                )
                vars_data["capsule_install_activation_key"] = vault_ref(
                    "vault_capsule_activation_key"
                )
                vault_data_changed = True
                vars_data_changed = True
            loadbalancer_activation_key = first_present(
                public_values.get("capsule_install_loadbalancer_activation_key"),
                public_values.get("loadbalancer_activation_key"),
                secret_values.get("loadbalancer_activation_key"),
            )
            if loadbalancer_activation_key is not None:
                vault_data["vault_capsule_loadbalancer_activation_key"] = QuotedString(
                    str(loadbalancer_activation_key)
                )
                vars_data["capsule_install_loadbalancer_activation_key"] = vault_ref(
                    "vault_capsule_loadbalancer_activation_key"
                )
                vault_data_changed = True
                vars_data_changed = True
            vg_name = first_present(
                public_values.get("capsule_install_vg_name"),
                public_values.get("capsule_vg_name"),
            )
            if vg_name is not None:
                vars_data["capsule_install_vg_name"] = str(vg_name)
                vars_data_changed = True
            for size_key, var_key in (
                ("capsule_pulp_size", "capsule_install_pulp_size"),
                ("capsule_pgsql_size", "capsule_install_pgsql_size"),
            ):
                size_value = first_present(
                    public_values.get(var_key),
                    public_values.get(size_key),
                )
                if size_value is not None:
                    vars_data[var_key] = QuotedString(str(size_value))
                    vars_data_changed = True
            data_disk_min_size = first_present(
                public_values.get("capsule_install_data_disk_min_size"),
                public_values.get("capsule_data_disk_min_size"),
            )
            if data_disk_min_size is not None:
                vars_data["capsule_install_data_disk_min_size"] = int(data_disk_min_size)
                vars_data_changed = True
            data_device_name = first_present(
                public_values.get("capsule_install_data_device_name"),
                public_values.get("capsule_data_device_name"),
            )
            if data_device_name is not None:
                vars_data["capsule_install_data_device_name"] = str(data_device_name)
                vars_data_changed = True
            data_device = first_present(
                public_values.get("capsule_install_data_device"),
                public_values.get("capsule_data_device"),
            )
            if data_device is not None:
                vars_data["capsule_install_data_device"] = str(data_device)
                vars_data_changed = True
            req_dirs = first_present(
                public_values.get("capsule_install_req_dirs"),
                public_values.get("capsule_req_dirs"),
            )
            if req_dirs:
                vars_data["capsule_install_req_dirs"] = copy.deepcopy(req_dirs)
                vars_data_changed = True
            if public_values.get("lifecycle_environments") is not None:
                vars_data["capsule_install_lifecycle_environments"] = copy.deepcopy(
                    public_values["lifecycle_environments"]
                )
                vars_data_changed = True
            if public_values.get("capsule_install_sync_wait_time") is not None:
                vars_data["capsule_install_sync_wait_time"] = int(
                    public_values["capsule_install_sync_wait_time"]
                )
                vars_data_changed = True
            if "capsule_install_setup_insights" in public_values:
                vars_data["capsule_install_setup_insights"] = as_bool(
                    public_values["capsule_install_setup_insights"], False
                )
                vars_data_changed = True
            if "satellite_haproxy" in public_values or "capsule_install_satellite_haproxy" in public_values:
                vars_data["capsule_install_satellite_haproxy"] = as_bool(
                    first_present(
                        public_values.get("capsule_install_satellite_haproxy"),
                        public_values.get("satellite_haproxy"),
                    ),
                    False,
                )
                vars_data_changed = True
            loadbalancer_fqdn = first_present(
                public_values.get("capsule_install_loadbalancer_fqdn"),
                public_values.get("loadbalancer_fqdn"),
            )
            if loadbalancer_fqdn is not None:
                vars_data["capsule_install_loadbalancer_fqdn"] = str(loadbalancer_fqdn)
                vars_data_changed = True
            vars_data.pop("oidc", None)

        if component == "cert_manager":
            if public_values.get("mode"):
                vars_data["ocp_cert_manager_mode"] = public_values["mode"]
            if public_values.get("idm_acme_directory_url"):
                vars_data.setdefault("idm", {})
                vars_data["idm"]["acme_directory_url"] = public_values["idm_acme_directory_url"]
            # Prefer uploaded CA PEM → files/certs/idm-root-ca.crt in the playbook repo.
            ca_b64 = first_present(
                public_values.get("idm_ca_bundle_content_base64"),
                secret_values.get("idm_ca_bundle_content_base64"),
                cfg.get("idm_ca_bundle_content_base64"),
            )
            if ca_b64:
                project_dir = env_dir.parents[2] if len(env_dir.parents) >= 3 else env_dir
                certs_dir = project_dir / "files" / "certs"
                certs_dir.mkdir(parents=True, exist_ok=True)
                ca_name = safe_upload_filename(
                    first_present(
                        public_values.get("idm_ca_bundle_filename"),
                        cfg.get("idm_ca_bundle_filename"),
                        "idm-root-ca.crt",
                    ),
                    "idm-root-ca.crt",
                )
                ca_target = certs_dir / ca_name
                try:
                    ca_target.write_bytes(base64.b64decode(str(ca_b64), validate=True))
                except (binascii.Error, ValueError) as exc:
                    raise SystemExit(
                        f"Invalid base64 IdM CA upload for {ca_target}: {exc}"
                    ) from exc
                try:
                    ca_pem_text = ca_target.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    ca_pem_text = ""
                ca_target.chmod(0o644)
                vars_data.setdefault("idm", {})
                vars_data["idm"]["ca_bundle_file"] = f"files/certs/{ca_name}"
                vars_data["idm_ca_bundle_file"] = f"files/certs/{ca_name}"
                # Embed PEM so Contoller jobs do not depend on cwd / project layout.
                if ca_pem_text.strip():
                    vars_data["idm"]["ca_bundle_pem"] = ca_pem_text
                    vars_data["idm_ca_bundle_pem"] = ca_pem_text
                vars_data_changed = True
            elif public_values.get("idm_ca_bundle_file"):
                vars_data.setdefault("idm", {})
                vars_data["idm"]["ca_bundle_file"] = public_values["idm_ca_bundle_file"]
                vars_data["idm_ca_bundle_file"] = public_values["idm_ca_bundle_file"]
                # If file already exists in the generated repo, also embed PEM.
                project_dir = env_dir.parents[2] if len(env_dir.parents) >= 3 else env_dir
                existing_ca = project_dir / str(public_values["idm_ca_bundle_file"])
                if existing_ca.is_file():
                    try:
                        ca_pem_text = existing_ca.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        ca_pem_text = ""
                    if ca_pem_text.strip():
                        vars_data["idm"]["ca_bundle_pem"] = ca_pem_text
                        vars_data["idm_ca_bundle_pem"] = ca_pem_text
                        vars_data_changed = True
            if public_values.get("awspca_namespace"):
                vars_data["ocp_awspca_namespace"] = public_values["awspca_namespace"]
            if public_values.get("awspca_secret_name"):
                vars_data["ocp_awspca_secret_name"] = public_values["awspca_secret_name"]
            if public_values.get("awspca_issuer_name"):
                vars_data["ocp_awspca_issuer_name"] = public_values["awspca_issuer_name"]
            if public_values.get("awspca_region"):
                vars_data["ocp_awspca_region"] = public_values["awspca_region"]
            if public_values.get("awspca_pca_arn"):
                vars_data["ocp_awspca_pca_arn"] = public_values["awspca_pca_arn"]
            if public_values.get("tls_crt"):
                vault_data["tls_crt"] = public_values["tls_crt"]
            # Never persist the raw base64 upload into group_vars (file is enough).
            for drop_key in (
                "idm_ca_bundle_content_base64",
                "idm_ca_bundle_filename",
            ):
                passthrough_public_values.pop(drop_key, None)
                vars_data.pop(drop_key, None)
                if isinstance(vars_data.get("component_config", {}).get(component), dict):
                    vars_data["component_config"][component].pop(drop_key, None)
            # Backfill embedded PEM from repo file so Contoller never depends on cwd.
            idm_block = vars_data.setdefault("idm", {})
            if not str(idm_block.get("ca_bundle_pem") or "").strip():
                project_dir = env_dir.parents[2] if len(env_dir.parents) >= 3 else env_dir
                candidates = []
                configured = first_present(
                    idm_block.get("ca_bundle_file"),
                    vars_data.get("idm_ca_bundle_file"),
                    public_values.get("idm_ca_bundle_file"),
                )
                if configured:
                    candidates.append(project_dir / str(configured))
                candidates.extend(
                    [
                        project_dir / "files" / "certs" / "ca.crt",
                        project_dir / "files" / "certs" / "idm-root-ca.crt",
                    ]
                )
                for candidate in candidates:
                    if candidate.is_file():
                        try:
                            pem = candidate.read_text(encoding="utf-8")
                        except UnicodeDecodeError:
                            pem = ""
                        if pem.strip():
                            idm_block["ca_bundle_pem"] = pem
                            vars_data["idm_ca_bundle_pem"] = pem
                            idm_block["ca_bundle_file"] = str(
                                candidate.relative_to(project_dir)
                            )
                            vars_data["idm_ca_bundle_file"] = idm_block["ca_bundle_file"]
                            vars_data_changed = True
                            break

        if component == "kafka":
            # Certified Operators catalog serves 3.2/3.3; channel 2.11 is dead and
            # leaves Subscriptions in ResolutionFailed.
            channel = str(
                first_present(
                    public_values.get("operator_channel"),
                    vars_data.get("operator_channel"),
                    "3.3",
                )
            ).strip()
            if (not channel) or channel.startswith("2."):
                channel = "3.3"
            vars_data["operator_channel"] = channel
            vars_data.setdefault("component_config", {}).setdefault("kafka", {})
            vars_data["component_config"]["kafka"]["operator_channel"] = channel
            vars_data["kafka_install_external_tls"] = False
            vars_data["kafka_install_use_ingress_cert"] = True
            vars_data_changed = True

        if component == "grafana":
            # Always rewrite — stale vars_grafana.yml with "5.20.0" wins over defaults
            # because bootstrap_resolve_component will not clobber defined vars.
            vars_data["operator_channel"] = "v5"
            vars_data["operator_name"] = "grafana-operator"
            vars_data["operator_source"] = "community-operators"
            vars_data["operator_source_namespace"] = "openshift-marketplace"
            vars_data["operator_csv_contains"] = "grafana-operator"
            vars_data["operator_name_substring"] = "grafana-operator"
            vars_data.setdefault("component_config", {}).setdefault("grafana", {})
            vars_data["component_config"]["grafana"]["operator_channel"] = "v5"
            vars_data.setdefault("components_env", {}).setdefault("grafana", {})
            vars_data["components_env"]["grafana"]["operator_channel"] = "v5"
            vars_data_changed = True

        if component == "eck":
            # Never pin a dead startingCSV; wait accepts any Succeeded eck CSV.
            vars_data["operator_starting_csv"] = ""
            vars_data["operator_channel"] = str(
                first_present(vars_data.get("operator_channel"), "stable")
            )
            vars_data.setdefault("component_config", {}).setdefault("eck", {})
            vars_data["component_config"]["eck"]["operator_starting_csv"] = ""
            vars_data_changed = True

        if component == "idm":
            vars_data.setdefault("components_env", {}).setdefault("idm", {})
            public_values.pop("storage", None)
            vars_data["component_config"][component].pop("storage", None)
            vars_data.pop("storage", None)
            vars_data["components_env"]["idm"].pop("storage", None)
            if public_values.get("hostname"):
                vars_data["components_env"]["idm"]["hostname"] = public_values["hostname"]
                vars_data["idm_hostname"] = public_values["hostname"]
                vars_data["idm_server_name"] = public_values["hostname"]
                vars_data["idm_configure_replica_server"] = public_values["hostname"]
                vars_data["ipaclient_servers"] = [public_values["hostname"]]
                vars_data["ipaclient_no_dns_lookup"] = True
            if public_values.get("domain"):
                vars_data["components_env"]["idm"]["domain"] = public_values["domain"]
                vars_data["idm_domain"] = public_values["domain"]
                vars_data["idm_configure_replica_domain"] = public_values["domain"]
                vars_data["ipaclient_domain"] = public_values["domain"]
            if public_values.get("realm"):
                vars_data["components_env"]["idm"]["realm"] = public_values["realm"]
                vars_data["idm_realm"] = public_values["realm"]
                vars_data["idm_configure_replica_realm"] = public_values["realm"]
                vars_data["ipaclient_realm"] = public_values["realm"]
            elif public_values.get("domain"):
                vars_data["ipaclient_realm"] = str(public_values["domain"]).upper()
                vars_data["idm_realm"] = str(public_values["domain"]).upper()
            if public_values.get("replica_hostname"):
                vars_data["idm_replica_hostname"] = public_values["replica_hostname"]
                vars_data["idm_configure_replica_hostname"] = public_values["replica_hostname"]
            if "replica_install_dns" in public_values:
                vars_data["idm_replica_install_dns"] = public_values["replica_install_dns"]
                vars_data["idm_configure_replica_setup_dns"] = public_values["replica_install_dns"]
            if "replica_install_ca" in public_values:
                vars_data["idm_replica_install_ca"] = public_values["replica_install_ca"]
                vars_data["idm_configure_replica_setup_ca"] = public_values["replica_install_ca"]
            if "auto_forwarders" in public_values:
                vars_data["idm_auto_forwarders"] = public_values["auto_forwarders"]
                vars_data["idm_configure_replica_auto_forwarders"] = public_values["auto_forwarders"]
            if public_values.get("custom_cert_file"):
                vars_data["idm_custom_cert_file"] = public_values["custom_cert_file"]
            if public_values.get("custom_cert_key_file"):
                vars_data["idm_custom_cert_key_file"] = public_values["custom_cert_key_file"]
            if public_values.get("custom_cert_chain_file"):
                vars_data["idm_custom_cert_chain_file"] = public_values["custom_cert_chain_file"]
            if public_values.get("ad_domain"):
                vars_data["idm_ad_trust_ad_domain"] = public_values["ad_domain"]
                vars_data["idm_ad_trust_ad_realm"] = str(public_values["ad_domain"]).upper()
            if public_values.get("ad_dc_hostname"):
                vars_data["idm_ad_trust_ad_dc_hostname"] = public_values["ad_dc_hostname"]
            if public_values.get("ad_dc_ip"):
                vars_data["idm_ad_trust_ad_dc_ip"] = public_values["ad_dc_ip"]
            if public_values.get("ad_admin"):
                vars_data["idm_ad_trust_ad_admin"] = public_values["ad_admin"]
            if "ad_two_way" in public_values:
                vars_data["idm_ad_trust_two_way"] = public_values["ad_two_way"]
            if public_values.get("ad_map_group"):
                vars_data["idm_ad_trust_map_ad_group"] = public_values["ad_map_group"]
            if public_values.get("ad_map_admins_group"):
                vars_data["idm_ad_trust_map_ad_admins_group"] = public_values["ad_map_admins_group"]
            if "ad_configure_groups" in public_values:
                vars_data["idm_ad_trust_configure_groups"] = public_values["ad_configure_groups"]

        if component == "rhel":
            vars_data.setdefault("components_env", {}).setdefault("rhel", {})
            vars_data["components_env"]["rhel"].update(public_values)

        if component == "stig":
            rhel_values = (preflight.get("component_config") or {}).get("rhel") or {}
            if rhel_values.get("compliance_profile"):
                vars_data["compliance_profile"] = rhel_values["compliance_profile"]
            if rhel_values.get("stig_profile"):
                vars_data["stig_profile"] = rhel_values["stig_profile"]
                vars_data["rhel_stig_profile"] = rhel_values["stig_profile"]
            if rhel_values.get("stig_engine"):
                vars_data["stig_engine"] = rhel_values["stig_engine"]
                vars_data.setdefault("components_env", {}).setdefault("rhel", {})
                vars_data["components_env"]["rhel"]["stig_engine"] = rhel_values["stig_engine"]
            if rhel_values.get("rhel_stig_cac_remediate") is not None:
                vars_data["rhel_stig_cac_remediate"] = rhel_values["rhel_stig_cac_remediate"]
                vars_data.setdefault("components_env", {}).setdefault("rhel", {})
                vars_data["components_env"]["rhel"]["rhel_stig_cac_remediate"] = rhel_values["rhel_stig_cac_remediate"]
            if public_values.get("profile"):
                vars_data["stig_profile"] = public_values["profile"]
                vars_data["rhel_stig_profile"] = public_values["profile"]
            if public_values.get("stig_engine"):
                vars_data["stig_engine"] = public_values["stig_engine"]
                vars_data.setdefault("components_env", {}).setdefault("rhel", {})
                vars_data["components_env"]["rhel"]["stig_engine"] = public_values["stig_engine"]
            if public_values.get("remediate") is not None:
                vars_data["rhel_stig_cac_remediate"] = public_values["remediate"]
                vars_data.setdefault("components_env", {}).setdefault("rhel", {})
                vars_data["components_env"]["rhel"]["rhel_stig_cac_remediate"] = public_values["remediate"]

        if component in ("quay", "kafka", "acs", "acm") and vars_data.get("storage"):
            normalized_storage = effective_storage_class(preflight, vars_data.get("storage"))
            if normalized_storage != vars_data.get("storage"):
                if normalized_storage:
                    vars_data["storage"] = normalized_storage
                    vars_data.setdefault("components_env", {}).setdefault(component, {})
                    vars_data["components_env"][component]["storage"] = normalized_storage
                else:
                    vars_data.pop("storage", None)
                    if component in vars_data.get("components_env", {}):
                        vars_data["components_env"][component].pop("storage", None)
                    vars_data.get("component_config", {}).get(component, {}).pop("storage", None)
                vars_data_changed = True

        write_yaml(vars_path, vars_data, "0644")
        if vault_data_changed:
            write_yaml(vault_path, vault_data, "0600")

    if secret_values:
        vault_data.setdefault("component_vault_config", {})
        vault_data["component_vault_config"][component] = {
            **vault_data["component_vault_config"].get(component, {}),
            **secret_values,
        }

        for k, v in secret_values.items():
            vault_data[k] = v

        if component == "aap":
            if secret_values.get("admin_password") is not None:
                vault_data["aap_admin_password"] = secret_values["admin_password"]
                vault_data["vault_controller_password"] = secret_values["admin_password"]
            vault_data.pop("admin_password", None)
            vault_data_changed = True

        if component == "satellite":
            if secret_values.get("service_account_password") is not None:
                vault_data["vault_satellite_service_account_password"] = secret_values["service_account_password"]
                vault_data["satellite_config_password"] = secret_values["service_account_password"]
                vault_data_changed = True
            if secret_values.get("admin_password") is not None:
                vault_data["vault_satellite_admin_password"] = secret_values["admin_password"]
                vault_data["satellite_config_admin_password"] = secret_values["admin_password"]
                vault_data["satellite_install_admin_password"] = secret_values["admin_password"]
                vault_data_changed = True
            rhn_org_id = first_present(
                public_values.get("satellite_install_rhn_org_id"),
                public_values.get("rhn_org_id"),
                public_values.get("org_id"),
                public_values.get("redhat_org_id"),
                public_values.get("satellite_rhn_org_id"),
                public_values.get("satellite_install_rhn_org_id"),
                secret_values.get("rhn_org_id"),
                secret_values.get("org_id"),
                secret_values.get("redhat_org_id"),
                secret_values.get("satellite_rhn_org_id"),
                secret_values.get("satellite_install_rhn_org_id"),
                secret_values.get("satellite_install_rhn_org_id"),
            )
            if rhn_org_id is not None:
                vault_data["vault_satellite_rhn_org_id"] = QuotedString(str(rhn_org_id))
                vault_data["satellite_install_rhn_org_id"] = QuotedString(str(rhn_org_id))
                vars_data["satellite_install_rhn_org_id"] = vault_ref("vault_satellite_rhn_org_id")
                vars_data["satellite_install_rhn_connected"] = True
                vars_data_changed = True
                vault_data_changed = True

            rhn_activation_key = first_present(
                secret_values.get("satellite_install_rhn_activation_key"),
                secret_values.get("admin_rhn_activation_key"),
                secret_values.get("satellite_admin_rhn_activation_key"),
                secret_values.get("satellite_install_admin_rhn_activation_key"),
                secret_values.get("rhn_activation_key"),
                secret_values.get("admin_activation_key"),
                public_values.get("admin_rhn_activation_key"),
                public_values.get("satellite_admin_rhn_activation_key"),
                public_values.get("satellite_install_admin_rhn_activation_key"),
                public_values.get("satellite_install_rhn_activation_key"),
                public_values.get("rhn_activation_key"),
                public_values.get("admin_activation_key"),
            )
            if rhn_activation_key is not None:
                vault_data["vault_satellite_rhn_activation_key"] = QuotedString(str(rhn_activation_key))
                vault_data["satellite_install_rhn_activation_key"] = QuotedString(str(rhn_activation_key))
                vars_data["satellite_install_rhn_activation_key"] = vault_ref("vault_satellite_rhn_activation_key")
                vars_data["satellite_install_rhn_connected"] = True
                vars_data_changed = True
                vault_data_changed = True

            client_activation_key = first_present(
                secret_values.get("activation_key"),
                secret_values.get("satellite_activation_key"),
                secret_values.get("client_activation_key"),
                secret_values.get("rhel_sat_reg_activation_key_name"),
                public_values.get("activation_key"),
                public_values.get("satellite_activation_key"),
                public_values.get("client_activation_key"),
                public_values.get("rhel_sat_reg_activation_key_name"),
            )
            if client_activation_key is not None:
                vars_data["satellite_activation_key"] = QuotedString(str(client_activation_key))
                vars_data["rhel_sat_reg_activation_key_name"] = QuotedString(str(client_activation_key))
                vars_data_changed = True

            if vars_data_changed:
                write_yaml(vars_path, vars_data, "0644")

        if component == "cert_manager":
            if secret_values.get("tls_key") is not None:
                vault_data["tls_key"] = secret_values["tls_key"]

        if component == "idm":
            if secret_values.get("admin_password") is not None:
                vault_data["vault_idm_admin_password"] = secret_values["admin_password"]
                vault_data["ipaadmin_password"] = secret_values["admin_password"]
                vault_data["idm_server_ipaadmin_password"] = secret_values["admin_password"]
                vault_data["idm_configure_replica_admin_password"] = secret_values["admin_password"]
                vault_data["idm_ad_trust_ipa_admin_password"] = secret_values["admin_password"]
            if secret_values.get("directory_manager_password") is not None:
                vault_data["vault_idm_directory_manager_password"] = secret_values["directory_manager_password"]
                vault_data["idm_configure_replica_dm_password"] = secret_values["directory_manager_password"]
            if secret_values.get("ad_admin_password") is not None:
                vault_data["vault_ad_trust_admin_password"] = secret_values["ad_admin_password"]
                vault_data["idm_ad_trust_ad_admin_password"] = secret_values["ad_admin_password"]

        if component in ("ec2_ami_copy", "ec2_instance", "aws_instance", "aws", "cert_manager"):
            merge_shared_aws_vault({**public_values, **secret_values})

        if component in ("ec2_ami_copy", "ec2_instance", "aws_instance"):
            if vault_path.exists():
                vault_path.unlink()
        elif component != "aws":
            write_yaml(vault_path, vault_data, "0600")


component_options = preflight.get("component_options") or {}
openshift_options = set(component_options.get("openshift") or [])
openshift = preflight.get("openshift") or {}
if openshift:
    if "openshift" not in selected_components:
        openshift = {}

if openshift:
    vars_path = env_dir / "vars_openshift.yml"
    vault_path = env_dir / "vault_openshift.yml"

    vars_data = load_yaml(vars_path)
    vault_data = load_yaml(vault_path)

    if openshift.get("api_host") is not None:
        vars_data["api_host"] = openshift.get("api_host")
        vars_data["host"] = openshift.get("api_host")

    if preflight.get("domain") is not None:
        vars_data["domain"] = preflight.get("domain")

    if openshift.get("apps_domain") is not None:
        vars_data["apps_domain"] = openshift.get("apps_domain")
        vars_data["app_domain"] = openshift.get("apps_domain")

    skip_tls_verify = bool(openshift.get("skip_tls_verify", True))
    vars_data["skip_tls_verify"] = skip_tls_verify
    vars_data["verify_ssl"] = not skip_tls_verify
    vars_data["validate_certs"] = not skip_tls_verify

    if openshift.get("token") is not None:
        vault_data["token"] = openshift.get("token")
        vault_data["openshift_token"] = openshift.get("token")

    use_kubeconfig = as_bool(openshift.get("use_kubeconfig"), False)
    kubeconfig_content = first_present(
        openshift.get("kubeconfig_content"),
        openshift.get("kubeconfig"),
    )
    if use_kubeconfig and kubeconfig_content is not None:
        vault_data["openshift_kubeconfig"] = kubeconfig_content
        vault_data["kubeconfig_content"] = kubeconfig_content
        vars_data["openshift_use_kubeconfig"] = True
    else:
        vault_data.pop("openshift_kubeconfig", None)
        vault_data.pop("kubeconfig_content", None)
        vars_data.pop("openshift_use_kubeconfig", None)

    vars_data["openshift_install_htpasswd_during_bootstrap"] = as_bool(
        openshift.get("install_htpasswd_during_bootstrap"),
        False,
    )
    vars_data["openshift_install_nfs_during_bootstrap"] = as_bool(
        openshift.get("install_nfs_during_bootstrap"),
        False,
    )

    if "nfs_csi" in openshift_options:
        nfs_server = first_present(
            openshift.get("nfs_server"),
            openshift.get("ocp_nfs_storage_server"),
        )
        nfs_share = first_present(
            openshift.get("nfs_share"),
            openshift.get("ocp_nfs_storage_share"),
        )
        if nfs_server is not None:
            vars_data["ocp_nfs_storage_server"] = str(nfs_server)
            vars_data["nfs_server"] = str(nfs_server)
        if nfs_share is not None:
            vars_data["ocp_nfs_storage_share"] = str(nfs_share)
            vars_data["nfs_share"] = str(nfs_share)
        vars_data["ocp_nfs_storage_class_name"] = str(
            first_present(
                openshift.get("nfs_storage_class_name"),
                openshift.get("ocp_nfs_storage_class_name"),
                "synology-nfs-csi",
            )
        )
        vars_data["ocp_nfs_storage_driver_version"] = str(
            first_present(
                openshift.get("nfs_driver_version"),
                openshift.get("ocp_nfs_storage_driver_version"),
                "4.11.0",
            )
        )
        vars_data["ocp_nfs_storage_nfs_version"] = str(
            first_present(
                openshift.get("nfs_version"),
                openshift.get("ocp_nfs_storage_nfs_version"),
                "4.1",
            )
        )
        vars_data["ocp_nfs_storage_create_test_namespace"] = as_bool(
            openshift.get("nfs_create_test_namespace"),
            True,
        )
        vars_data["ocp_nfs_storage_create_test_pvc"] = as_bool(
            openshift.get("nfs_create_test_pvc"),
            False,
        )
        vars_data["ocp_nfs_storage_test_namespace"] = str(
            first_present(
                openshift.get("nfs_test_namespace"),
                "synology-nfs-pv",
            )
        )
    else:
        for nfs_key in (
            "ocp_nfs_storage_server",
            "nfs_server",
            "ocp_nfs_storage_share",
            "nfs_share",
            "ocp_nfs_storage_class_name",
            "ocp_nfs_storage_driver_version",
            "ocp_nfs_storage_nfs_version",
            "ocp_nfs_storage_create_test_namespace",
            "ocp_nfs_storage_create_test_pvc",
            "ocp_nfs_storage_test_namespace",
        ):
            vars_data.pop(nfs_key, None)

    vars_data["openshift_install_iscsi_during_bootstrap"] = as_bool(
        openshift.get("install_iscsi_during_bootstrap"),
        False,
    )

    if "iscsi_csi" in openshift_options:
        iscsi_host = first_present(
            openshift.get("iscsi_dsm_host"),
            openshift.get("ocp_iscsi_storage_dsm_host"),
        )
        iscsi_user = first_present(
            openshift.get("iscsi_dsm_username"),
            openshift.get("ocp_iscsi_storage_dsm_username"),
        )
        iscsi_pass = first_present(
            openshift.get("iscsi_dsm_password"),
            openshift.get("ocp_iscsi_storage_dsm_password"),
        )
        if iscsi_host is not None:
            vars_data["ocp_iscsi_storage_dsm_host"] = str(iscsi_host)
            vars_data["iscsi_dsm_host"] = str(iscsi_host)
        if iscsi_user is not None:
            vault_data["ocp_iscsi_storage_dsm_username"] = str(iscsi_user)
            vault_data["iscsi_dsm_username"] = str(iscsi_user)
        if iscsi_pass is not None:
            vault_data["ocp_iscsi_storage_dsm_password"] = str(iscsi_pass)
            vault_data["iscsi_dsm_password"] = str(iscsi_pass)
        vars_data["ocp_iscsi_storage_dsm_port"] = int(
            first_present(
                openshift.get("iscsi_dsm_port"),
                openshift.get("ocp_iscsi_storage_dsm_port"),
                5000,
            )
        )
        vars_data["ocp_iscsi_storage_dsm_https"] = as_bool(
            openshift.get("iscsi_dsm_https"),
            False,
        )
        vars_data["ocp_iscsi_storage_class_name"] = str(
            first_present(
                openshift.get("iscsi_storage_class_name"),
                openshift.get("ocp_iscsi_storage_class_name"),
                "synology-iscsi-storage",
            )
        )
        vars_data["ocp_iscsi_storage_location"] = str(
            first_present(
                openshift.get("iscsi_location"),
                openshift.get("ocp_iscsi_storage_location"),
                "/volume1",
            )
        )
        vars_data["ocp_iscsi_storage_is_default"] = as_bool(
            openshift.get("iscsi_is_default"),
            True,
        )
        vars_data["ocp_iscsi_storage_install_snapshotter"] = as_bool(
            openshift.get("iscsi_install_snapshotter"),
            True,
        )
    else:
        for iscsi_key in (
            "ocp_iscsi_storage_dsm_host",
            "iscsi_dsm_host",
            "ocp_iscsi_storage_dsm_port",
            "ocp_iscsi_storage_dsm_https",
            "ocp_iscsi_storage_class_name",
            "ocp_iscsi_storage_location",
            "ocp_iscsi_storage_is_default",
            "ocp_iscsi_storage_install_snapshotter",
        ):
            vars_data.pop(iscsi_key, None)
        for iscsi_vault_key in (
            "ocp_iscsi_storage_dsm_username",
            "iscsi_dsm_username",
            "ocp_iscsi_storage_dsm_password",
            "iscsi_dsm_password",
        ):
            vault_data.pop(iscsi_vault_key, None)

    if "admin_htpasswd" in openshift_options:
        action = str(openshift.get("htpasswd_action") or "add").lower()
        if action not in ("add", "replace", "remove"):
            action = "add"
        vars_data["htpasswd_action"] = action
        users = openshift.get("htpasswd_users")
        normalized_users = []
        if isinstance(users, list):
            for user in users:
                if not isinstance(user, dict):
                    continue
                name = str(user.get("name") or "").strip()
                if not name:
                    continue
                password = str(user.get("password") or "").strip()
                if not password:
                    raise SystemExit(
                        f"Admin HTPasswd user '{name}' has an empty password. "
                        "Set a password in preflight (OpenShift → Admin HTPasswd); "
                        "there is no silent redhat123 default."
                    )
                normalized_users.append(
                    {
                        "name": name,
                        "password": password,
                        "role": user.get("role") or "cluster-admin",
                    }
                )
        if not normalized_users and (
            openshift.get("admin_username") or openshift.get("admin_password")
        ):
            admin_username = str(openshift.get("admin_username") or "admin").strip() or "admin"
            admin_password = str(openshift.get("admin_password") or "").strip()
            if not admin_password:
                raise SystemExit(
                    "Admin HTPasswd password is empty. "
                    "Set a password in preflight (OpenShift → Admin HTPasswd); "
                    "there is no silent redhat123 default."
                )
            normalized_users = [
                {
                    "name": admin_username,
                    "password": admin_password,
                    "role": openshift.get("admin_role") or "cluster-admin",
                }
            ]
        # Contoller JT uses component htpass_admin; env gen also creates admin_htpasswd stubs.
        htpass_vault_paths = [
            env_dir / "vault_htpass_admin.yml",
            env_dir / "vault_admin_htpasswd.yml",
        ]
        htpass_vars_paths = [
            env_dir / "vars_htpass_admin.yml",
            env_dir / "vars_admin_htpasswd.yml",
        ]
        if normalized_users:
            vault_data["htpasswd_users"] = normalized_users
            vault_data["htpasswd_pass"] = normalized_users[0].get("password") or ""
            for htpass_admin_vault_path in htpass_vault_paths:
                htpass_admin_vault = load_yaml(htpass_admin_vault_path)
                # Drop bogus stub keys (e.g. admin_htpasswd: redhat123 from old templates).
                htpass_admin_vault.pop("admin_htpasswd", None)
                htpass_admin_vault.pop("htpass_admin", None)
                htpass_admin_vault["htpasswd_users"] = copy.deepcopy(normalized_users)
                htpass_admin_vault["htpasswd_pass"] = normalized_users[0].get("password") or ""
                write_yaml(htpass_admin_vault_path, htpass_admin_vault, "0600")
            for htpass_admin_vars_path in htpass_vars_paths:
                htpass_admin_vars = load_yaml(htpass_admin_vars_path)
                htpass_admin_vars["htpasswd_action"] = action
                # Keep only role-relevant keys in the dedicated vars files.
                write_yaml(htpass_admin_vars_path, {"htpasswd_action": action}, "0644")
        else:
            raise SystemExit(
                "Admin HTPasswd is selected but no users with name+password were provided. "
                "Add at least one user under OpenShift → Admin HTPasswd."
            )
    else:
        vars_data.pop("htpasswd_action", None)
        vault_data.pop("htpasswd_users", None)
        vault_data.pop("htpasswd_pass", None)

    if "console_banner" in openshift_options and (
        openshift.get("banner_text")
        or str(openshift.get("banner_state") or "").lower() in ("delete", "absent")
    ):
        banner_state = str(openshift.get("banner_state") or "add").strip().lower()
        if banner_state in ("present",):
            banner_state = "add"
        if banner_state in ("new",):
            banner_state = "update"
        if banner_state in ("absent",):
            banner_state = "delete"
        if banner_state not in ("add", "update", "delete"):
            banner_state = "add"
        vars_data["state"] = banner_state
        vars_data["console_banner_state"] = banner_state
        vars_data["ocp_console_banner_state"] = banner_state
        if banner_state != "delete":
            if openshift.get("banner_text"):
                vars_data["ocp_console_banner_text"] = openshift.get("banner_text")
                vars_data["console_banner_text"] = openshift.get("banner_text")
            if openshift.get("banner_location"):
                vars_data["ocp_console_banner_location"] = openshift.get("banner_location")
            if openshift.get("banner_background_color"):
                vars_data["ocp_console_banner_background_color"] = openshift.get(
                    "banner_background_color"
                )
            if openshift.get("banner_text_color"):
                vars_data["ocp_console_banner_text_color"] = openshift.get(
                    "banner_text_color"
                )
    else:
        vars_data.pop("ocp_console_banner_text", None)
        vars_data.pop("console_banner_text", None)
        vars_data.pop("ocp_console_banner_location", None)
        vars_data.pop("ocp_console_banner_background_color", None)
        vars_data.pop("ocp_console_banner_text_color", None)
        vars_data.pop("state", None)
        vars_data.pop("console_banner_state", None)
        vars_data.pop("ocp_console_banner_state", None)

    write_yaml(vars_path, vars_data, "0644")
    write_yaml(vault_path, vault_data, "0600")

if "ldap_auth" in openshift_options:
    ldap_cfg = openshift.get("ldap_auth") or {}
    idp_name = str(
        first_present(
            ldap_cfg.get("idp_name"),
            "LDAP_IDM",
        )
    ).strip()
    ldap_config = {
        "enabled": "true",
        "vendor": "rhds",
        "connectionUrl": str(
            first_present(
                ldap_cfg.get("connection_url"),
                ldap_cfg.get("connectionUrl"),
                "ldap://idm.server.lab",
            )
            or "ldap://idm.server.lab"
        ),
        "bindDn": str(
            first_present(
                ldap_cfg.get("bind_dn"),
                ldap_cfg.get("bindDn"),
                "cn=Directory Manager",
            )
            or "cn=Directory Manager"
        ),
        "bindCredential": str(
            first_present(
                ldap_cfg.get("bind_credential"),
                ldap_cfg.get("bindCredential"),
                "",
            )
            or ""
        ),
        "usersDn": str(
            first_present(
                ldap_cfg.get("users_dn"),
                ldap_cfg.get("usersDn"),
                "cn=users,cn=accounts,dc=server,dc=lab",
            )
            or "cn=users,cn=accounts,dc=server,dc=lab"
        ),
        "authType": "simple",
        "usernameLDAPAttribute": str(
            first_present(
                ldap_cfg.get("username_ldap_attribute"),
                ldap_cfg.get("usernameLDAPAttribute"),
                "uid",
            )
            or "uid"
        ),
        "rdnLDAPAttribute": "uid",
        "uuidLDAPAttribute": "nsuniqueid",
        "userObjectClasses": "inetOrgPerson",
    }
    for ldap_vars_name in (
        "vars_ldap_auth_openshift.yml",
        "vars_openshift_ldap_auth.yml",
    ):
        ldap_vars_path = env_dir / ldap_vars_name
        ldap_vars = load_yaml(ldap_vars_path) if ldap_vars_path.exists() else {}
        if idp_name:
            ldap_vars.setdefault("openshift_ldap_auth", {})
            if isinstance(ldap_vars["openshift_ldap_auth"], dict):
                ldap_vars["openshift_ldap_auth"]["idp_name"] = idp_name
                if ldap_cfg.get("mapping_method"):
                    ldap_vars["openshift_ldap_auth"]["mapping_method"] = str(
                        ldap_cfg.get("mapping_method")
                    )
            ldap_vars.setdefault("components_env", {}).setdefault(
                "ldap_auth_openshift", {}
            )
            ldap_vars["components_env"]["ldap_auth_openshift"].setdefault(
                "openshift_ldap_auth", {}
            )
            ldap_vars["components_env"]["ldap_auth_openshift"]["openshift_ldap_auth"][
                "idp_name"
            ] = idp_name
            ldap_vars.setdefault("ocp_ldap_auth_config", {})
            if isinstance(ldap_vars["ocp_ldap_auth_config"], dict):
                ldap_vars["ocp_ldap_auth_config"]["idp_name"] = idp_name
        write_yaml(ldap_vars_path, ldap_vars, "0644")
    for ldap_vault_name in (
        "vault_ldap_auth_openshift.yml",
        "vault_openshift_ldap_auth.yml",
    ):
        ldap_vault_path = env_dir / ldap_vault_name
        ldap_vault = load_yaml(ldap_vault_path) if ldap_vault_path.exists() else {}
        existing = ldap_vault.get("ldap_config")
        if isinstance(existing, dict):
            merged = dict(existing)
            merged.update({k: v for k, v in ldap_config.items() if v not in (None, "")})
            # Keep existing bindCredential when form left password blank.
            if not str(ldap_config.get("bindCredential") or "").strip() and existing.get(
                "bindCredential"
            ):
                merged["bindCredential"] = existing.get("bindCredential")
            ldap_vault["ldap_config"] = merged
        else:
            ldap_vault["ldap_config"] = ldap_config
        write_yaml(ldap_vault_path, ldap_vault, "0600")

if "oauth_rhbk" in openshift_options:
    rhbk_vars_path = env_dir / "vars_rhbk.yml"
    oauth_cfg = openshift.get("oauth_rhbk") or {}
    if rhbk_vars_path.exists():
        rhbk_vars = load_yaml(rhbk_vars_path)
        idp_name = str(
            first_present(
                oauth_cfg.get("idp_name"),
                "Keycloak",
            )
        ).strip()
        client_id = str(
            first_present(
                oauth_cfg.get("client_id"),
                oauth_cfg.get("keycloak_client_id"),
                rhbk_vars.get("rhbk_client"),
            )
            or ""
        ).strip()
        realm = str(
            first_present(
                oauth_cfg.get("realm"),
                rhbk_vars.get("rhbk_realm"),
                rhbk_vars.get("ocp_rhbk_realm"),
                "rhlab",
            )
            or "rhlab"
        ).strip()
        keycloak_host = str(
            first_present(
                oauth_cfg.get("keycloak_hostname"),
                rhbk_vars.get("ocp_rhbk_hostname"),
                rhbk_vars.get("rhbk_hostname"),
            )
            or ""
        ).strip()
        keycloak_host = re.sub(r"^https?://", "", keycloak_host)
        keycloak_host = re.sub(r"/.*$", "", keycloak_host)
        scopes_raw = first_present(oauth_cfg.get("extra_scopes"), "groups")
        if isinstance(scopes_raw, list):
            extra_scopes = [str(s).strip() for s in scopes_raw if str(s).strip()]
        else:
            extra_scopes = [
                part.strip()
                for part in str(scopes_raw or "groups").replace("\n", ",").split(",")
                if part.strip()
            ]
        if not extra_scopes:
            extra_scopes = ["groups"]
        mapping_method = str(
            first_present(oauth_cfg.get("mapping_method"), "claim") or "claim"
        )
        if idp_name:
            rhbk_vars["openshift_oidc_idp_name"] = idp_name
        if client_id:
            rhbk_vars["rhbk_client"] = client_id
            rhbk_vars["openshift_oidc_client_id"] = client_id
        if realm:
            rhbk_vars["rhbk_realm"] = realm
            rhbk_vars["ocp_rhbk_realm"] = realm
        if keycloak_host:
            rhbk_vars["ocp_rhbk_hostname"] = keycloak_host
            rhbk_vars["rhbk_hostname"] = keycloak_host
        oidc_auth = rhbk_vars.get("openshift_oidc_auth")
        if not isinstance(oidc_auth, dict):
            oidc_auth = {}
        oidc_auth = {
            **oidc_auth,
            "enabled": True,
            "openshift_oidc_idp_name": idp_name or oidc_auth.get("openshift_oidc_idp_name") or "Keycloak",
            "keycloak_client_id": client_id or oidc_auth.get("keycloak_client_id") or "",
            "openshift_oidc_mapping_method": mapping_method,
            "openshift_oauth_resource_name": "cluster",
            "extra_scopes": extra_scopes,
        }
        if keycloak_host and realm:
            oidc_auth["issuer"] = f"https://{keycloak_host}/realms/{realm}"
        rhbk_vars["openshift_oidc_auth"] = oidc_auth
        write_yaml(rhbk_vars_path, rhbk_vars, "0644")

        rhbk_vault_path = env_dir / "vault_rhbk.yml"
        if rhbk_vault_path.exists():
            rhbk_vault = load_yaml(rhbk_vault_path)
            rhbk_vault_changed = False
            for stale_key in (
                "openshift_oidc_idp_name",
                "rhbk_client",
                "openshift_oidc_client_id",
                "rhbk_realm",
                "ocp_rhbk_realm",
                "ocp_rhbk_hostname",
                "rhbk_hostname",
                "openshift_oidc_auth",
            ):
                if stale_key in rhbk_vault:
                    rhbk_vault.pop(stale_key, None)
                    rhbk_vault_changed = True
            if rhbk_vault_changed:
                write_yaml(rhbk_vault_path, rhbk_vault, "0600")

route_options = {
    opt
    for opt in openshift_options
    if opt
    in {
        "discover_routes_print",
        "alternate_routes",
        "discover_routes_alt",
    }
}
if route_options and "openshift" in selected_components:
    routes_vars_path = env_dir / "vars_routes.yml"
    routes_vars = load_yaml(routes_vars_path)

    discover_cfg = openshift.get("discover_routes") or {}
    scope = str(discover_cfg.get("scope") or "all").strip().lower()
    namespaces = discover_cfg.get("namespaces") or []
    if isinstance(namespaces, str):
        namespaces = [
            item.strip()
            for item in re.split(r"[\s,]+", namespaces)
            if item.strip()
        ]
    if scope == "selected_apps":
        selected_apps = (preflight.get("component_apps") or {}).get("openshift") or []
        derived = []
        for app in selected_apps:
            derived.extend(APP_ROUTE_NAMESPACES.get(str(app).lower(), []))
        namespaces = sorted(set(derived))
    elif scope != "namespaces":
        namespaces = []

    if openshift.get("api_host") is not None:
        routes_vars["api_host"] = openshift.get("api_host")
        routes_vars["host"] = openshift.get("api_host")

    routes_vars["ocp_discover_routes_namespaces"] = namespaces

    alt_cfg = openshift.get("alternate_routes") or {}
    suffix = str(alt_cfg.get("route_name_suffix") or "-alt").strip() or "-alt"
    routes_vars["alt_routes_suffix"] = suffix
    routes_vars["alt_routes_force_replace"] = as_bool(
        alt_cfg.get("force_replace"),
        False,
    )

    raw_labels = alt_cfg.get("route_labels") or {}
    label_map = {}
    if isinstance(raw_labels, list):
        for item in raw_labels:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            label_map[key] = str(item.get("value") or "")
    elif isinstance(raw_labels, dict):
        label_map = {str(k): str(v) for k, v in raw_labels.items()}

    ingress_name = str(alt_cfg.get("ingress_controller_name") or "").strip()
    if ingress_name:
        routes_vars["alt_routes_ingress_controller_name"] = ingress_name
        routes_vars["ocp_alt_routes_ingress_controller_name"] = ingress_name
    else:
        routes_vars.pop("alt_routes_ingress_controller_name", None)
        routes_vars.pop("ocp_alt_routes_ingress_controller_name", None)

    routes_vars["alt_routes_default_labels"] = label_map
    write_yaml(routes_vars_path, routes_vars, "0644")

    routes_vault_path = env_dir / "vault_routes.yml"
    routes_vault = load_yaml(routes_vault_path)
    openshift_vault_path = env_dir / "vault_openshift.yml"
    openshift_vault = load_yaml(openshift_vault_path) if openshift_vault_path.exists() else {}
    token = first_present(
        openshift.get("token"),
        openshift_vault.get("token"),
        routes_vault.get("token"),
    )
    if token is not None:
        routes_vault["token"] = token
    write_yaml(routes_vault_path, routes_vault, "0600")

for component, cfg in (preflight.get("component_config") or {}).items():
    if component not in selected_components:
        continue
    merge_component(component, cfg)

print(f"Overlayed preflight component values into {env_dir}")
