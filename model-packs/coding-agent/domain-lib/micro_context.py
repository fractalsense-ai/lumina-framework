"""Micro-context builder for coding-agent job turns.

Produces a compact, deterministic micro-context dictionary from a
validated job payload and optional runtime metadata. The runtime adapter
consumes the `tier` field for routing decisions.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any


def build_micro_context(validated_job: dict[str, Any], extras: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a micro-context using the normalized job dict.

    `validated_job` should be the `normalized` dict returned by
    `job_intake.validate_job(...).normalized`.
    """
    priority = (validated_job or {}).get("priority") or "normal"
    tier_map = {"high": "critical", "normal": "ok", "low": "minor"}
    exec_map = {"high": 1, "normal": 2, "low": 3}
    tier = tier_map.get(priority, "ok")

    files = list(validated_job.get("files") or [])

    return {
        "job_id": (validated_job.get("title")[:64] if validated_job.get("title") else None),
        "tier": tier,
        "execution_tier": exec_map.get(priority, 3),
        "scope_valid": bool(validated_job.get("title") and validated_job.get("description")),
        "files": files,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "extras": extras or {},
    }
