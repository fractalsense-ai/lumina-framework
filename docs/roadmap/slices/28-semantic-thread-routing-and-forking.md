---
title: "Slice 28 — Semantic Thread Routing and Context Forking"
slice: 28
status: delivered
version: 1.0.0
last_updated: 2026-07-20
---

## Purpose

Replace timestamp-only session creation defaults with semantic routing that can attach new turns to relevant active threads, create new threads when unmatched, and fork context on topic drift.

## Scope

- Define thread-matching policy using scoped vector retrieval + confidence thresholds.
- Bootstrap the Business Ops policy surface with pack-level routing defaults and
  organization/site overrides; the System Pack enforces the resolved policy.
- Define fork/merge rules and operator intercept prompts.
- Define rolling recap contract for long-running thread compression into summary state.
- Define compatibility behavior with existing transcript seals and session resume paths.

## Out of Scope

- Full UI redesign.
- Auto-merge behavior without operator visibility.
- Persistence backend replacement.

## Required Changes

- Add router policy documentation and data contract for thread candidates.
- Add a policy-only `model-packs/business-ops/cfg/` foundation with a
  versioned `thread_routing_policy`; its precedence is site override,
  organization override, then Business Ops default.
- Add client/server interface spec for attach/new/fork decisions.
- Add deterministic test matrix for routing outcomes.

## New/Changed Contracts

- New `thread_routing_decision` contract:
  - `attach_existing`,
  - `create_new`,
  - `fork_from`.
- New `thread_summary_state` contract for recap-based continuity.
- New `thread_routing_policy` contract with configurable confidence thresholds,
  recap cadence, candidate limits, and explicit operator-intercept behavior.
- The System Pack owns scope enforcement, decision validation, and audit
  evidence; Business Ops owns organization-configurable operating-policy values.

## Files Likely Touched

- `src/web/app.tsx`
- `src/web/services/transcriptStore.ts`
- `src/lumina/api/processing.py`
- `src/lumina/api/pipeline/payload.py`
- `model-packs/business-ops/cfg/runtime-config.yaml` (new policy-only foundation)
- `model-packs/business-ops/cfg/thread-routing-policy.yaml` (new)
- `tests/*thread*` (new)
- `docs/roadmap/slices/28-semantic-thread-routing-and-forking.md`

## Acceptance Criteria

- New user turn can be routed to existing relevant thread when confidence is high and scope matches.
- Topic drift can produce deterministic fork behavior with explicit rationale.
- Operator can override routing decision.
- Organization and site configuration can tune routing thresholds without
  bypassing System Pack scope, audit, or authority controls.
- Raw transcript retention remains optional and not required for thread continuity.

## Tests

- Deterministic routing tests with fixed embeddings/fixtures.
- Policy-resolution tests for default, organization, and site precedence, plus
  invalid or cross-scope configuration rejection.
- Regression tests for existing session create/resume behavior.
- Fork/merge policy tests across same-site and cross-site boundaries.

## Ledger/Governance Impact

- Routing decisions become auditable evidence artifacts (including confidence and rationale).
- No direct privilege changes.

## Follow-Up Slices

- Slice 29: precedent confidence and escalation consumes routed thread context.
- Slice 32: expands the policy-only Business Ops foundation into the full pack,
  its role model, domain physics, and initial vertical workflows.
