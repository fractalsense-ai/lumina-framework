"""Scope-safe institutional retrieval bridge for thread-routing preflight."""
from __future__ import annotations

from dataclasses import dataclass

from lumina.retrieval.contracts import RetrievalFilter
from lumina.retrieval.institutional import InstitutionalMemoryIndexer
from lumina.thread_routing.policy import ThreadRoutingPolicy
from lumina.thread_routing.router import (
    ThreadCandidate,
    ThreadRoutingDecision,
    decide_thread_route,
)


@dataclass(frozen=True)
class ThreadRoutingPreflight:
    """Decision plus the scoped retrieval hits used to make it."""

    decision: ThreadRoutingDecision
    candidates: tuple[ThreadCandidate, ...]


def _confidence_from_cosine(score: float) -> float:
    """Map cosine similarity from $[-1, 1]$ to routing confidence $[0, 1]$."""
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _thread_candidates(results: object) -> list[ThreadCandidate]:
    """Collapse multiple summary hits to each thread's strongest candidate."""
    strongest: dict[str, ThreadCandidate] = {}
    for result in results:
        chunk = result.chunk
        if not chunk.thread_id or not chunk.record_id:
            continue
        candidate = ThreadCandidate(
            thread_id=chunk.thread_id,
            summary_record_id=chunk.record_id,
            score=_confidence_from_cosine(result.score),
        )
        current = strongest.get(candidate.thread_id)
        if current is None or (candidate.score, candidate.summary_record_id) > (
            current.score,
            current.summary_record_id,
        ):
            strongest[candidate.thread_id] = candidate
    return list(strongest.values())


def preflight_thread_route(
    query: str,
    *,
    indexer: InstitutionalMemoryIndexer,
    policy: ThreadRoutingPolicy,
    actor_id: str,
    active_thread_id: str | None = None,
) -> ThreadRoutingPreflight:
    """Retrieve same-site summaries and select an auditable thread route.

    Incoming text is used only to compute an in-memory query embedding; returned
    evidence contains summary record IDs and scores, never the query text.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("thread routing preflight requires a non-empty query")
    results = indexer.search(
        query,
        RetrievalFilter(
            organization_id=policy.organization_id,
            site_id=policy.site_id,
            institutional_only=True,
        ),
        k=policy.candidate_limit,
    )
    candidates = _thread_candidates(results)
    decision = decide_thread_route(
        candidates,
        policy,
        actor_id=actor_id,
        active_thread_id=active_thread_id,
    )
    return ThreadRoutingPreflight(decision=decision, candidates=decision.candidates)