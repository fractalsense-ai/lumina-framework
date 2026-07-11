---
title: "Slice 12 — Tier-2 Decomposer & DAG Planner"
version: 0.6.0
status: delivered
last_updated: 2026-06-29
---

Purpose
-------

Build a deterministic Tier-2 decomposer that converts an approved `CodingAgentJob` into a `PlanDAG` of `PlanNode`s, assigns `TaskSlice`s, and exposes a topological ordering suitable for Tier-3 execution.

Scope
-----

- Implement `domain-lib/tier2_decomposer.py` with `decompose_job`, `topological_sort`, and `assign_task_slices`.
- Implement `domain-lib/dag_validator.py` for pure validation of DAGs.
- Add `controllers` wiring to expose a Tier-2 dispatch path.

Out of Scope
------------

- LLM-based Tier-1 architect planning
- Persistent storage or external orchestration

Required Changes
----------------

- New: `model-packs/coding-agent/domain-lib/tier2_decomposer.py`
- New: `model-packs/coding-agent/domain-lib/dag_validator.py`
- Update: `model-packs/coding-agent/controllers/tier_dispatcher.py` (add `dispatch_to_tier_2`)
- Update: `model-packs/coding-agent/controllers/runtime_adapters.py` (call `dispatch_to_tier_2` when evidence contains a `job` and `execution_tier==2`)
- Tests: `tests/test_coding_agent_tier2_decomposer.py`

Acceptance Criteria
-------------------

- `decompose_job()` produces a valid `PlanDAG` for both explicit `task_graph` and fallback single-node jobs.
- `topological_sort()` orders nodes correctly and raises on cycles.
- `assign_task_slices()` respects global allowed adapter list.
- Unit tests added and passing locally.

Tests
-----

See the test plan in repository tests.

Follow-Up Slices
----------------

- Slice 13: Tier-1 Architect (LLM-driven planner)
- Slice 14: Execution orchestration and retry policies
