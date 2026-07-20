"""Scope-safe institutional retrieval bridge for decision precedent evaluation."""
from __future__ import annotations

from datetime import UTC, datetime

from lumina.decision_precedent.policy import DecisionPrecedentPolicy
from lumina.decision_precedent.scorer import DecisionConfidenceScore, PrecedentCandidate, score_decision_precedent
from lumina.retrieval.contracts import RetrievalFilter
from lumina.retrieval.institutional import InstitutionalMemoryIndexer


def _confidence_from_cosine(score: float) -> float:
    """Map cosine similarity from $[-1, 1]$ to confidence $[0, 1]$."""
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _parse_created_utc(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _precedent_candidates(results: object) -> list[PrecedentCandidate]:
    """Keep only timestamped ThreadSummaryRecords and deduplicate by record ID."""
    candidates: dict[str, PrecedentCandidate] = {}
    for result in results:
        chunk = result.chunk
        if chunk.record_type != "ThreadSummaryRecord":
            continue
        created_utc = _parse_created_utc(chunk.created_utc)
        if not chunk.thread_id or not chunk.record_id or created_utc is None:
            continue
        candidate = PrecedentCandidate(
            summary_record_id=chunk.record_id,
            thread_id=chunk.thread_id,
            similarity=_confidence_from_cosine(result.score),
            created_utc=created_utc,
        )
        current = candidates.get(candidate.summary_record_id)
        if current is None or candidate.similarity > current.similarity:
            candidates[candidate.summary_record_id] = candidate
    return list(candidates.values())


def evaluate_decision_precedent(
    query: str,
    *,
    indexer: InstitutionalMemoryIndexer,
    policy: DecisionPrecedentPolicy,
    actor_id: str,
    risk_class: str,
    evaluated_utc: datetime | None = None,
    record_id: str | None = None,
) -> DecisionConfidenceScore:
    """Return deterministic confidence from same-site summaries without retaining query text."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("decision precedent evaluation requires a non-empty query")
    results = indexer.search(
        query,
        RetrievalFilter(
            organization_id=policy.organization_id,
            site_id=policy.site_id,
            institutional_only=True,
        ),
        k=policy.candidate_limit,
    )
    return score_decision_precedent(
        _precedent_candidates(results),
        policy,
        actor_id=actor_id,
        risk_class=risk_class,
        evaluated_utc=evaluated_utc or datetime.now(UTC),
        record_id=record_id,
    )