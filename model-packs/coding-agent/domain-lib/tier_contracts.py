from __future__ import annotations

from dataclasses import dataclass, asdict
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
        )
