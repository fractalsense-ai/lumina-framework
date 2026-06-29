from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class PlanNode:
    node_id: str
    description: str
    depends_on: List[str]
    tier_hint: int = 2
    # Action type indicates what kind of action this node requires.
    # Examples: "code", "document", "review". Defaults to "code" for
    # backward compatibility with existing nodes.
    action_type: str = "code"
    # Optional lineage to a parent/global node when this node is derived into
    # a micro-DAG. Empty means this node is already global/root-level.
    parent_node_id: str = ""


@dataclass
class PlanDAG:
    nodes: List[PlanNode]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": [asdict(n) for n in self.nodes], "created_at": self.created_at}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanDAG":
        nodes = [PlanNode(**n) for n in data.get("nodes", [])]
        return cls(nodes=nodes, created_at=data.get("created_at") or datetime.utcnow().isoformat() + "Z")


@dataclass
class ArchitectPlan:
    plan_id: str
    root_job_id: str
    global_dag: PlanDAG
    system_state_refs: List[str] = field(default_factory=list)
    tier_assignments: Dict[str, int] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "root_job_id": self.root_job_id,
            "global_dag": self.global_dag.to_dict(),
            "system_state_refs": list(self.system_state_refs or []),
            "tier_assignments": dict(self.tier_assignments or {}),
            "validation_errors": list(self.validation_errors or []),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchitectPlan":
        return cls(
            plan_id=str(data.get("plan_id", "")),
            root_job_id=str(data.get("root_job_id", "")),
            global_dag=PlanDAG.from_dict(data.get("global_dag") or {}),
            system_state_refs=list(data.get("system_state_refs") or []),
            tier_assignments={str(k): int(v) for k, v in dict(data.get("tier_assignments") or {}).items()},
            validation_errors=list(data.get("validation_errors") or []),
            created_at=data.get("created_at") or datetime.utcnow().isoformat() + "Z",
        )


@dataclass
class TaskSlice:
    slice_id: str
    node_id: str
    task_description: str
    allowed_tools: List[str]
    context_budget_tokens: int = 1024
    tier: int = 3
    # Model class to execute this slice. Examples: "llm", "slm". Default
    # remains "llm" to preserve current behavior.
    model_class: str = "llm"
    depends_on: List[str] = field(default_factory=list)
    parent_node_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskSlice":
        return cls(
            slice_id=data["slice_id"],
            node_id=data.get("node_id", ""),
            task_description=data.get("task_description", ""),
            allowed_tools=list(data.get("allowed_tools") or []),
            context_budget_tokens=int(data.get("context_budget_tokens", 1024)),
            tier=int(data.get("tier", 3)),
            model_class=str(data.get("model_class", "llm")),
            depends_on=list(data.get("depends_on") or []),
            parent_node_id=str(data.get("parent_node_id", "")),
        )


@dataclass
class ExecutionContext:
    completed_node_ids: List[str] = field(default_factory=list)
    failed_node_ids: List[str] = field(default_factory=list)
    retry_counts: Dict[str, int] = field(default_factory=dict)
    max_retries_per_node: int = 2
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completed_node_ids": list(self.completed_node_ids or []),
            "failed_node_ids": list(self.failed_node_ids or []),
            "retry_counts": {str(k): int(v) for k, v in dict(self.retry_counts or {}).items()},
            "max_retries_per_node": int(self.max_retries_per_node),
            "base_backoff_seconds": float(self.base_backoff_seconds),
            "max_backoff_seconds": float(self.max_backoff_seconds),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "ExecutionContext":
        payload = data or {}
        return cls(
            completed_node_ids=[str(x) for x in list(payload.get("completed_node_ids") or [])],
            failed_node_ids=[str(x) for x in list(payload.get("failed_node_ids") or [])],
            retry_counts={str(k): int(v) for k, v in dict(payload.get("retry_counts") or {}).items()},
            max_retries_per_node=int(payload.get("max_retries_per_node", 2)),
            base_backoff_seconds=float(payload.get("base_backoff_seconds", 1.0)),
            max_backoff_seconds=float(payload.get("max_backoff_seconds", 30.0)),
        )
