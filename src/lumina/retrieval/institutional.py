"""Local-first ingestion of Slice 26 institutional memory records."""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from lumina.retrieval.embedder import DocChunk, DocEmbedder
from lumina.retrieval.contracts import InstitutionalMemoryStore, RetrievalFilter
from lumina.retrieval.vector_store import SearchResult

_RECORD_SUMMARY_FIELDS = (
    "summary",
    "decision_summary",
    "event_type",
)


def _required_identifier(record: dict[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"institutional record requires {field_name}")
    return value.strip()


def _summary_text(record: dict[str, Any]) -> str:
    for field_name in _RECORD_SUMMARY_FIELDS:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("institutional record requires a summary field")


def _metadata(record: dict[str, Any]) -> dict[str, str | None]:
    reference = record.get("external_system_reference")
    reference = reference if isinstance(reference, dict) else {}
    provider_data = reference.get("provider_data")
    provider_data = provider_data if isinstance(provider_data, dict) else {}
    return {
        "record_id": record.get("record_id"),
        "provider": provider_data.get("provider"),
        "external_record_type": reference.get("external_record_type"),
        "external_record_id": reference.get("external_record_id"),
        "module_key": record.get("module_key"),
    }


def record_to_chunk(record: dict[str, Any]) -> DocChunk:
    """Convert one scoped memory record into a deterministic index chunk."""
    record_type = _required_identifier(record, "record_type")
    record_id = _required_identifier(record, "record_id")
    organization_id = _required_identifier(record, "organization_id")
    site_id = _required_identifier(record, "site_id")
    actor_id = _required_identifier(record, "actor_id")
    summary = _summary_text(record)
    content = json.dumps(
        {
            "organization_id": organization_id,
            "site_id": site_id,
            "record_type": record_type,
            "record_id": record_id,
            "summary": summary,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    metadata = _metadata(record)

    return DocChunk(
        source_path=f"institutional://{record_id}",
        heading=record_type,
        text=summary,
        content_hash=DocChunk.compute_hash(content),
        content_type="institutional_memory",
        domain_id=str(record.get("domain_id") or ""),
        organization_id=organization_id,
        site_id=site_id,
        actor_id=actor_id,
        device_id=record.get("device_id") if isinstance(record.get("device_id"), str) else None,
        record_id=record_id,
        provider=metadata["provider"],
        external_record_type=metadata["external_record_type"],
        external_record_id=metadata["external_record_id"],
        module_key=metadata["module_key"],
    )


class InstitutionalMemoryIndexer:
    """Embed and persist scoped memory records using the current local store."""

    def __init__(self, store: InstitutionalMemoryStore, embedder: DocEmbedder) -> None:
        self._store = store
        self._embedder = embedder

    def ingest(self, records: Iterable[dict[str, Any]]) -> dict[str, int]:
        """Index new records and return deterministic ingestion counts."""
        new_chunks: list[DocChunk] = []
        skipped = 0
        for record in records:
            chunk = record_to_chunk(record)
            if self._store.has_hash(chunk.content_hash):
                skipped += 1
            else:
                new_chunks.append(chunk)

        if new_chunks:
            vectors = self._embedder.embed_chunks(new_chunks)
            self._store.add(new_chunks, vectors)
            self._store.save()

        return {
            "records_seen": skipped + len(new_chunks),
            "records_indexed": len(new_chunks),
            "records_skipped": skipped,
        }

    def search(
        self,
        query: str,
        retrieval_filter: RetrievalFilter,
        *,
        k: int = 5,
    ) -> list[SearchResult]:
        """Search institutional memory with mandatory hard scope filters."""
        retrieval_filter.validate()
        if not retrieval_filter.institutional_only:
            raise ValueError("institutional search requires institutional_only")
        self._store.load()
        if self._store.size == 0:
            return []
        return self._store.search(
            self._embedder.embed_query(query),
            k=k,
            retrieval_filter=retrieval_filter,
        )

    @staticmethod
    def canonical_content(record: dict[str, Any]) -> str:
        """Return the stable content payload used for deterministic inspection."""
        return json.dumps(
            {
                "organization_id": record.get("organization_id"),
                "site_id": record.get("site_id"),
                "record_type": record.get("record_type"),
                "record_id": record.get("record_id"),
                "summary": _summary_text(record),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
