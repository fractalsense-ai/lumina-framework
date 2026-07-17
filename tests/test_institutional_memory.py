"""Tests for local-first institutional memory ingestion."""
from __future__ import annotations

import numpy as np
import pytest

from lumina.retrieval.embedder import EMBEDDING_DIM
from lumina.retrieval.institutional import InstitutionalMemoryIndexer, record_to_chunk
from lumina.retrieval.vector_store import VectorStore


class _FakeEmbedder:
    def embed_chunks(self, chunks):
        return np.ones((len(chunks), EMBEDDING_DIM), dtype=np.float32)

    def embed_query(self, query):
        return np.ones(EMBEDDING_DIM, dtype=np.float32)


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


def test_record_to_chunk_preserves_scope_and_provenance() -> None:
    chunk = record_to_chunk(_record())
    assert chunk.content_type == "institutional_memory"
    assert chunk.organization_id == "org-a"
    assert chunk.site_id == "site-1"
    assert chunk.actor_id == "actor-1"
    assert chunk.record_id == "memory-1"
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
