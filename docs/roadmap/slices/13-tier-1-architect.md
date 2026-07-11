---
title: "Slice 13 — Tier-1 Architect & SLM Routing"
slice: 13
pack: model-packs/coding-agent/pack.yaml
status: delivered
version: 0.8.0
last_updated: 2026-06-29
---

Purpose
-------

Implement the Tier-1 Architect for global planning and model-class assignment.
The architect classifies plan nodes by action type (for example, `document` vs
`code`) and routes documentation-style work toward the local Lumina SLM where
appropriate.

Scope
-----

- Add deterministic Tier-1 planning helpers for global DAG creation.
- Classify plan nodes by action type and derive model class hints.
- Preserve dependency context for later Tier-2 slicing.
- Prefer local SLM routing for lightweight documentation tasks.
- Keep all planning inside the bounded Coding Agent factory contract.

Out of Scope
------------

- Direct user ingress into the Coding Agent.
- Activation, registration, deployment, or production promotion.
- Provider-specific credential handling or live cloud model calls.
- Evidence harvest and teardown lifecycle implementation.

Required Changes
----------------

- Add `model-packs/coding-agent/domain-lib/tier1_architect.py`.
- Update Tier dispatcher wiring so Tier 1 can produce architect plan evidence.
- Add tests for architecture planning, node classification, and model-class map
  construction.

New/Changed Contracts
---------------------

- `ArchitectPlan` captures a global DAG, system-state references, tier
  assignments, and validation errors.
- `PlanNode.action_type` supports model-class classification.
- `build_model_class_map(...)` exposes model-class hints to later slicing.

Files Likely Touched
--------------------

- `model-packs/coding-agent/domain-lib/tier1_architect.py`
- `model-packs/coding-agent/domain-lib/tier_contracts.py`
- `model-packs/coding-agent/controllers/tier_dispatcher.py`
- `tests/test_coding_agent_tier1_architect.py`

Boundary Compliance
-------------------

This slice preserves the Slice 1, 5, and 6 boundary contracts. Tier-1 planning
accepts only scoped job data supplied through the Coding Agent runtime path. It
does not create runtime ingress, hold credentials, activate artifacts, register
outputs, or deploy changes. Internal tests may call Tier-1 helpers directly as
validation seams; those calls are not product/runtime ingress.

Acceptance Criteria
-------------------

- Tier-1 helpers produce deterministic architect plan evidence.
- Documentation-style nodes can be classified for local SLM routing.
- Model-class mapping is stable and consumable by Tier 2.
- Invalid global plans surface validation errors rather than being executed.
- Tests cover planning, classification, and dispatcher integration.

Tests
-----

Run focused Tier-1 tests and related dispatcher tests.

Ledger/Governance Impact
------------------------

This slice adds planning evidence only. Governance approval, registration,
activation, evidence harvest, and teardown remain System Pack-governed future
lifecycle work.

Follow-Up Slices
----------------

- Slice 14: DAG-correct orchestration.
- Slice 15: Tier-3 execution gating and retry policy.

Implementation details and tests live in `model-packs/coding-agent/domain-lib/tier1_architect.py`.
