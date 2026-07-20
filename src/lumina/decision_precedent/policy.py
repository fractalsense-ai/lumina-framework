"""Business Ops decision-precedent policy loading and safe override resolution."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina.core.policy_validation import validate_policy_header
from lumina.core.yaml_loader import load_yaml

_POLICY_FIELDS = frozenset({
    "candidate_limit",
    "suggest_threshold",
    "confirmation_threshold",
    "stale_after_days",
    "stale_penalty",
    "missing_precedent_penalty",
    "high_risk_classes",
    "confirmation_risk_classes",
})
_RISK_CLASS_FIELDS = frozenset({"high_risk_classes", "confirmation_risk_classes"})


@dataclass(frozen=True)
class DecisionPrecedentPolicy:
    """Resolved deterministic policy for one authenticated organization/site."""

    policy_version: int
    candidate_limit: int
    suggest_threshold: float
    confirmation_threshold: float
    stale_after_days: int
    stale_penalty: float
    missing_precedent_penalty: float
    high_risk_classes: tuple[str, ...]
    confirmation_risk_classes: tuple[str, ...]
    organization_id: str
    site_id: str


def _require_scope(identifier: str, field_name: str) -> str:
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError(f"decision precedent requires {field_name}")
    return identifier.strip()


def _as_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"decision precedent policy {field_name} must be a mapping")
    return value


def _merge_policy(base: dict[str, Any], override: dict[str, Any], field_name: str) -> dict[str, Any]:
    unknown = set(override) - _POLICY_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"decision precedent policy {field_name} has unknown fields: {names}")
    merged = dict(base)
    merged.update(override)
    return merged


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"decision precedent policy {field_name} must be a finite number")
    numeric = float(value)
    if not 0 <= numeric <= 1:
        raise ValueError(f"decision precedent policy {field_name} must be between 0 and 1")
    return numeric


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"decision precedent policy {field_name} must be a positive integer")
    return value


def _risk_classes(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"decision precedent policy {field_name} must contain non-empty strings")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"decision precedent policy {field_name} must be unique")
    return normalized


def _validate_resolved_policy(
    policy: dict[str, Any], *, policy_version: int, organization_id: str, site_id: str
) -> DecisionPrecedentPolicy:
    missing = _POLICY_FIELDS - set(policy)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"decision precedent policy defaults are missing: {names}")
    if isinstance(policy_version, bool) or not isinstance(policy_version, int) or policy_version < 1:
        raise ValueError("decision precedent policy policy_version must be a positive integer")
    suggest_threshold = _number(policy["suggest_threshold"], "suggest_threshold")
    confirmation_threshold = _number(policy["confirmation_threshold"], "confirmation_threshold")
    if confirmation_threshold > suggest_threshold:
        raise ValueError("decision precedent policy confirmation_threshold cannot exceed suggest_threshold")
    high_risk_classes = _risk_classes(policy["high_risk_classes"], "high_risk_classes")
    confirmation_risk_classes = _risk_classes(
        policy["confirmation_risk_classes"], "confirmation_risk_classes"
    )
    overlap = set(high_risk_classes) & set(confirmation_risk_classes)
    if overlap:
        raise ValueError("decision precedent policy risk classes cannot overlap")
    return DecisionPrecedentPolicy(
        policy_version=policy_version,
        candidate_limit=_positive_integer(policy["candidate_limit"], "candidate_limit"),
        suggest_threshold=suggest_threshold,
        confirmation_threshold=confirmation_threshold,
        stale_after_days=_positive_integer(policy["stale_after_days"], "stale_after_days"),
        stale_penalty=_number(policy["stale_penalty"], "stale_penalty"),
        missing_precedent_penalty=_number(
            policy["missing_precedent_penalty"], "missing_precedent_penalty"
        ),
        high_risk_classes=high_risk_classes,
        confirmation_risk_classes=confirmation_risk_classes,
        organization_id=organization_id,
        site_id=site_id,
    )


def resolve_decision_precedent_policy(
    config: dict[str, Any], *, organization_id: str, site_id: str
) -> DecisionPrecedentPolicy:
    """Resolve site, organization, then default policy for authenticated scope."""
    organization_id = _require_scope(organization_id, "organization_id")
    site_id = _require_scope(site_id, "site_id")
    config = validate_policy_header(config, policy_name="decision precedent")
    defaults = _as_mapping(config.get("defaults"), "defaults")
    resolved = _merge_policy({}, defaults, "defaults")
    organizations = _as_mapping(config.get("organizations", {}), "organizations")
    organization_override = _as_mapping(
        organizations.get(organization_id, {}), f"organizations.{organization_id}"
    )
    sites = _as_mapping(organization_override.get("sites", {}), f"organizations.{organization_id}.sites")
    organization_fields = {key: value for key, value in organization_override.items() if key != "sites"}
    resolved = _merge_policy(resolved, organization_fields, f"organizations.{organization_id}")
    site_override = _as_mapping(
        sites.get(site_id, {}), f"organizations.{organization_id}.sites.{site_id}"
    )
    resolved = _merge_policy(resolved, site_override, f"organizations.{organization_id}.sites.{site_id}")
    return _validate_resolved_policy(
        resolved,
        policy_version=config.get("policy_version"),
        organization_id=organization_id,
        site_id=site_id,
    )


def load_decision_precedent_policy(
    config_path: str | Path, *, organization_id: str, site_id: str
) -> DecisionPrecedentPolicy:
    """Load and resolve policy from a Business Ops configuration file."""
    return resolve_decision_precedent_policy(
        load_yaml(config_path), organization_id=organization_id, site_id=site_id
    )