"""Sequential thinking trace schema for Tier-3 local SLM builders.

This module defines the deterministic JSON schema (simple dataclass)
that Tier-3 SLMs must emit as their scratchpad output. It is intentionally
small and JSON-only to simplify parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable


@dataclass(frozen=True)
class SequentialThinkingTrace:
    steps: tuple[Any, ...]
    conclusion: str = ""
    confidence: float = 0.0

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_steps(cls, steps: Iterable[Any], conclusion: str = "", confidence: float = 0.0) -> "SequentialThinkingTrace":
        return cls(steps=tuple(steps), conclusion=conclusion, confidence=float(confidence))
