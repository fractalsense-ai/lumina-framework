---
title: "Slice 15 — Tier-3 Execution Gating and Retry Policy"
pack: model-packs/coding-agent/pack.yaml
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

## Acceptance Criteria

- Slices with unresolved dependencies are blocked when plan context is provided.
- Recoverable failures produce retry scheduling metadata and backoff seconds.
- Non-recoverable or exhausted-retry failures return deterministic failure outcomes.
- Dispatcher returns structured Tier-3 evidence for all key execution outcomes.
- Tests cover execution context, readiness gating, retry policy, and dispatcher behavior.
- This document is tracked in `docs/MANIFEST.yaml` via `scripts/manifest-regenerate.ps1`.
