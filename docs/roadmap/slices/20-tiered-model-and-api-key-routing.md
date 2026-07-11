---
title: "Slice 20 — Tiered Model and API Key Routing"
slice: 20
pack: model-packs/coding-agent/pack.yaml
status: delivered
version: 0.1.0
last_updated: 2026-06-30
---

Summary
-------

Implement per-tier provider selection and API-key routing for tier-3 execution, with a fail-closed policy when cloud providers are disabled or credentials are missing.

Key points
- Add a `provider_routing` domain module to resolve provider and API-key env var names per-slice.
- Enforce local policy via `LUMINA_ALLOW_CLOUD` and pre-flight check for required API-key env vars.
- Surface selected provider metadata on dispatch results under `dispatch_result.provider`.
- Add unit tests for routing and policy enforcement; document the slice and regenerate `docs/MANIFEST.yaml`.

Boundary compliance
- Provider routing uses environment-variable indirection for key names and does not persist raw secrets in state.
- Offline/local provider routing remains the default fallback to preserve safe test and local execution.
- Cloud/provider selection does not grant activation, registration, deployment, or System Pack authority.

Notes
- This slice is intentionally conservative: when cloud providers are disabled or a required API key is missing, execution fails closed rather than attempting a network call.
- Future slices may add per-pack deny lists and provider-specific configuration.
