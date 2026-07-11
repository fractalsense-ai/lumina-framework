---
title: "Slice 30 — ERPNext Adapter Foundation and Deterministic Fixtures"
slice: 30
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Define API-first ERPNext integration contracts and deterministic fake-fixture execution so business workflows can be developed and validated before live ERP connectivity.

## Scope

- Define ERP adapter abstraction surface for read/write operations.
- Define allowlisted operation catalog for initial business workflows.
- Define fixture-driven simulation mode for deterministic CI and local development.
- Define credential-handling boundaries external to prompt payloads.

## Out of Scope

- Live ERPNext deployment provisioning.
- Browser automation as primary integration path.
- Production secret management implementation details.

## Required Changes

- Add ERP adapter interface and operation schemas.
- Add fixture framework and deterministic replay cases.
- Add docs for API-first policy and headless-browser fallback policy.

## New/Changed Contracts

- New `erpnext_adapter` contract with operation signatures and response envelopes.
- New `erpnext_fixture_scenario` contract for test replay.
- New security contract: credentials are provided only via runtime environment/secrets layer, never model prompts.

## Files Likely Touched

- `model-packs/template/modules/*/tool-adapters/*.yaml`
- `model-packs/*/controllers/tool_adapters.py` (new ERP adapter family)
- `tests/test_*erpnext*` (new)
- `docs/roadmap/slices/30-erpnext-adapter-foundation-and-fixtures.md`

## Acceptance Criteria

- All ERP operations used by downstream slices run against fake fixtures deterministically.
- Adapter requests/responses are schema-validated.
- No credentials appear in prompt contracts, telemetry payloads, or test artifacts.
- Headless/browser automation remains explicitly secondary fallback.

## Tests

- Fixture replay tests for read and draft-write operations.
- Contract tests for adapter request/response schemas.
- Negative tests for unauthorized operations and malformed payloads.

## Ledger/Governance Impact

- ERP mutation intents become evidence-bearing operations with deterministic audit shape.
- Final authority to commit high-impact changes remains under governance gates.

## Follow-Up Slices

- Slice 31: business ops pack consumes ERP adapter contracts.
- Slice 32: auto-repair MVP executes end-to-end fixture scenarios.
