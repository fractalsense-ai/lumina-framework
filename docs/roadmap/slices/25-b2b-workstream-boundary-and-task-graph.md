---
title: "Slice 25 — B2B Workstream Boundary and Global Task Graph"
slice: 25
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Define the implementation boundary for the `b2b-institutional-memory-business-systems-architecture` workstream so an external business system remains the transactional source of record and Lumina remains the semantic memory, decision precedent, escalation, and bounded automation layer.

## Scope

- Formalize the global task graph and phase order for the B2B workstream.
- Record explicit system boundaries: external system state ownership, Lumina memory ownership, and governance constraints.
- Define non-negotiable constraints for credentials, transcript handling, and deterministic test posture.

## Out of Scope

- New runtime code, APIs, adapters, migrations, or UI changes.
- Live external-system connectivity.
- New model-pack extraction from the repository.

## Required Changes

- New slice specification documenting the full workstream graph and implementation sequence.
- Add this slice to the roadmap index with `Planned` status.

## New/Changed Contracts

- New roadmap contract: `b2b-institutional-memory-business-systems-architecture` global task graph.
- Architectural boundary contract:
  - External business systems own transactional system-of-record objects.
  - Lumina owns semantic retrieval, precedent evaluation, confidence scoring, and escalation packets.
- Connector routing contract:
  - One primary connector may be configured per site.
  - Multiple active connectors may be configured and selected by capability.
- Security contract:
  - No credentials in prompts, telemetry payloads, checkpoints, or generated artifacts.
  - No raw transcript persistence as required institutional-memory substrate.

## Files Likely Touched

- `docs/roadmap/README.md`
- `docs/roadmap/slices/25-b2b-workstream-boundary-and-task-graph.md`

## Acceptance Criteria

- Workstream scope explicitly separates source-of-record duties from semantic/reasoning duties.
- Slice sequence is explicit and dependency-ordered.
- Provider neutrality is explicit: no provider-specific doctypes/fields in canonical workflow contracts.
- Constraints match framework posture:
  - local-first deployment,
  - API-first business-system integration,
  - deterministic tests before live integration,
  - bounded authority gates preserved.

## Tests

- Documentation consistency check:
  - roadmap index includes Slice 25.
  - section headings match roadmap convention.

## Ledger/Governance Impact

- No runtime ledger behavior change.
- Planning-only governance clarification to prevent accidental authority expansion into the business domain.

## Follow-Up Slices

- Slice 26: tenant/site/actor-scoped memory contracts.
- Slice 27: institutional vector memory layer.
- Slice 28: semantic thread routing and forking.
