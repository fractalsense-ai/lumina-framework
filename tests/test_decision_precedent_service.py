"""Tests for scope-safe Slice 29 institutional precedent retrieval."""
from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from lumina.decision_precedent.policy import DecisionPrecedentPolicy
from lumina.decision_precedent.service import evaluate_decision_precedent
from lumina.retrieval.embedder import EMBEDDING_DIM
from lumina.retrieval.institutional import InstitutionalMemoryIndexer
from lumina.retrieval.vector_store import VectorStore


class _FakeEmbedder:
    def embed_chunks(self, chunks):
        return np.asarray([self.embed_query(chunk.text) for chunk in chunks], dtype=np.float32)

    def embed_query(self, query):
        vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vector[0 if "brake" in query.lower() else 1] = 1.0
        return vector


def _policy() -> DecisionPrecedentPolicy:
    return DecisionPrecedentPolicy(
        policy_version=1, candidate_limit=5, suggest_threshold=0.88, confirmation_threshold=0.70,
        stale_after_days=90, stale_penalty=0.18, missing_precedent_penalty=1.0,
        high_risk_classes=("financial",), confirmation_risk_classes=("operational",),
        organization_id="org-a", site_id="site-a",
    )


def _summary(record_id: str, *, organization_id: str = "org-a", site_id: str = "site-a", created_utc: str = "2026-07-19T12:00:00Z") -> dict:
    return {
        "record_type": "ThreadSummaryRecord", "record_id": record_id,
        "organization_id": organization_id, "site_id": site_id, "actor_id": "actor-a",
        "thread_id": f"thread-{record_id}", "summary": "Brake inspection work order.",
        "created_utc": created_utc,
    }


@pytest.mark.unit
def test_evaluation_uses_only_same_site_timestamped_summaries(tmp_path) -> None:
    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "memory"), _FakeEmbedder())
    indexer.ingest([_summary("same-site"), _summary("other-site", site_id="site-b")])

    score = evaluate_decision_precedent(
        "brake update", indexer=indexer, policy=_policy(), actor_id="actor-a", risk_class="routine",
        evaluated_utc=datetime(2026, 7, 20, tzinfo=UTC), record_id="score-a",
    )

    assert score.tier == "suggest_only"
    assert [match.summary_record_id for match in score.precedent_matches] == ["same-site"]


@pytest.mark.unit
def test_missing_timestamp_is_not_eligible_precedent(tmp_path) -> None:
    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "memory"), _FakeEmbedder())
    record = _summary("untimestamped")
    record.pop("created_utc")
    indexer.ingest([record])

    score = evaluate_decision_precedent(
        "brake update", indexer=indexer, policy=_policy(), actor_id="actor-a", risk_class="routine",
        evaluated_utc=datetime(2026, 7, 20, tzinfo=UTC), record_id="score-a",
    )

    assert score.tier == "mandatory_escalation"
    assert score.precedent_matches == ()


@pytest.mark.unit
def test_persisted_store_retains_summary_timestamp(tmp_path) -> None:
    store = VectorStore(tmp_path / "memory")
    indexer = InstitutionalMemoryIndexer(store, _FakeEmbedder())
    indexer.ingest([_summary("persisted")])
    reloaded = InstitutionalMemoryIndexer(VectorStore(tmp_path / "memory"), _FakeEmbedder())

    score = evaluate_decision_precedent(
        "brake update", indexer=reloaded, policy=_policy(), actor_id="actor-a", risk_class="routine",
        evaluated_utc=datetime(2026, 7, 20, tzinfo=UTC), record_id="score-a",
    )

    assert score.precedent_matches[0].created_utc == datetime(2026, 7, 19, 12, tzinfo=UTC)