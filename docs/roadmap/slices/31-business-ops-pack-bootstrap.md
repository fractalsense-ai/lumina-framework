---
title: "Slice 31 — Business Ops Pack Bootstrap"
slice: 31
status: planned
version: 0.1.0
last_updated: 2026-07-11
---

## Purpose

Bootstrap a reusable business-operations model pack (from template patterns) that binds actor model, scoped institutional memory, ERP adapter calls, and bounded governance behavior.

## Scope

- Define business-ops pack skeleton (manifest, runtime config, domain physics, profiles, role map).
- Define actor types and groups suitable for SMB operations contexts.
- Define initial operation categories and bounded standing orders.
- Define module extension posture for verticals (auto repair first, others later).

## Out of Scope

- Full multi-vertical implementation.
- Production UI polish.
- Billing/commercial packaging logic.

## Required Changes

- Create business-ops pack slice spec aligned with template pack anatomy.
- Define module-map strategy and role/permission model.
- Define domain profile extension fields required by institutional memory and ERP references.

## New/Changed Contracts

- New `business-ops` domain-pack contract (pack identity + module boundaries).
- New role and actor contracts for owner/manager/operator/front-desk/customer-intake contexts.
- New profile extension contract including organization/site defaults and memory policy flags.

## Files Likely Touched

- `model-packs/template/pack.yaml`
- `model-packs/template/cfg/runtime-config.yaml`
- `model-packs/template/cfg/domain-profile-extension.yaml`
- `docs/7-concepts/domain-pack-anatomy.md`
- `docs/roadmap/slices/31-business-ops-pack-bootstrap.md`

## Acceptance Criteria

- Pack scaffold follows HMVC and runtime adapter contract patterns already used in framework.
- Actor, role, and profile contracts align with scoped memory and ERP adapter requirements.
- Governance boundaries stay consistent with System Pack authority model.

## Tests

- Structural pack tests (manifest/runtime-config/domain-physics shape).
- Role/permission contract tests.
- Profile merge tests for base/domain/role composition.

## Ledger/Governance Impact

- Introduces business-domain governance semantics without changing system authority ownership.
- Ensures all bounded operations remain traceable through existing audit model.

## Follow-Up Slices

- Slice 32: first vertical module (auto repair) and deployment/test readiness.
