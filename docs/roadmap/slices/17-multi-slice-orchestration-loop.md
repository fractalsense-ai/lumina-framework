---
title: "Slice 17 — Multi-Slice Orchestration Loop"
slice: 17
pack: model-packs/coding-agent/pack.yaml
status: delivered
version: 0.1.0
last_updated: 2026-06-30
---

Summary
-------

This slice introduces a deterministic multi-slice orchestration loop for Tier-3 execution. It executes ready slices in stable topological order, enforces per-turn budgets, and halts safely on retry scheduling or permanent failures.

Key points
- Adds `TurnBudget` for token/time/slice limits per turn.
- Adds `OrchestrationResult` contract for structured loop outcomes.
- Adds loop controller `execute_dag_until(...)` with deterministic ordering and halt semantics.
- Integrates runtime path to restore persisted execution context, orchestrate multiple slices, and persist checkpoints after each executed slice.

Boundary compliance
- The orchestration loop schedules scoped `TaskSlice` execution only; it does not create user ingress or authorize new work.
- `OrchestrationResult` is execution evidence returned for review, not activation or registration approval.
- Tests may call orchestration helpers directly as validation seams while runtime ingress remains System Pack mediated.

Notes
- After adding or editing this file run `scripts/manifest-regenerate.ps1` to update `docs/MANIFEST.yaml`.
