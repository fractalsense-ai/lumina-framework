---
title: "Slice 29 — Decision Precedent, Confidence, and Escalation"
slice: 29
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Codify institutional decision precedent retrieval and confidence scoring so Lumina can propose proxy decisions when safe and escalate high-liability or low-confidence cases to human authority.

## Scope

- Define confidence model inputs:
  - precedent similarity,
  - scope match,
  - recency,
  - risk class.
- Define action policy tiers:
  - suggest-only,
  - require confirmation,
  - mandatory escalation.
- Define escalation packet shape for owner/manager approvals.

## Out of Scope

- Push-notification transport implementation.
- Final mobile UX.
- Automated execution of high-liability physical operations.

## Required Changes

- Add precedent evaluation policy spec and confidence rubric.
- Add escalation contract spec aligned with existing system escalation records.
- Add deterministic fixtures demonstrating safe/unsafe recommendation boundaries.

## New/Changed Contracts

- New `precedent_match` contract with provenance and confidence evidence.
- New `decision_confidence_score` contract with transparent component fields.
- New `business_escalation_packet` contract for targeted approval requests.

## Files Likely Touched

- `standards/escalation-record-schema-v1.json`
- `standards/domain-evidence-schema-v1.json`
- `src/lumina/orchestrator/actor_resolver.py`
- `src/lumina/api/pipeline/response.py`
- `tests/test_*escalation*` (new)
- `docs/roadmap/slices/29-decision-precedent-confidence-and-escalation.md`

## Acceptance Criteria

- Confidence score is deterministic for fixed fixture inputs.
- Policy tiers are enforceable without model-side hidden behavior.
- High-risk decisions always escalate.
- Decision rationale is audit-visible and replayable.

## Tests

- Deterministic score calculation tests.
- Policy threshold tests (`suggest`, `confirm`, `escalate`).
- Regression tests for existing standing-order escalation paths.

## Ledger/Governance Impact

- Adds formal precedent-evidence and confidence traces to governance packets.
- Preserves System Pack authority boundaries; recommendations do not equal activation.

## Follow-Up Slices

- Slice 30: canonical business-system contracts and capability taxonomy.
- Slice 31: connector registry and capability routing.
