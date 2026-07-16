---
title: "Slice 35 — Auto Repair MVP Over Connector Abstractions"
slice: 35
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Deliver the first verticalized end-to-end loop (auto repair operations) using canonical business-system operations so workflow behavior is portable across providers.

## Scope

- Define auto-repair workflow scope (intake -> estimate context -> parts/work-order status -> customer update draft -> escalation handoff).
- Bind workflow to institutional memory retrieval and confidence thresholds.
- Bind workflow to routed connector operations constrained by allowlists.
- Add provider-agnostic vertical defaults with provider-specific mapping adapters.

## Out of Scope

- Full accounting automation.
- Autonomous irreversible transactions without approval.
- Multi-vertical completion.

## Required Changes

- Add vertical-specific module contracts and policy defaults.
- Add deterministic scenarios and expected outcomes through canonical envelopes.
- Add escalation and confidence profiles tuned for service operations.
- Add portability checks ensuring workflow package runs with each conformant connector.

## New/Changed Contracts

- New vertical workflow contracts for service intake, estimate context package, and customer communication draft.
- New confidence/escalation threshold profile defaults for auto-repair intents.
- New provider portability checklist contract for workflow readiness.

## Files Likely Touched

- `model-packs/business-ops/**` (new)
- `src/lumina/**` (workflow glue where needed)
- `tests/test_*auto_repair*`
- `docs/roadmap/slices/35-auto-repair-mvp-over-connector-abstractions.md`

## Acceptance Criteria

- Deterministic scenario tests pass for vertical MVP paths.
- Confidence/escalation thresholds are externally configurable and auditable.
- Workflow logic remains canonical and connector-agnostic.
- No credential leakage in logs/prompts/fixtures.

## Tests

- End-to-end fixture tests for intake/status/update/escalation flows.
- Contract tests for vertical workflow packets and escalation record shape.
- Portability tests across at least two conformant connectors.

## Ledger/Governance Impact

- Vertical actions generate structured evidence packets and escalation records.
- Governance gates remain mandatory for high-impact commits/cancels.

## Follow-Up Slices

- Slice 36: single-box deployment and operational hardening.
