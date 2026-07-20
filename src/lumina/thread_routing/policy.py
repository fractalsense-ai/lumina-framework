"""Business Ops routing-policy loading and scope-safe override resolution."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina.core.yaml_loader import load_yaml

_POLICY_FIELDS = frozenset({
    "attach_threshold",
    "fork_threshold",
    "ambiguity_margin",
    "recap_interval_turns",
    "candidate_limit",
    "manual_only",
    "require_operator_confirmation_for",
})
_CONFIRMATION_ACTIONS = frozenset({
    "attach_existing",
    "create_new",
    "fork_from",
    "ambiguous_attach",
})


@dataclass(frozen=True)
class ThreadRoutingPolicy:
    """Resolved policy for one authenticated organization and site."""

    policy_version: int
    attach_threshold: float
    fork_threshold: float
    ambiguity_margin: float
    recap_interval_turns: int
    candidate_limit: int
    manual_only: bool
    require_operator_confirmation_for: tuple[str, ...]
    organization_id: str
    site_id: str


def _require_scope(identifier: str, field_name: str) -> str:
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError(f"thread routing requires {field_name}")
    return identifier.strip()


def _as_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"thread routing policy {field_name} must be a mapping")
    return value


def _merge_policy(base: dict[str, Any], override: dict[str, Any], field_name: str) -> dict[str, Any]:
    unknown = set(override) - _POLICY_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"thread routing policy {field_name} has unknown fields: {names}")
    merged = dict(base)
    merged.update(override)
    return merged


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"thread routing policy {field_name} must be a finite number")
    numeric = float(value)
    if not 0 <= numeric <= 1:
        raise ValueError(f"thread routing policy {field_name} must be between 0 and 1")
    return numeric


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"thread routing policy {field_name} must be a positive integer")
    return value


def _validate_resolved_policy(policy: dict[str, Any], *, policy_version: int, organization_id: str, site_id: str) -> ThreadRoutingPolicy:
    missing = _POLICY_FIELDS - set(policy)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"thread routing policy defaults are missing: {names}")
    unknown = set(policy) - _POLICY_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"thread routing policy has unknown fields: {names}")
    if isinstance(policy_version, bool) or not isinstance(policy_version, int) or policy_version < 1:
        raise ValueError("thread routing policy policy_version must be a positive integer")

    attach_threshold = _number(policy["attach_threshold"], "attach_threshold")
    fork_threshold = _number(policy["fork_threshold"], "fork_threshold")
    if fork_threshold > attach_threshold:
        raise ValueError("thread routing policy fork_threshold cannot exceed attach_threshold")
    confirmation_actions = policy["require_operator_confirmation_for"]
    if not isinstance(confirmation_actions, list) or any(
        not isinstance(action, str) or action not in _CONFIRMATION_ACTIONS
        for action in confirmation_actions
    ):
        raise ValueError("thread routing policy requires valid confirmation actions")
    if len(set(confirmation_actions)) != len(confirmation_actions):
        raise ValueError("thread routing policy confirmation actions must be unique")
    if not isinstance(policy["manual_only"], bool):
        raise ValueError("thread routing policy manual_only must be boolean")

    return ThreadRoutingPolicy(
        policy_version=policy_version,
        attach_threshold=attach_threshold,
        fork_threshold=fork_threshold,
        ambiguity_margin=_number(policy["ambiguity_margin"], "ambiguity_margin"),
        recap_interval_turns=_positive_integer(policy["recap_interval_turns"], "recap_interval_turns"),
        candidate_limit=_positive_integer(policy["candidate_limit"], "candidate_limit"),
        manual_only=policy["manual_only"],
        require_operator_confirmation_for=tuple(confirmation_actions),
        organization_id=organization_id,
        site_id=site_id,
    )


def resolve_thread_routing_policy(
    config: dict[str, Any],
    *,
    organization_id: str,
    site_id: str,
) -> ThreadRoutingPolicy:
    """Resolve site, organization, then default policy for authenticated scope."""
    organization_id = _require_scope(organization_id, "organization_id")
    site_id = _require_scope(site_id, "site_id")
    unknown = set(config) - {"schema_version", "policy_version", "defaults", "organizations"}
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"thread routing policy has unknown top-level fields: {names}")
    if config.get("schema_version") != "1.0.0":
        raise ValueError("unsupported thread routing policy schema_version")
    policy_version = config.get("policy_version")
    defaults = _as_mapping(config.get("defaults"), "defaults")
    resolved = _merge_policy({}, defaults, "defaults")

    organizations = config.get("organizations", {})
    organizations = _as_mapping(organizations, "organizations")
    organization_override = organizations.get(organization_id, {})
    organization_override = _as_mapping(organization_override, f"organizations.{organization_id}")
    sites = organization_override.get("sites", {})
    sites = _as_mapping(sites, f"organizations.{organization_id}.sites")
    organization_fields = {key: value for key, value in organization_override.items() if key != "sites"}
    resolved = _merge_policy(resolved, organization_fields, f"organizations.{organization_id}")

    site_override = sites.get(site_id, {})
    site_override = _as_mapping(site_override, f"organizations.{organization_id}.sites.{site_id}")
    resolved = _merge_policy(resolved, site_override, f"organizations.{organization_id}.sites.{site_id}")
    return _validate_resolved_policy(
        resolved,
        policy_version=policy_version,
        organization_id=organization_id,
        site_id=site_id,
    )


def load_thread_routing_policy(
    config_path: str | Path,
    *,
    organization_id: str,
    site_id: str,
) -> ThreadRoutingPolicy:
    """Load and resolve a policy file for an authenticated scope."""
    config = load_yaml(config_path)
    return resolve_thread_routing_policy(
        config,
        organization_id=organization_id,
        site_id=site_id,
    )