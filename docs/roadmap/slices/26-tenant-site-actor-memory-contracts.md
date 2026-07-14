---
title: "Slice 26 — Tenant/Site/Actor Memory Contracts"
slice: 26
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Introduce explicit identity and scoping contracts for institutional memory so retrieval and precedent logic are safely partitioned by organization, site, actor, and operational context.

## Scope

- Define new schema contracts for organizational scope:
  - `organization_id`,
  - `site_id`,
  - `actor_id`,
  - `device_id` (optional),
  - external system record references.
- Define memory record contract families:
  - institutional memory record,
  - decision precedent record,
  - thread summary record,
  - business-system event mirror record.
- Specify how these contracts align with existing profile/session/log persistence abstractions.

## Out of Scope

- Database migration implementation.
- Runtime retrieval changes.
- Connector implementation.

## Required Changes

- Add standards-level schema drafts for scoped memory records.
- Add concept documentation describing identity propagation through session, profile, retrieval, and escalation surfaces.

## New/Changed Contracts

- New memory scoping contract: all institutional memory artifacts must be filterable by organization and site.
- New actor linkage contract: memory artifacts should optionally link to actor and device sources.
- New external-system reference contract: memory records may carry `connector_instance_id`, `provider`, `external_record_type`, and `external_record_id` without embedding credentials.

## Files Likely Touched

- `standards/retrieval-index-schema-v1.json`
- `standards/*.json` (new memory record schemas)
- `docs/7-concepts/*.md` (new institutional-memory concept note)
- `docs/roadmap/slices/26-tenant-site-actor-memory-contracts.md`

## Acceptance Criteria

- Contracts support strict organization/site scoping for retrieval.
- Contracts are compatible with local-first storage and deterministic replay tests.
- Contracts prohibit credential-bearing fields.
- Contracts avoid provider-specific canonical field requirements (provider specifics only in optional namespaced metadata).
- Contracts do not require raw transcript persistence for institutional memory continuity.

## Tests

- Schema validation tests for all new contracts.
- Deterministic fixture tests proving scope filters prevent cross-tenant retrieval.

## Ledger/Governance Impact

- Enables ledger-linked institutional evidence envelopes with explicit actor/site provenance.
- No change to existing authority gates; this slice only defines data contracts.

## Follow-Up Slices

- Slice 27: institutional vector memory indexing and retrieval policy.
- Slice 29: confidence and escalation rules consume these contracts.
