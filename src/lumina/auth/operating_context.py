"""Validation helpers for organization/site operating contexts."""
from __future__ import annotations

from typing import Any


def normalize_operating_memberships(value: Any) -> list[dict[str, Any]]:
    """Validate and normalize persisted organization/site memberships."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("operating_memberships must be a list")

    normalized: list[dict[str, Any]] = []
    organization_ids: set[str] = set()
    for membership in value:
        if not isinstance(membership, dict):
            raise ValueError("operating memberships must be mappings")
        if set(membership) - {"organization_id", "site_ids", "site_roles"}:
            raise ValueError("operating membership contains unsupported fields")
        organization_id = membership.get("organization_id")
        site_ids = membership.get("site_ids")
        site_roles = membership.get("site_roles", {})
        if not isinstance(organization_id, str) or not organization_id.strip():
            raise ValueError("operating membership requires organization_id")
        if organization_id in organization_ids:
            raise ValueError("operating memberships must not repeat organization_id")
        if not isinstance(site_ids, list) or not site_ids:
            raise ValueError("operating membership requires site_ids")
        clean_sites: list[str] = []
        for site_id in site_ids:
            if not isinstance(site_id, str) or not site_id.strip():
                raise ValueError("operating membership site_ids must be non-empty strings")
            if site_id.strip() in clean_sites:
                raise ValueError("operating membership site_ids must be unique")
            clean_sites.append(site_id.strip())
        if not isinstance(site_roles, dict) or any(
            site_id not in clean_sites or not isinstance(role, str) or not role.strip()
            for site_id, role in site_roles.items()
        ):
            raise ValueError("site_roles must map assigned site IDs to non-empty roles")
        organization_ids.add(organization_id.strip())
        normalized.append(
            {
                "organization_id": organization_id.strip(),
                "site_ids": clean_sites,
                "site_roles": {site_id: role.strip() for site_id, role in site_roles.items()},
            }
        )
    return normalized


def resolve_operating_context(
    memberships: Any,
    *,
    organization_id: str,
    site_id: str,
) -> dict[str, str | None]:
    """Return a validated active context or reject an unassigned site."""
    if not isinstance(organization_id, str) or not organization_id.strip():
        raise ValueError("operating context requires organization_id")
    if not isinstance(site_id, str) or not site_id.strip():
        raise ValueError("operating context requires site_id")
    organization_id = organization_id.strip()
    site_id = site_id.strip()
    for membership in normalize_operating_memberships(memberships):
        if membership["organization_id"] == organization_id and site_id in membership["site_ids"]:
            roles = membership["site_roles"]
            return {
                "organization_id": organization_id,
                "site_id": site_id,
                "site_role": roles.get(site_id),
            }
    raise ValueError("actor is not assigned to the requested organization and site")


def default_operating_context(memberships: Any) -> dict[str, str | None] | None:
    """Return the first configured context for login, or None when unassigned."""
    normalized = normalize_operating_memberships(memberships)
    if not normalized:
        return None
    membership = normalized[0]
    return resolve_operating_context(
        normalized,
        organization_id=membership["organization_id"],
        site_id=membership["site_ids"][0],
    )


def operating_context_from_claims(claims: dict[str, Any]) -> dict[str, str | None] | None:
    """Extract exactly one active context from a verified JWT payload."""
    organization_id = claims.get("organization_id")
    site_id = claims.get("site_id")
    if organization_id is None and site_id is None:
        return None
    if not isinstance(organization_id, str) or not organization_id.strip():
        raise ValueError("JWT operating context requires organization_id")
    if not isinstance(site_id, str) or not site_id.strip():
        raise ValueError("JWT operating context requires site_id")
    context: dict[str, str | None] = {
        "organization_id": organization_id.strip(),
        "site_id": site_id.strip(),
        "site_role": None,
    }
    device_id = claims.get("device_id")
    if device_id is not None:
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("JWT device_id must be a non-empty string")
        context["device_id"] = device_id.strip()
    return context


def contexts_match(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    """Return whether two JWT-like mappings carry the same active scope."""
    return operating_context_from_claims(left or {}) == operating_context_from_claims(right or {})