---
title: "Slice 36 — Single-Box Deployment and Operational Hardening"
slice: 36
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Define and validate the single-box deployment profile for pilot rollout, including deterministic fallback behavior, observability, and operator runbooks.

## Scope

- Define single-box deployment profile (all core services local on one host) and resource envelope guidance.
- Define connector/runtime operational health checks and startup ordering.
- Define backup/restore and local retention controls for institutional memory artifacts.
- Define operator runbooks for route failures, connector degradation, and escalation backlog handling.

## Out of Scope

- Multi-tenant cloud deployment topology.
- Full HA/disaster-recovery architecture.
- Enterprise SSO and centralized secrets platform integration.

## Required Changes

- Add deployment profile documentation/scripts for single-box setup.
- Add operational diagnostics and smoke checks.
- Add deterministic degraded-mode scenarios.
- Add release-readiness checklist for pilot site rollout.

## New/Changed Contracts

- New deployment profile contract for single-box operation.
- New operational health-report contract for connectors and memory services.
- New pilot-readiness checklist contract.

## Files Likely Touched

- `scripts/**` (single-box bootstrap helpers)
- `docs/8-admin/**`
- `tests/test_*deployment*smoke*`
- `docs/roadmap/slices/36-single-box-deployment-and-operational-hardening.md`

## Acceptance Criteria

- Single-box profile runs without mandatory network dependencies besides optional external business-system endpoints.
- Degraded-mode behaviors are deterministic and auditable.
- Operator runbooks cover the top failure and recovery paths.
- Readiness checklist is complete and executable.

## Tests

- Deployment smoke test for single-box profile.
- Health-check and degraded-mode scenario tests.
- Backup/restore validation tests.

## Ledger/Governance Impact

- Deployment profile enforces local retention posture and explicit approval checkpoints.
- Operational interventions become traceable administrative evidence.

## Follow-Up Slices

- Next roadmap phase: broaden vertical coverage and multi-site operational tooling.
