from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List
from datetime import datetime, UTC


@dataclass
class TelemetryEvent:
    event_type: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "TelemetryEvent":
        payload = data or {}
        timestamp = payload.get("timestamp") or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return cls(
            event_type=str(payload.get("event_type", "")),
            timestamp=str(timestamp),
            payload=dict(payload.get("payload") or {}),
        )


@dataclass
class OrchestrationTurnSummary:
    plan_id: str
    executed_slices: List[str] = field(default_factory=list)
    halt_reason: str = ""
    halt_reason_compat: str = ""
    budget_snapshot: Dict[str, Any] = field(default_factory=dict)
    evidence_summary: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "OrchestrationTurnSummary":
        payload = data or {}
        return cls(
            plan_id=str(payload.get("plan_id", "default")),
            executed_slices=[str(x) for x in list(payload.get("executed_slices") or [])],
            halt_reason=str(payload.get("halt_reason", "")),
            halt_reason_compat=str(payload.get("halt_reason_compat", "")),
            budget_snapshot=dict(payload.get("budget_snapshot") or {}),
            evidence_summary=[dict(x or {}) for x in list(payload.get("evidence_summary") or [])],
        )
