---
title: "Slice 32 — Auto Repair MVP and Single-Box Deployment Topology"
slice: 32
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Define the first vertical implementation (independent auto repair) and the local-first single-box deployment model that combines ERPNext + Lumina institutional memory + bounded agentic tooling.

## Scope

- Define auto-repair MVP module workflows:
  - intake to structured repair order draft,
  - precedent-assisted technician support,
  - bounded escalation to owner/manager approval,
  - ERP draft updates through adapters.
- Define single-box deployment topology and multi-site thin-client extension pattern.
- Define deterministic end-to-end scenario fixtures spanning memory, precedent, and ERP adapter layers.

## Out of Scope

- General availability hardening for all verticals.
- Full POS and restaurant implementation.
- Production remote notification transport implementation.

## Required Changes

- Add auto-repair module slice spec with actor flows and operation boundaries.
- Add deployment architecture note for local server + VPN-based multi-site access.
- Add deterministic E2E fixture plan with fake ERPNext responses.

## New/Changed Contracts

- New auto-repair module contract for task/event shapes.
- New deployment contract for local-first runtime assumptions:
  - ERP and Lumina colocated,
  - secure LAN/VLAN boundary,
  - optional VPN for remote/site-2 access.
- New E2E fixture contract linking thread routing, precedent scoring, and ERP operation replay.

## Files Likely Touched

- `model-packs/*/modules/*/domain-physics.json` (new auto-repair module)
- `docs/7-concepts/*.md` (new deployment architecture concept)
- `tests/test_*business_ops*` (new)
- `tests/test_*erpnext*` (expanded)
- `docs/roadmap/slices/32-auto-repair-mvp-and-single-box-deployment.md`

## Acceptance Criteria

- End-to-end deterministic scenario runs with fake ERP fixtures:
  - complaint -> structured draft repair order,
  - precedent retrieval -> confidence-scored recommendation,
  - high-risk case -> escalation packet,
  - approval -> bounded ERP draft mutation.
- Deployment topology documented for one-site and thin-client multi-site cases.
- No prompts require credentials; no raw transcript persistence required for institutional continuity.

## Tests

- Deterministic integration tests with fixture replay only.
- Contract tests for escalation packets and decision traces.
- Retrieval isolation tests across organization/site boundaries.

## Ledger/Governance Impact

- Adds full vertical evidence chain from intake to approval and ERP draft update.
- Maintains authority boundaries: recommendations and staging remain separate from final governance approvals.

## Follow-Up Slices

- Operational hardening slices (performance, backup/restore, disaster recovery).
- Additional vertical module slices (restaurant/POS, light manufacturing, service ops).
