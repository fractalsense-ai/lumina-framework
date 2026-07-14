---
title: "Slice 30 — Canonical Business-System Contracts and Capability Taxonomy"
slice: 30
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Define provider-neutral JSON Schema contracts and capability taxonomy so Business Ops workflows remain vendor-agnostic and all connector implementations conform to the same canonical operation envelopes.

## Scope

- Define canonical schemas for:
	- external system references,
	- connector manifests,
	- business operation request/result envelopes,
	- business-system events,
	- connector errors,
	- fixture scenarios.
- Define capability taxonomy for the first business-ops surface (`party/customer`, `catalog/item`, `inventory`, `sales/pos`, `purchasing`, `service/work-order`, `scheduling`, `timekeeping`, `accounting/invoice`).
- Define canonical action classes (`query`, `create_draft`, `update_draft`, `request_commit`, `request_cancel`, `sync_event`).

## Out of Scope

- Provider-specific mappings or API clients.
- Runtime connector registry/routing behavior.
- Live external-system connectivity.

## Required Changes

- Add canonical schemas under `standards/` for business-system envelopes and references.
- Add capability taxonomy and conformance notes in docs.
- Add deterministic schema fixture tests for all canonical contracts.

## New/Changed Contracts

- New `external_system_reference` contract.
- New `business_system_connector_manifest` contract.
- New `business_operation_request` and `business_operation_result` contracts.
- New `business_system_event` contract.
- New `connector_error` and `connector_fixture_scenario` contracts.
- Security contract: credentials are referenced via runtime secrets/config only; credentials never appear in prompts, telemetry, fixtures, or institutional memory records.

## Files Likely Touched

- `standards/*.json` (new canonical business-system schemas)
- `tests/test_*schema*` (new)
- `docs/7-concepts/*.md`
- `docs/roadmap/slices/30-erpnext-adapter-foundation-and-fixtures.md`

## Acceptance Criteria

- Canonical schemas are sufficient to express provider-independent workflows without required vendor-specific fields.
- Contract fixtures validate deterministically in CI/local runs.
- Capability taxonomy is explicit and versioned.
- No credential-bearing field exists in canonical schemas.

## Tests

- Schema validation tests for each canonical contract.
- Positive/negative fixtures for each action class and capability namespace.
- Backward-compat checks ensuring no breakage to existing standards tests.

## Ledger/Governance Impact

- Canonical operation envelopes become evidence-bearing governance artifacts regardless of provider.
- Final commit/cancel authority remains governed by system/domain policy gates.

## Follow-Up Slices

- Slice 31: connector registry and capability routing.
- Slice 32: business-ops pack bootstrap against canonical contracts.
