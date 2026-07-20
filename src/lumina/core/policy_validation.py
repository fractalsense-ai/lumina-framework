"""Shared validation for versioned Business Ops policy documents."""
from __future__ import annotations

from typing import Any


_TOP_LEVEL_POLICY_FIELDS = frozenset({"schema_version", "policy_version", "defaults", "organizations"})


def validate_policy_header(config: dict[str, Any], *, policy_name: str) -> dict[str, Any]:
    """Reject unsupported policy document shapes before resolving overrides."""
    unknown = set(config) - _TOP_LEVEL_POLICY_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"{policy_name} policy has unknown top-level fields: {names}")
    if config.get("schema_version") != "1.0.0":
        raise ValueError(f"unsupported {policy_name} policy schema_version")
    return config