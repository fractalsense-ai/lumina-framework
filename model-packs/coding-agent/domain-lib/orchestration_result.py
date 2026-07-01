from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OrchestrationResult:
    executed_slice_ids: List[str] = field(default_factory=list)
    completed_node_ids: List[str] = field(default_factory=list)
    failed_node_id: str | None = None
    halt_reason: str = "budget_exhausted"
    halt_reason_compat: str = "budget_exhausted"
    evidence_timeline: List[Dict[str, Any]] = field(default_factory=list)
    evidence_commit: Dict[str, Any] | None = None
    teardown_result: Dict[str, Any] | None = None
    execution_context: Dict[str, Any] = field(default_factory=dict)
    budget: Dict[str, Any] = field(default_factory=dict)
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executed_slice_ids": [str(value) for value in list(self.executed_slice_ids or [])],
            "completed_node_ids": [str(value) for value in list(self.completed_node_ids or [])],
            "failed_node_id": None if self.failed_node_id is None else str(self.failed_node_id),
            "halt_reason": str(self.halt_reason),
            "halt_reason_compat": str(self.halt_reason_compat),
            "telemetry": dict(self.telemetry or {}),
            "evidence_timeline": [dict(value or {}) for value in list(self.evidence_timeline or [])],
            "evidence_commit": None if self.evidence_commit is None else dict(self.evidence_commit),
            "teardown_result": None if self.teardown_result is None else dict(self.teardown_result),
            "execution_context": dict(self.execution_context or {}),
            "budget": dict(self.budget or {}),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "OrchestrationResult":
        payload = data or {}
        failed_node = payload.get("failed_node_id")
        return cls(
            executed_slice_ids=[str(value) for value in list(payload.get("executed_slice_ids") or [])],
            completed_node_ids=[str(value) for value in list(payload.get("completed_node_ids") or [])],
            failed_node_id=None if failed_node in (None, "") else str(failed_node),
            halt_reason=str(payload.get("halt_reason", "budget_exhausted")),
            halt_reason_compat=str(payload.get("halt_reason_compat", payload.get("halt_reason", "budget_exhausted"))),
            evidence_timeline=[dict(value or {}) for value in list(payload.get("evidence_timeline") or [])],
            evidence_commit=None if payload.get("evidence_commit") is None else dict(payload.get("evidence_commit") or {}),
            teardown_result=None if payload.get("teardown_result") is None else dict(payload.get("teardown_result") or {}),
            telemetry=dict(payload.get("telemetry") or {}),
            execution_context=dict(payload.get("execution_context") or {}),
            budget=dict(payload.get("budget") or {}),
        )
