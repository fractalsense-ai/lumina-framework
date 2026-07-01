---
title: "Slice 18 — Orchestration Hardening and Determinism"
slice: 18
pack: model-packs/coding-agent/pack.yaml
status: planned
version: 0.1.0
last_updated: 2026-06-30
sha256: pending
---

Summary
-------

This slice hardens the Slice 17 orchestration path by making budget behavior deterministic, surfacing persistence failures explicitly, and preserving backward-compatible halt semantics for callers.

Key points
- Makes token budget checks slice-aware before dispatch using `TaskSlice.context_budget_tokens`.
- Differentiates budget halt reasons (`slice_limit_reached`, `token_budget_exhausted`, `time_budget_exhausted`) and preserves compatibility via `halt_reason_compat`.
- Consolidates halt resolution into one deterministic decision path.
- Expands orchestration `evidence_timeline` entries to include full Tier-3 evidence payload.
- Hardens runtime orchestration to return explicit failures when execution-state infrastructure is unavailable.
- Adds regression tests for budget preflight, token accounting fallback, time-budget halts, evidence completeness, and invalid state-store handling.

Boundary compliance
- Hardening improves deterministic evidence and failure reporting inside scoped Coding Agent execution.
- Persistence and halt failures are surfaced as reviewable results; they do not grant activation, registration, deployment, or credential authority.
- Approval, evidence harvest, and teardown remain future System Pack-governed lifecycle work.

Notes
- After adding or editing this file run `scripts/manifest-regenerate.ps1` to update `docs/MANIFEST.yaml`.
