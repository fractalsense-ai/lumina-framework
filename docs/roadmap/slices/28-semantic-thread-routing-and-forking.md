---
title: "Slice 28 — Semantic Thread Routing and Context Forking"
slice: 28
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Replace timestamp-only session creation defaults with semantic routing that can attach new turns to relevant active threads, create new threads when unmatched, and fork context on topic drift.

## Scope

- Define thread-matching policy using scoped vector retrieval + confidence thresholds.
- Define fork/merge rules and operator intercept prompts.
- Define rolling recap contract for long-running thread compression into summary state.
- Define compatibility behavior with existing transcript seals and session resume paths.

## Out of Scope

- Full UI redesign.
- Auto-merge behavior without operator visibility.
- Persistence backend replacement.

## Required Changes

- Add router policy documentation and data contract for thread candidates.
- Add client/server interface spec for attach/new/fork decisions.
- Add deterministic test matrix for routing outcomes.

## New/Changed Contracts

- New `thread_routing_decision` contract:
  - `attach_existing`,
  - `create_new`,
  - `fork_from`.
- New `thread_summary_state` contract for recap-based continuity.
- New confidence threshold policy contract with explicit override behavior.

## Files Likely Touched

- `src/web/app.tsx`
- `src/web/services/transcriptStore.ts`
- `src/lumina/api/processing.py`
- `src/lumina/api/pipeline/payload.py`
- `tests/*thread*` (new)
- `docs/roadmap/slices/28-semantic-thread-routing-and-forking.md`

## Acceptance Criteria

- New user turn can be routed to existing relevant thread when confidence is high and scope matches.
- Topic drift can produce deterministic fork behavior with explicit rationale.
- Operator can override routing decision.
- Raw transcript retention remains optional and not required for thread continuity.

## Tests

- Deterministic routing tests with fixed embeddings/fixtures.
- Regression tests for existing session create/resume behavior.
- Fork/merge policy tests across same-site and cross-site boundaries.

## Ledger/Governance Impact

- Routing decisions become auditable evidence artifacts (including confidence and rationale).
- No direct privilege changes.

## Follow-Up Slices

- Slice 29: precedent confidence and escalation consumes routed thread context.
