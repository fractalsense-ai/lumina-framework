---
title: "Slice 11 — Three-tier Execution Interface"
version: 0.5.0
last_updated: 2026-06-28
date: 2026-06-28
---

Summary
-------

Slice 11 formalizes the three-tier execution contracts between the Architect (Tier 1), Decomposer (Tier 2), and Builder (Tier 3).

Goals
-----

- Define `TaskSlice` and `PlanDAG` contracts used to route and constrain execution.
- Implement a Tier-3 dispatcher that executes safe, policy-gated tool adapters.
- Wire the dispatcher into the domain runtime adapter so evidence-bearing ticks may be executed deterministically.

Progress
--------

- Added `domain-lib/tier_contracts.py` with `PlanDAG`, `PlanNode`, and `TaskSlice` dataclasses.
- Implemented `controllers/tier_dispatcher.py` — Tier-3 path only; calls existing adapters and emits `SequentialThinkingTrace`.
- Wired `runtime_adapters.domain_step()` to dispatch when `evidence.task_slice` is present.

Next
----

- Expand Tier-2 decomposition helpers and DAG planning primitives.
- Add comprehensive tests for tier routing and policy interactions.
- Bump pack version and publish Slice 11 changelog entry.
