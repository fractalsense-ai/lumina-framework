from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4


@dataclass
class ExecutionCheckpoint:
    plan_id: str
    checkpoint_id: str
    execution_context: Dict[str, Any]
    timestamp: str
    source: str = "runtime"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "checkpoint_id": str(self.checkpoint_id),
            "execution_context": dict(self.execution_context or {}),
            "timestamp": str(self.timestamp),
            "source": str(self.source or "runtime"),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "ExecutionCheckpoint":
        payload = data or {}
        return cls(
            plan_id=str(payload.get("plan_id", "")),
            checkpoint_id=str(payload.get("checkpoint_id") or uuid4()),
            execution_context=dict(payload.get("execution_context") or {}),
            timestamp=str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
            source=str(payload.get("source") or "runtime"),
        )


@dataclass
class ExecutionStateStore:
    checkpoints: List[ExecutionCheckpoint] = field(default_factory=list)
    retention_limit: int = 10

    def save_checkpoint(self, plan_id: str, execution_context: Dict[str, Any], source: str = "runtime") -> ExecutionCheckpoint:
        checkpoint = ExecutionCheckpoint(
            plan_id=str(plan_id or "default"),
            checkpoint_id=str(uuid4()),
            execution_context=dict(execution_context or {}),
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source=str(source or "runtime"),
        )
        self.checkpoints.append(checkpoint)
        self._prune_for_plan(checkpoint.plan_id)
        return checkpoint

    def load_latest_checkpoint(self, plan_id: str) -> ExecutionCheckpoint | None:
        normalized = str(plan_id or "default")
        matches = [c for c in self.checkpoints if c.plan_id == normalized]
        if not matches:
            return None
        return matches[-1]

    def list_checkpoints(self, plan_id: str | None = None) -> List[ExecutionCheckpoint]:
        if plan_id is None:
            matches = list(self.checkpoints)
        else:
            normalized = str(plan_id or "default")
            matches = [c for c in self.checkpoints if c.plan_id == normalized]
        return matches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retention_limit": int(self.retention_limit),
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.list_checkpoints()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "ExecutionStateStore":
        payload = data or {}
        retention = int(payload.get("retention_limit", 10))
        retention = max(1, retention)
        checkpoints = [ExecutionCheckpoint.from_dict(item) for item in list(payload.get("checkpoints") or [])]
        store = cls(checkpoints=checkpoints, retention_limit=retention)

        for plan_id in {c.plan_id for c in checkpoints}:
            store._prune_for_plan(plan_id)
        return store

    def _prune_for_plan(self, plan_id: str) -> None:
        normalized = str(plan_id or "default")
        plan_checkpoints = [c for c in self.checkpoints if c.plan_id == normalized]
        if len(plan_checkpoints) <= self.retention_limit:
            return

        keep_ids = {c.checkpoint_id for c in plan_checkpoints[-self.retention_limit :]}
        self.checkpoints = [c for c in self.checkpoints if c.plan_id != normalized or c.checkpoint_id in keep_ids]
