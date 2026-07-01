---
title: "Slice 15 — Tier-3 Execution Gating and Retry Policy"
slice: 15
pack: model-packs/coding-agent/pack.yaml
status: delivered
version: 0.9.0
last_updated: 2026-06-29
sha256: pending
---

Slice 15 enforces runtime-safe execution at Tier 3 by validating readiness
before execution and applying deterministic retry policy for recoverable failures.

## Purpose

Tier 3 should execute only slices that are dependency-ready and within retry budget.
This avoids wasted calls, duplicate execution, and retry storms.

## Scope

- Introduce an execution context contract for completed nodes and retry counters.
- Add a readiness scheduler to validate whether a slice is executable.
- Add deterministic retry classification and bounded exponential backoff.
- Emit Tier-3 execution evidence for success, blocked, retry-scheduled, and failure outcomes.
- Wire dispatcher enforcement for optional plan-aware gating while preserving backward compatibility.

## Out of Scope

- Direct invocation by users, domain packs, template packs, or providers.
- Activation, registration, deployment, or production promotion.
- Persistent checkpoint storage across turns.
- External telemetry sinks, evidence harvest, and teardown lifecycle work.

## Required Changes

- Add readiness scheduling helpers for dependency-aware Tier-3 execution.
- Add retry policy classification and deterministic backoff helpers.
- Add structured Tier-3 execution evidence for success, blocked, retry, and
  permanent failure outcomes.
- Update dispatcher logic to enforce readiness when plan context is supplied.

## New/Changed Contracts

- `ExecutionContext` tracks completed nodes, failed nodes, retry counts, and
  retry bounds.
- `Tier3ExecutionEvidence` records ready status, attempt count, retryability,
  allowed tools, denied tools, and failure metadata.
- Retry policy classifies transient and permanent failures deterministically.

## Files Likely Touched

- `model-packs/coding-agent/domain-lib/tier3_ready_scheduler.py`
- `model-packs/coding-agent/domain-lib/retry_policy.py`
- `model-packs/coding-agent/domain-lib/tier3_evidence.py`
- `model-packs/coding-agent/domain-lib/tier_contracts.py`
- `model-packs/coding-agent/controllers/tier_dispatcher.py`
- `tests/test_coding_agent_tier3_gating_and_retry.py`

## Boundary Compliance

Tier-3 gating constrains execution inside a scoped Coding Agent job. It does
not authorize work, broaden file boundaries, activate artifacts, register
outputs, deploy changes, or access production credentials. Internal dispatcher
tests may call Tier-3 logic directly as validation seams; product/runtime ingress
remains System Pack mediated.

## Acceptance Criteria

- Slices with unresolved dependencies are blocked when plan context is provided.
- Recoverable failures produce retry scheduling metadata and backoff seconds.
- Non-recoverable or exhausted-retry failures return deterministic failure outcomes.
- Dispatcher returns structured Tier-3 evidence for all key execution outcomes.
- Tests cover execution context, readiness gating, retry policy, and dispatcher behavior.
- This document is tracked in `docs/MANIFEST.yaml` via `scripts/manifest-regenerate.ps1`.

## Tests

Run focused Tier-3 gating, retry policy, and dispatcher tests.

## Ledger/Governance Impact

This slice produces execution evidence only. It does not write approval,
registration, activation, evidence harvest, or teardown records. Those remain
System Pack-governed lifecycle responsibilities.

## Follow-Up Slices

- Slice 16: Execution-state persistence.
- Slice 17: Multi-slice orchestration loop.
