---
title: "Slice 27 — Institutional Vector Memory Layer"
slice: 27
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Extend the existing retrieval stack into a tenant/site/actor-scoped institutional memory layer that stores and retrieves operational precedent, summaries, and external-system-linked evidence while preserving local-first deployment.

## Scope

- Define indexing and retrieval behavior for institutional memory artifacts.
- Specify incremental ingestion from decision records, summaries, and business-system event mirrors.
- Specify filter and ranking rules combining semantic similarity with strict scope constraints.
- Define rollout path from current flat-file vector stores to pluggable local backends without API contract breakage.

## Out of Scope

- Replacing the current vector backend in this slice.
- Advanced ANN/cluster infrastructure.
- Cloud-hosted vector dependencies.

## Required Changes

- Add retrieval subsystem design docs for scoped institutional indexing.
- Add interface updates for scoped store registry and filter-aware search.
- Add deterministic benchmark fixtures for memory recall quality.

## New/Changed Contracts

- New scoped retrieval contract:
  - hard filters (`organization_id`, `site_id`) before scoring,
  - optional filters (`actor_id`, `module_key`, `provider`, `external_record_type`, `external_record_id`).
- New memory ingestion contract:
  - index summaries and decision/evidence artifacts,
  - raw transcripts optional and not required.
- New store abstraction contract for backend portability (flat-file now, local DB/vector engine later).

## Files Likely Touched

- `src/lumina/retrieval/vector_store.py`
- `src/lumina/retrieval/housekeeper.py`
- `src/lumina/orchestrator/knowledge_retriever.py`
- `src/lumina/core/nlp.py`
- `tests/test_retrieval.py`
- `docs/roadmap/slices/27-institutional-vector-memory-layer.md`

## Acceptance Criteria

- Retrieval can enforce organization/site scope deterministically.
- Institutional-memory search works without requiring transcript replay.
- Existing domain retrieval remains backward compatible.
- All tests run with fake/local fixtures only.

## Tests

- Deterministic retrieval unit tests with synthetic institutional records.
- Scope-isolation tests proving no cross-site leakage.
- Regression tests for current `KnowledgeIndex` and domain retrieval flows.

## Ledger/Governance Impact

- Improves evidence traceability by tying recalled memory items to scoped artifact identities.
- No direct authority changes; retrieval remains advisory until policy gates permit action.

## Follow-Up Slices

- Slice 28: semantic thread routing and fork/merge behavior.
- Slice 29: confidence scoring and escalation policy on retrieved precedent.
