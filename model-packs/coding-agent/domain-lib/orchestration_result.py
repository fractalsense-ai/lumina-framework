from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OrchestrationResult:
    executed_slice_ids: List[str] = field(default_factory=list)
    completed_node_ids: List[str] = field(default_factory=list)
    failed_node_id: str | None = None
    halt_reason: str = "budget_exhausted"
    evidence_timeline: List[Dict[str, Any]] = field(default_factory=list)
    execution_context: Dict[str, Any] = field(default_factory=dict)
    budget: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executed_slice_ids": [str(value) for value in list(self.executed_slice_ids or [])],
            "completed_node_ids": [str(value) for value in list(self.completed_node_ids or [])],
            "failed_node_id": None if self.failed_node_id is None else str(self.failed_node_id),
            "halt_reason": str(self.halt_reason),
            "evidence_timeline": [dict(value or {}) for value in list(self.evidence_timeline or [])],
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
            evidence_timeline=[dict(value or {}) for value in list(payload.get("evidence_timeline") or [])],
            execution_context=dict(payload.get("execution_context") or {}),
            budget=dict(payload.get("budget") or {}),
        )
