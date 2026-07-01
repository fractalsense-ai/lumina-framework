"""Deterministic teardown coordinator stub.

This module provides a minimal coordinator that declares the cleanup intent
and a simple in-memory executor used by tests. Real resource cleanup should be
performed by System Pack adapters; this is intentionally conservative.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from datetime import datetime


@dataclass
class TeardownResult:
    plan_id: str
    slice_id: str
    removed: List[str]
    failed: List[Dict[str, Any]]
    started_at: str = datetime.utcnow().isoformat() + "Z"
    completed_at: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def execute_teardown(plan_id: str, slice_context: Dict[str, Any]) -> TeardownResult:
    # Minimal executor used in tests: mark provided 'temp_paths' as removed.
    temp_paths = slice_context.get("temp_paths") or []
    removed = []
    failed = []
    for p in temp_paths:
        try:
            # Do not actually delete on disk in tests; just simulate success.
            removed.append(str(p))
        except Exception as exc:
            failed.append({"path": str(p), "error": str(exc)})

    res = TeardownResult(plan_id=plan_id, slice_id=slice_context.get("slice_id", ""), removed=removed, failed=failed, completed_at=datetime.utcnow().isoformat() + "Z")
    return res
