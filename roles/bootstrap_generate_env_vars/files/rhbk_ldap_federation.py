# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Keycloak LDAP federation ``ldap_config`` / group mapper defaults.

FreeIPA (IdM) runs on 389 Directory Server. Keycloak's vendor label is often
``rhds``, but FreeIPA-specific attributes (``ipaUniqueID``, subtree search,
posix object classes) must still be applied. Never invent bind credentials,
Base DN, or server URLs - only fill attribute defaults when the operator
selected federation and left those fields unset.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional


def _s(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first(*values: Any) -> str:
    for value in values:
        text = _s(value)
        if text:
            return text
    return ""


def is_freeipa_provider(provider: Any, public: Optional[Mapping[str, Any]] = None) -> bool:
    """True when the form/options indicate FreeIPA / IdM LDAP."""
    pub = public or {}
    token = _s(provider).lower()
    if token in {"freeipa", "idm", "ipa", "rhds", "ldap"}:
        # Explicit FreeIPA / IdM markers win; plain ``ldap`` alone is not enough.
        if token in {"freeipa", "idm", "ipa"}:
            return True
    for key in ("federation_directory", "federation_vendor", "ldap_vendor"):
        if _s(pub.get(key)).lower() in {"freeipa", "idm", "ipa"}:
            return True
    # Lab convention: usersDn under cn=accounts implies FreeIPA tree.
    users_dn = _first(pub.get("federation_users_dn"), pub.get("usersDn")).lower()
    if "cn=accounts" in users_dn:
        return True
    return token in {"freeipa", "idm", "ipa"}


def freeipa_ldap_attribute_defaults() -> dict[str, str]:
    """Keycloak LDAP attribute defaults appropriate for FreeIPA / IdM."""
    return {
        "vendor": "rhds",
        "authType": "simple",
        "editMode": "READ_ONLY",
        "importEnabled": "true",
        "syncRegistrations": "false",
        "usernameLDAPAttribute": "uid",
        "rdnLDAPAttribute": "uid",
        # FreeIPA unique id (not RHDS nsuniqueid).
        "uuidLDAPAttribute": "ipaUniqueID",
        "userObjectClasses": "inetOrgPerson, posixAccount",
        # SUBTREE - FreeIPA accounts are not always one level under usersDn.
        "searchScope": "2",
        "connectionPooling": "true",
        "pagination": "true",
        "startTls": "false",
        "useTruststoreSpi": "ldapsOnly",
        "batchSizeForSync": "1000",
        "fullSyncPeriod": "-1",
        "changedSyncPeriod": "-1",
        "enabled": "true",
    }


def freeipa_ldap_group_mapper_defaults(users_dn: str = "") -> dict[str, str]:
    """group-ldap-mapper defaults for FreeIPA ``cn=groups,cn=accounts,...``."""
    groups_dn = ""
    users = _s(users_dn)
    if users.lower().startswith("cn=users,"):
        groups_dn = "cn=groups," + users[len("cn=users,") :]
    elif "cn=accounts" in users.lower():
        # Fallback: replace users -> groups in the RDN only.
        groups_dn = users.replace("cn=users", "cn=groups", 1)
    return {
        "groups.dn": groups_dn,
        "group.name.ldap.attribute": "cn",
        "group.object.classes": "groupOfNames",
        "preserve.group.inheritance": "false",
        "ignore.missing.groups": "false",
        "membership.ldap.attribute": "member",
        "membership.attribute.type": "DN",
        # Empty user attribute is correct for DN membership in Keycloak.
        "membership.user.ldap.attribute": "",
        "mode": "READ_ONLY",
        "user.roles.retrieve.strategy": "LOAD_GROUPS_BY_MEMBER_ATTRIBUTE",
    }


def build_rhbk_ldap_config(
    *,
    public: Mapping[str, Any],
    secret: Mapping[str, Any],
    existing: Optional[Mapping[str, Any]] = None,
    apply_freeipa_defaults: bool = True,
) -> dict[str, Any]:
    """Merge form federation_* fields into a Keycloak ``ldap_config`` dict.

    Empty form strings never wipe a previously good value. Missing required
    connection fields stay absent so the role can fail with a clear assert
    instead of creating a blank Connection URL in Keycloak.
    """
    pub = dict(public or {})
    sec = dict(secret or {})
    # Drop blank existing values so they cannot block form/federation_* fills
    # (empty connectionUrl/bindDn in vault was the blank-Keycloak failure mode).
    merged: dict[str, Any] = {
        key: value for key, value in dict(existing or {}).items() if _s(value)
    }

    provider = _first(pub.get("federation_provider"), pub.get("federation_directory"), "ldap")
    use_freeipa = apply_freeipa_defaults and is_freeipa_provider(provider, pub)

    if use_freeipa:
        for key, value in freeipa_ldap_attribute_defaults().items():
            # Do not override an explicit existing non-empty value.
            if not _s(merged.get(key)):
                merged[key] = value
        # Correct common RHDS-only leftovers when the FreeIPA tree is in use
        # (vendor=rhds alone previously left nsuniqueid / one-level search).
        if _s(merged.get("uuidLDAPAttribute")).lower() == "nsuniqueid":
            merged["uuidLDAPAttribute"] = "ipaUniqueID"
        if _s(merged.get("searchScope")) == "1":
            merged["searchScope"] = "2"
        classes = _s(merged.get("userObjectClasses")).lower()
        if classes and "posixaccount" not in classes.replace(" ", ""):
            merged["userObjectClasses"] = "inetOrgPerson, posixAccount"
    else:
        merged.setdefault("vendor", "rhds")
        merged.setdefault("enabled", "true")
        merged.setdefault("authType", "simple")
        merged.setdefault("usernameLDAPAttribute", "uid")
        merged.setdefault("rdnLDAPAttribute", "uid")
        merged.setdefault("uuidLDAPAttribute", "nsuniqueid")
        merged.setdefault("userObjectClasses", "inetOrgPerson")
        merged.setdefault("searchScope", "1")

    field_map = (
        ("connectionUrl", ("federation_ldap_url", "connectionUrl", "connection_url")),
        ("bindDn", ("federation_bind_dn", "bindDn", "bind_dn")),
        ("usersDn", ("federation_users_dn", "usersDn", "users_dn")),
        ("bindCredential", ("federation_bind_password", "bindCredential", "bind_credential")),
    )
    sources: dict[str, Mapping[str, Any]] = {
        "federation_ldap_url": pub,
        "connectionUrl": pub,
        "connection_url": pub,
        "federation_bind_dn": pub,
        "bindDn": pub,
        "bind_dn": pub,
        "federation_users_dn": pub,
        "usersDn": pub,
        "users_dn": pub,
        "federation_bind_password": sec,
        "bindCredential": sec,
        "bind_credential": sec,
    }
    for target, keys in field_map:
        incoming = _first(*(sources[k].get(k) for k in keys if k in sources))
        if incoming:
            merged[target] = incoming
        # else: keep existing; never write ""

    # Vendor override from form when provided.
    vendor = _first(pub.get("federation_vendor"), pub.get("ldap_vendor"))
    if vendor:
        merged["vendor"] = vendor if vendor.lower() not in {"freeipa", "idm", "ipa"} else "rhds"

    return merged


def merge_ldap_config_into_vault(
    vault_data: MutableMapping[str, Any],
    ldap_config: Mapping[str, Any],
) -> bool:
    """Write ``ldap_config`` into vault data. Returns True when changed."""
    existing = vault_data.get("ldap_config")
    if not isinstance(existing, dict):
        vault_data["ldap_config"] = {
            key: value for key, value in dict(ldap_config).items() if _s(value)
        }
        return True
    before = {key: value for key, value in existing.items() if _s(value)}
    updated = dict(before)
    for key, value in ldap_config.items():
        if _s(value):
            updated[key] = value
    # Remove keys that remain blank after merge.
    updated = {key: value for key, value in updated.items() if _s(value)}
    vault_data["ldap_config"] = updated
    return updated != before


def required_ldap_fields_missing(ldap_config: Mapping[str, Any]) -> list[str]:
    """Return required Keycloak LDAP keys that are blank."""
    missing = []
    for key in ("connectionUrl", "bindDn", "usersDn", "bindCredential"):
        if not _s(ldap_config.get(key)):
            missing.append(key)
    return missing
