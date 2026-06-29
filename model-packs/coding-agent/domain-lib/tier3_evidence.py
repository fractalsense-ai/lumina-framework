from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class Tier3ExecutionEvidence:
    slice_id: str
    node_id: str
    model_class: str
    status: str
    ready: bool
    retryable: bool
    retry_after_seconds: float = 0.0
    attempt_count: int = 0
    error_class: str = ""
    error_message: str = ""
    completed_node_ids: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tier3ExecutionEvidence":
        payload = data or {}
        return cls(
            slice_id=str(payload.get("slice_id", "")),
            node_id=str(payload.get("node_id", "")),
            model_class=str(payload.get("model_class", "llm")),
            status=str(payload.get("status", "unknown")),
            ready=bool(payload.get("ready", False)),
            retryable=bool(payload.get("retryable", False)),
            retry_after_seconds=float(payload.get("retry_after_seconds", 0.0)),
            attempt_count=int(payload.get("attempt_count", 0)),
            error_class=str(payload.get("error_class", "")),
            error_message=str(payload.get("error_message", "")),
            completed_node_ids=[str(x) for x in list(payload.get("completed_node_ids") or [])],
            denied_tools=[str(x) for x in list(payload.get("denied_tools") or [])],
            allowed_tools=[str(x) for x in list(payload.get("allowed_tools") or [])],
            created_at=str(payload.get("created_at", datetime.utcnow().isoformat() + "Z")),
        )
