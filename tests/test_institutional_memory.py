"""Tests for local-first institutional memory ingestion."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from lumina.retrieval.embedder import EMBEDDING_DIM
from lumina.retrieval.institutional import InstitutionalMemoryIndexer, record_to_chunk
from lumina.retrieval.vector_store import VectorStore
from lumina.thread_routing.policy import ThreadRoutingPolicy
from lumina.thread_routing.service import preflight_thread_route

FIXTURE_PATH = Path(__file__).parent / "artifacts" / "institutional-memory-recall-fixture.json"


class _FakeEmbedder:
    def embed_chunks(self, chunks):
        return np.ones((len(chunks), EMBEDDING_DIM), dtype=np.float32)

    def embed_query(self, query):
        return np.ones(EMBEDDING_DIM, dtype=np.float32)


class _FixtureEmbedder:
    @staticmethod
    def _embed(text: str) -> np.ndarray:
        vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vector[0 if "brake" in text.lower() else 1] = 1.0
        return vector

    def embed_chunks(self, chunks):
        return np.asarray([self._embed(chunk.text) for chunk in chunks], dtype=np.float32)

    def embed_query(self, query):
        return self._embed(query)


def _record(record_id: str = "memory-1") -> dict:
    return {
        "record_type": "ThreadSummaryRecord",
        "record_id": record_id,
        "organization_id": "org-a",
        "site_id": "site-1",
        "actor_id": "actor-1",
        "thread_id": "thread-1",
        "summary": "The maintenance decision was resolved.",
        "status": "resolved",
        "created_utc": "2026-07-16T12:00:00Z",
        "external_system_reference": {
            "connector_instance_id": "connector-1",
            "external_record_type": "work_order",
            "external_record_id": "wo-1",
            "provider_data": {"provider": "erp"},
        },
    }


def _routing_policy() -> ThreadRoutingPolicy:
    return ThreadRoutingPolicy(
        policy_version=1,
        attach_threshold=0.85,
        fork_threshold=0.60,
        ambiguity_margin=0.04,
        recap_interval_turns=10,
        candidate_limit=5,
        manual_only=False,
        require_operator_confirmation_for=("fork_from",),
        organization_id="org-a",
        site_id="site-1",
    )


def test_record_to_chunk_preserves_scope_and_provenance() -> None:
    chunk = record_to_chunk(_record())
    assert chunk.content_type == "institutional_memory"
    assert chunk.organization_id == "org-a"
    assert chunk.site_id == "site-1"
    assert chunk.actor_id == "actor-1"
    assert chunk.record_id == "memory-1"
    assert chunk.thread_id == "thread-1"
    assert chunk.provider == "erp"
    assert chunk.external_record_id == "wo-1"
    assert chunk.content_hash == record_to_chunk(_record()).content_hash


def test_indexer_deduplicates_by_content_hash(tmp_path) -> None:
    store = VectorStore(tmp_path / "vs")
    indexer = InstitutionalMemoryIndexer(store, _FakeEmbedder())

    first = indexer.ingest([_record()])
    second = indexer.ingest([_record()])

    assert first == {"records_seen": 1, "records_indexed": 1, "records_skipped": 0}
    assert second == {"records_seen": 1, "records_indexed": 0, "records_skipped": 1}
    assert store.size == 1


def test_vector_store_round_trip_preserves_institutional_thread_id(tmp_path) -> None:
    store = VectorStore(tmp_path / "vs")
    indexer = InstitutionalMemoryIndexer(store, _FakeEmbedder())
    indexer.ingest([_record()])

    restored = VectorStore(tmp_path / "vs")
    restored.load()

    assert restored._chunks[0].thread_id == "thread-1"


def test_indexer_keeps_distinct_records_with_matching_summaries(tmp_path) -> None:
    store = VectorStore(tmp_path / "vs")
    indexer = InstitutionalMemoryIndexer(store, _FakeEmbedder())
    other_record = _record("memory-2")
    other_record["organization_id"] = "org-b"
    other_record["site_id"] = "site-2"

    result = indexer.ingest([_record(), other_record])

    assert result == {"records_seen": 2, "records_indexed": 2, "records_skipped": 0}
    assert store.size == 2


def test_indexer_accepts_transcript_free_decision_record(tmp_path) -> None:
    record = _record("decision-1")
    record.pop("thread_id")
    record["record_type"] = "DecisionPrecedentRecord"
    record["decision_summary"] = record.pop("summary")
    record["outcome"] = "successful"
    store = VectorStore(tmp_path / "vs")

    result = InstitutionalMemoryIndexer(store, _FakeEmbedder()).ingest([record])

    assert result["records_indexed"] == 1
    assert store._chunks[0].text == "The maintenance decision was resolved."


def test_indexer_search_requires_hard_scope(tmp_path) -> None:
    from lumina.retrieval.contracts import RetrievalFilter

    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "vs"), _FakeEmbedder())
    indexer.ingest([_record()])

    results = indexer.search(
        "maintenance",
        RetrievalFilter(
            organization_id="org-a",
            site_id="site-1",
            institutional_only=True,
        ),
    )

    assert len(results) == 1
    assert results[0].chunk.record_id == "memory-1"

    with pytest.raises(ValueError, match="institutional_only"):
        indexer.search(
            "maintenance",
            RetrievalFilter(organization_id="org-a", site_id="site-1"),
        )


def test_indexer_search_excludes_scoped_non_institutional_chunks(tmp_path) -> None:
    from lumina.retrieval.contracts import RetrievalFilter
    from lumina.retrieval.embedder import DocChunk

    store = VectorStore(tmp_path / "vs")
    store.add(
        [
            DocChunk(
                source_path="domain.md",
                heading="domain",
                text="maintenance decision",
                content_hash=DocChunk.compute_hash("domain"),
                organization_id="org-a",
                site_id="site-1",
            ),
        ],
        np.ones((1, EMBEDDING_DIM), dtype=np.float32),
    )
    indexer = InstitutionalMemoryIndexer(store, _FakeEmbedder())
    indexer.ingest([_record()])

    results = indexer.search(
        "maintenance",
        RetrievalFilter(
            organization_id="org-a",
            site_id="site-1",
            institutional_only=True,
        ),
    )

    assert [result.chunk.content_type for result in results] == ["institutional_memory"]


def test_recall_fixture_returns_only_the_scoped_expected_precedent(tmp_path) -> None:
    from lumina.retrieval.contracts import RetrievalFilter

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "vs"), _FixtureEmbedder())
    indexer.ingest(fixture["records"])

    results = indexer.search(
        fixture["query"],
        RetrievalFilter(**fixture["filter"]),
        k=fixture["k"],
    )

    assert [result.chunk.record_id for result in results] == fixture["expected_record_ids"]


def test_preflight_routes_to_same_site_thread_and_excludes_other_sites(tmp_path) -> None:
    store = VectorStore(tmp_path / "vs")
    indexer = InstitutionalMemoryIndexer(store, _FixtureEmbedder())
    same_site = _record("summary-brake")
    same_site["summary"] = "Brake maintenance work order is open."
    same_site["thread_id"] = "thread-brake"
    other_site = _record("summary-other-site")
    other_site["site_id"] = "site-2"
    other_site["summary"] = "Brake maintenance work order is open."
    other_site["thread_id"] = "thread-other-site"
    indexer.ingest([same_site, other_site])

    preflight = preflight_thread_route(
        "brake inspection update",
        indexer=indexer,
        policy=_routing_policy(),
        actor_id="actor-1",
    )

    assert preflight.decision.decision == "attach_existing"
    assert preflight.decision.thread_id == "thread-brake"
    assert [candidate.thread_id for candidate in preflight.candidates] == ["thread-brake"]


def test_preflight_forks_when_active_thread_has_no_scoped_match(tmp_path) -> None:
    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "vs"), _FixtureEmbedder())

    preflight = preflight_thread_route(
        "unrelated inventory count",
        indexer=indexer,
        policy=_routing_policy(),
        actor_id="actor-1",
        active_thread_id="thread-active",
    )

    assert preflight.decision.decision == "fork_from"
    assert preflight.decision.source_thread_id == "thread-active"


@pytest.mark.parametrize("field", ["organization_id", "site_id", "actor_id"])
def test_record_to_chunk_requires_scope(field: str) -> None:
    record = _record()
    record.pop(field)
    with pytest.raises(ValueError, match=field):
        record_to_chunk(record)


def test_record_to_chunk_requires_summary() -> None:
    record = _record()
    record.pop("summary")
    with pytest.raises(ValueError, match="summary"):
        record_to_chunk(record)
