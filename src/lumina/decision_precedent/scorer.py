"""Pure deterministic confidence scoring over already scope-filtered evidence."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from lumina.decision_precedent.policy import DecisionPrecedentPolicy

DecisionTier = Literal["suggest_only", "require_confirmation", "mandatory_escalation"]
RecencyBand = Literal["current", "stale"]


@dataclass(frozen=True)
class PrecedentCandidate:
    """A scope-filtered summary candidate without transcript content."""

    summary_record_id: str
    thread_id: str
    similarity: float
    created_utc: datetime

    def __post_init__(self) -> None:
        if not self.summary_record_id or not self.thread_id:
            raise ValueError("precedent candidates require summary and thread identifiers")
        if isinstance(self.similarity, bool) or not isinstance(self.similarity, (int, float)):
            raise ValueError("precedent candidate similarity must be numeric")
        if not 0 <= self.similarity <= 1:
            raise ValueError("precedent candidate similarity must be between 0 and 1")
        if self.created_utc.tzinfo is None:
            raise ValueError("precedent candidate created_utc must include a timezone")


@dataclass(frozen=True)
class PrecedentMatch:
    """A normalized, rank-stable source record used for confidence evidence."""

    summary_record_id: str
    thread_id: str
    similarity: float
    created_utc: datetime
    recency_band: RecencyBand
    rank: int


@dataclass(frozen=True)
class DecisionConfidenceScore:
    """Fully explainable score with a policy-enforced action tier."""

    record_id: str
    organization_id: str
    site_id: str
    actor_id: str
    policy_version: int
    risk_class: str
    similarity_score: float
    recency_penalty: float
    missing_precedent_penalty: float
    final_score: float
    tier: DecisionTier
    rationale_codes: tuple[str, ...]
    precedent_matches: tuple[PrecedentMatch, ...]

    def as_record(self, *, created_utc: datetime | None = None) -> dict[str, object]:
        """Serialize schema-valid evidence without raw input text or transcript data."""
        timestamp = created_utc or datetime.now(UTC)
        return {
            "record_id": self.record_id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "actor_id": self.actor_id,
            "policy_version": self.policy_version,
            "risk_class": self.risk_class,
            "similarity_score": self.similarity_score,
            "recency_penalty": self.recency_penalty,
            "missing_precedent_penalty": self.missing_precedent_penalty,
            "final_score": self.final_score,
            "tier": self.tier,
            "rationale_codes": list(self.rationale_codes),
            "precedent_matches": [
                {
                    "record_id": f"{self.record_id}:match:{match.rank}",
                    "organization_id": self.organization_id,
                    "site_id": self.site_id,
                    "actor_id": self.actor_id,
                    "summary_record_id": match.summary_record_id,
                    "thread_id": match.thread_id,
                    "similarity": match.similarity,
                    "created_utc": match.created_utc.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                    "recency_band": match.recency_band,
                    "rank": match.rank,
                }
                for match in self.precedent_matches
            ],
            "created_utc": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }


def _require_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"decision confidence requires {field_name}")
    return value.strip()


def _ordered_matches(
    candidates: list[PrecedentCandidate], policy: DecisionPrecedentPolicy, *, evaluated_utc: datetime
) -> tuple[PrecedentMatch, ...]:
    cutoff = evaluated_utc - __import__("datetime").timedelta(days=policy.stale_after_days)
    ordered = sorted(candidates, key=lambda candidate: (-candidate.similarity, candidate.summary_record_id))
    matches: list[PrecedentMatch] = []
    for rank, candidate in enumerate(ordered[: policy.candidate_limit], start=1):
        band: RecencyBand = "stale" if candidate.created_utc.astimezone(UTC) < cutoff else "current"
        matches.append(PrecedentMatch(
            summary_record_id=candidate.summary_record_id,
            thread_id=candidate.thread_id,
            similarity=float(candidate.similarity),
            created_utc=candidate.created_utc,
            recency_band=band,
            rank=rank,
        ))
    return tuple(matches)


def score_decision_precedent(
    candidates: list[PrecedentCandidate],
    policy: DecisionPrecedentPolicy,
    *,
    actor_id: str,
    risk_class: str,
    evaluated_utc: datetime | None = None,
    record_id: str | None = None,
) -> DecisionConfidenceScore:
    """Score candidates deterministically; risk and absence always override similarity."""
    actor_id = _require_identifier(actor_id, "actor_id")
    risk_class = _require_identifier(risk_class, "risk_class")
    now = evaluated_utc or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("decision confidence evaluated_utc must include a timezone")
    matches = _ordered_matches(candidates, policy, evaluated_utc=now)
    best = matches[0] if matches else None
    similarity_score = best.similarity if best else 0.0
    recency_penalty = policy.stale_penalty if best and best.recency_band == "stale" else 0.0
    missing_penalty = policy.missing_precedent_penalty if best is None else 0.0
    final_score = round(max(0.0, similarity_score - recency_penalty - missing_penalty), 6)
    rationale: list[str] = []
    if risk_class in policy.high_risk_classes:
        tier: DecisionTier = "mandatory_escalation"
        rationale.append("high_risk_class")
    elif best is None:
        tier = "mandatory_escalation"
        rationale.append("missing_precedent")
    elif final_score >= policy.suggest_threshold and risk_class not in policy.confirmation_risk_classes:
        tier = "suggest_only"
        rationale.append("high_confidence_precedent")
    elif final_score >= policy.confirmation_threshold:
        tier = "require_confirmation"
        rationale.append("confirmation_threshold")
    else:
        tier = "mandatory_escalation"
        rationale.append("insufficient_confidence")
    if best and best.recency_band == "stale":
        rationale.append("stale_precedent")
    if risk_class in policy.confirmation_risk_classes and tier == "require_confirmation":
        rationale.append("confirmation_risk_class")
    return DecisionConfidenceScore(
        record_id=record_id or str(uuid.uuid4()),
        organization_id=policy.organization_id,
        site_id=policy.site_id,
        actor_id=actor_id,
        policy_version=policy.policy_version,
        risk_class=risk_class,
        similarity_score=similarity_score,
        recency_penalty=recency_penalty,
        missing_precedent_penalty=missing_penalty,
        final_score=final_score,
        tier=tier,
        rationale_codes=tuple(rationale),
        precedent_matches=matches,
    )