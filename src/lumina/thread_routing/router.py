"""Pure, deterministic decisions over already scoped thread candidates."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from lumina.thread_routing.policy import ThreadRoutingPolicy

RoutingAction = Literal["attach_existing", "create_new", "fork_from"]
RationaleCode = Literal[
    "high_confidence_match",
    "no_eligible_match",
    "topic_drift",
    "ambiguous_attach",
    "manual_policy",
    "operator_override",
]


@dataclass(frozen=True)
class ThreadCandidate:
    """One scope-filtered summary hit supplied by institutional retrieval."""

    thread_id: str
    summary_record_id: str
    score: float

    def __post_init__(self) -> None:
        if not self.thread_id or not self.summary_record_id:
            raise ValueError("thread candidates require thread and summary record identifiers")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ValueError("thread candidate score must be numeric")
        if not 0 <= self.score <= 1:
            raise ValueError("thread candidate score must be between 0 and 1")


@dataclass(frozen=True)
class ThreadRoutingDecision:
    """Transcript-free, auditable choice for routing one incoming turn."""

    decision_id: str
    organization_id: str
    site_id: str
    actor_id: str
    decision: RoutingAction
    thread_id: str
    source_thread_id: str | None
    policy_version: int
    confidence: float
    rationale_code: RationaleCode
    operator_confirmation_required: bool
    candidates: tuple[ThreadCandidate, ...]
    operator_override: bool = False

    def as_record(self, *, created_utc: datetime | None = None) -> dict[str, object]:
        """Serialize the decision as a schema-valid, transcript-free record."""
        timestamp = created_utc or datetime.now(UTC)
        return {
            "schema_version": "1.0.0",
            "decision_id": self.decision_id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "actor_id": self.actor_id,
            "decision": self.decision,
            "thread_id": self.thread_id,
            "source_thread_id": self.source_thread_id,
            "policy_version": self.policy_version,
            "confidence": self.confidence,
            "rationale_code": self.rationale_code,
            "operator_confirmation_required": self.operator_confirmation_required,
            "operator_override": self.operator_override,
            "candidates": [
                {
                    "thread_id": candidate.thread_id,
                    "summary_record_id": candidate.summary_record_id,
                    "score": candidate.score,
                    "rank": rank,
                }
                for rank, candidate in enumerate(self.candidates, start=1)
            ],
            "created_utc": timestamp.isoformat().replace("+00:00", "Z"),
        }


def _new_thread_id() -> str:
    return f"thread-{uuid.uuid4()}"


def _ordered_candidates(candidates: list[ThreadCandidate], limit: int) -> tuple[ThreadCandidate, ...]:
    return tuple(sorted(candidates, key=lambda candidate: (-candidate.score, candidate.thread_id))[:limit])


def decide_thread_route(
    candidates: list[ThreadCandidate],
    policy: ThreadRoutingPolicy,
    *,
    actor_id: str,
    active_thread_id: str | None = None,
    decision_id: str | None = None,
    new_thread_id: str | None = None,
) -> ThreadRoutingDecision:
    """Choose attach, create, or fork without inspecting raw transcript text."""
    if not actor_id or not actor_id.strip():
        raise ValueError("thread routing requires actor_id")
    ordered = _ordered_candidates(candidates, policy.candidate_limit)
    best = ordered[0] if ordered else None
    active = next((candidate for candidate in ordered if candidate.thread_id == active_thread_id), None)
    generated_thread_id = new_thread_id or _new_thread_id()

    decision: RoutingAction
    thread_id: str
    source_thread_id: str | None = None
    confidence = best.score if best else 0.0
    rationale: RationaleCode

    if policy.manual_only:
        decision = "create_new"
        thread_id = generated_thread_id
        rationale = "manual_policy"
    elif best is not None and best.score >= policy.attach_threshold:
        decision = "attach_existing"
        thread_id = best.thread_id
        rationale = "high_confidence_match"
    elif active_thread_id and (active is None or active.score < policy.fork_threshold):
        decision = "fork_from"
        thread_id = generated_thread_id
        source_thread_id = active_thread_id
        confidence = active.score if active else 0.0
        rationale = "topic_drift"
    else:
        decision = "create_new"
        thread_id = generated_thread_id
        rationale = "no_eligible_match"

    ambiguous = (
        decision == "attach_existing"
        and len(ordered) > 1
        and best is not None
        and best.score - ordered[1].score <= policy.ambiguity_margin
    )
    if ambiguous:
        rationale = "ambiguous_attach"
    confirmation_required = (
        policy.manual_only
        or ambiguous
        or decision in policy.require_operator_confirmation_for
    )
    return ThreadRoutingDecision(
        decision_id=decision_id or str(uuid.uuid4()),
        organization_id=policy.organization_id,
        site_id=policy.site_id,
        actor_id=actor_id.strip(),
        decision=decision,
        thread_id=thread_id,
        source_thread_id=source_thread_id,
        policy_version=policy.policy_version,
        confidence=confidence,
        rationale_code=rationale,
        operator_confirmation_required=confirmation_required,
        candidates=ordered,
    )