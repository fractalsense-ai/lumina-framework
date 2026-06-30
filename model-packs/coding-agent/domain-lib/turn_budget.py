from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
import time


@dataclass
class TurnBudget:
    max_tokens: int = 0
    max_time_seconds: float = 0.0
    max_slices_per_turn: int = 1
    started_at_epoch: float = field(default_factory=time.time)
    consumed_tokens: int = 0
    executed_slices: int = 0

    @classmethod
    def from_params(cls, params: Dict[str, Any] | None) -> "TurnBudget":
        payload = params or {}
        nested = payload.get("turn_budget") if isinstance(payload.get("turn_budget"), dict) else {}

        max_tokens = nested.get("max_tokens", payload.get("max_tokens", 0))
        max_time = nested.get("max_time_seconds", payload.get("max_time_seconds", 0.0))
        max_slices = nested.get("max_slices_per_turn", payload.get("max_slices_per_turn", 1))

        return cls(
            max_tokens=max(0, int(max_tokens or 0)),
            max_time_seconds=max(0.0, float(max_time or 0.0)),
            max_slices_per_turn=max(1, int(max_slices or 1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_tokens": int(self.max_tokens),
            "max_time_seconds": float(self.max_time_seconds),
            "max_slices_per_turn": int(self.max_slices_per_turn),
            "started_at_epoch": float(self.started_at_epoch),
            "consumed_tokens": int(self.consumed_tokens),
            "executed_slices": int(self.executed_slices),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "TurnBudget":
        payload = data or {}
        return cls(
            max_tokens=max(0, int(payload.get("max_tokens", 0) or 0)),
            max_time_seconds=max(0.0, float(payload.get("max_time_seconds", 0.0) or 0.0)),
            max_slices_per_turn=max(1, int(payload.get("max_slices_per_turn", 1) or 1)),
            started_at_epoch=float(payload.get("started_at_epoch", time.time())),
            consumed_tokens=max(0, int(payload.get("consumed_tokens", 0) or 0)),
            executed_slices=max(0, int(payload.get("executed_slices", 0) or 0)),
        )

    def time_remaining(self, now_epoch: float | None = None) -> float | None:
        if self.max_time_seconds <= 0:
            return None
        now = float(time.time() if now_epoch is None else now_epoch)
        elapsed = max(0.0, now - float(self.started_at_epoch))
        return max(0.0, float(self.max_time_seconds) - elapsed)

    def can_execute_slice(self, now_epoch: float | None = None) -> bool:
        if self.executed_slices >= self.max_slices_per_turn:
            return False
        if self.max_tokens > 0 and self.consumed_tokens >= self.max_tokens:
            return False
        remaining = self.time_remaining(now_epoch)
        if remaining is not None and remaining <= 0:
            return False
        return True

    def record_slice(self, token_count: int = 0) -> None:
        self.executed_slices = int(self.executed_slices) + 1
        self.consumed_tokens = int(self.consumed_tokens) + max(0, int(token_count or 0))


def budget_exhaustion_reason(turn_budget: TurnBudget, now_epoch: float | None = None) -> str:
    if turn_budget.executed_slices >= turn_budget.max_slices_per_turn:
        return "budget_exhausted"
    if turn_budget.max_tokens > 0 and turn_budget.consumed_tokens >= turn_budget.max_tokens:
        return "budget_exhausted"
    remaining = turn_budget.time_remaining(now_epoch)
    if remaining is not None and remaining <= 0:
        return "budget_exhausted"
    return "budget_available"
