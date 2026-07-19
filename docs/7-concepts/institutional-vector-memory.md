---
version: 1.0.0
last_updated: 2026-07-19
---

# Institutional Vector Memory

Slice 27 adds a local-first institutional-memory retrieval layer over the
existing vector store. It indexes concise institutional records rather than raw
chat transcripts, so operational continuity can survive session boundaries
without making transcript retention a prerequisite.

## Record And Scope Boundary

The indexer accepts the Slice 26 provider-neutral record families:

- institutional memory records;
- decision precedent records;
- thread summary records; and
- business-system event mirror records.

Every indexed record requires `organization_id`, `site_id`, and `actor_id`.
Institutional search requires `organization_id`, `site_id`, and
`institutional_only=true`. The store first excludes nonmatching scope and
non-institutional chunks, then ranks only eligible vectors. Optional actor,
device, module, provider, and external-record filters further narrow the
eligible corpus.

This ordering is a security boundary: similarity ranking must never make an
out-of-scope record eligible for recall.

## Ingestion Lifecycle

1. Validate the scoped record identity and derive its summary text.
2. Convert the record to a `DocChunk` with institutional provenance metadata.
3. Create a deterministic content identity from organization, site, record
   type, record ID, and summary.
4. Skip an already-indexed identity; otherwise embed and persist the new chunk.
5. Reload persisted metadata before retrieval so local process restarts do not
   change recall behavior.

The stable identity permits repeated ingestion of one record while preserving
separate records that happen to have identical summaries in another scope.

## Local Backend Portability

`InstitutionalMemoryIndexer` depends on the `InstitutionalMemoryStore` protocol:
load, save, hash lookup, add, size, and filter-aware search. `VectorStore` is
the initial flat-file implementation (`vectors.npz` plus `metadata.json`). A
future local SQLite or vector engine backend can implement that protocol without
changing record ingestion or retrieval-filter callers.

Slice 27 deliberately does not require an ANN service, a hosted vector
dependency, or a live business-system connector. Backend replacement and
connector lifecycle work remain later slices.

## Deterministic Recall Fixture

`tests/artifacts/institutional-memory-recall-fixture.json` holds a synthetic
brake-procedure query with same-site distractor and cross-site lookalike records.
The focused test verifies that fixed embeddings return the expected local
precedent and never retrieve the cross-site lookalike. This fixture is a
repeatable recall-quality baseline, not a production corpus.

## Governance Posture

Retrieved records are advisory evidence. They retain artifact identity and
scope provenance but do not grant authority, bypass policy gates, or trigger
external mutations. Slice 28 consumes this layer for thread routing; Slice 29
uses it for confidence and escalation decisions.
