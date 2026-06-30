---
title: "Slice 19 — Execution Telemetry and Trace Export"
slice: 19
pack: model-packs/coding-agent/pack.yaml
status: planned
version: 0.1.0
last_updated: 2026-06-30
sha256: pending
---

Summary
-------

This slice adds deterministic, in-pack telemetry for orchestration runs enabling reliable debugging and basic audit traces without introducing external telemetry sinks.

Key points
- Adds `OrchestrationTelemetryEvent` and `OrchestrationTurnSummary` contracts.
- Emits start/per-slice/halt telemetry events from the orchestration loop.
- Includes telemetry summary in orchestration dispatch results under `dispatch_result.telemetry`.
- Adds deterministic tests and docs; updates `docs/MANIFEST.yaml`.

Notes
- This slice intentionally avoids integrating external sinks; it provides an export contract that downstream tooling can consume.
