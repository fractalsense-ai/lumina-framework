---
title: "Slice 16 — Execution State Persistence & Checkpoint Recovery"
slice: 16
pack: model-packs/coding-agent/pack.yaml
status: planned
version: 0.1.0
last_updated: 2026-06-30
sha256: pending
---

Summary
-------

This slice implements persistent execution-state checkpoints for the coding-agent pack so Tier-3 execution progress, retry counters, and failure context survive across turns. It enables deterministic resume, bounded retention of checkpoints, and a compatibility bridge for callers that do not provide persisted state.

Key points
- Persistence lives in-pack (in-state serialized) to avoid external dependencies.
- Checkpoints include plan id, checkpoint id, timestamp, source, and serialized `ExecutionContext`.
- Retention default: keep last 10 checkpoints per plan.
- Runtime restores latest checkpoint before Tier-3 dispatch and saves updated checkpoint after dispatch.

Notes
- After adding or editing this file run `scripts/manifest-regenerate.ps1` to update `docs/MANIFEST.yaml`.
