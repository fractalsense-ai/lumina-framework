# Coding Agent Pack Changelog

## 0.8.0 — 2026-07-11

- Slices 13-24 implementation reconciliation and closure update.
- Slice 13: Tier-1 architect planning and model-class routing delivered.
- Slice 14: DAG-correct orchestration delivered.
- Slice 15: Tier-3 execution gating and retry policy delivered.
- Slice 16: execution checkpoint persistence and deterministic resume delivered.
- Slice 17: multi-slice orchestration loop delivered.
- Slice 18: orchestration hardening and deterministic halt semantics delivered.
- Slice 19: in-pack telemetry and trace export contracts delivered.
- Slice 20: tiered provider routing and API-key policy enforcement delivered.
- Slice 21: boundary reconciliation docs and compliance notes delivered.
- Slice 22: System Pack approval/activation gate integration delivered.
- Slice 23: evidence harvest and teardown envelope emission delivered.
- Slice 24: System-led evidence commit and teardown confirmation delivered.

## 0.7.0 — 2026-06-29

- Phase 3: Tier-2 decomposer heuristics and robustness
	- Added conservative token-cost estimation (`_estimate_tokens_for_node`) with `tier_hint` prioritization
	- Grouping heuristics (`group_nodes_into_slices`) to pack `PlanNode`s into `TaskSlice`s within a token budget
	- `assign_task_slices` supports grouped slices and marks oversized nodes in `TaskSlice.task_description`
	- Added unit tests for grouping, priority effects, missing allowed tool handling, and oversized-node detection

## 0.2.0 — 2026-06-28

- Added `domain-lib/job_intake.py`: `ValidationResult` class and `validate_job()` — lightweight deterministic payload validation (title required, description ≥ 10 chars, priority enum check).
- Added `domain-lib/micro_context.py`: `build_micro_context()` — maps job priority to routing tier and builds a micro-context dict for downstream routing.
- Updated `controllers/nlp_pre_interpreter.py`: wires `validate_job` + `build_micro_context` on JSON payloads found in input; exposes `job_validation` and `micro_context` output keys.
- Updated `controllers/runtime_adapters.py`: `domain_step()` reads `evidence["micro_context"]` to prefer `scope_valid` and `tier` for routing decisions.
- Added `tests/test_coding_agent_job_intake.py`: 3 focused tests covering validator, micro-context builder, and pre-interpreter extraction.
- `docs/MANIFEST.yaml` regenerated; 296 SHA-256 entries OK.

## 0.1.0 — 2026-06-28

- Added initial Slice 7 skeleton for the coding-agent model pack.
- Added System Pack-only ingress invariants and deterministic adapter stubs.
- Added prompt and turn interpretation contracts for bounded artifact generation.

## 0.3.0 — 2026-06-28

- Design for Slice 9: `context_staging.py`, `job_interpreter.py`, `change_request.py` (planned). 
- Added tests for hermes abstractions: `tests/test_coding_agent_hermes_abstractions.py` (planned execution in Slice 9).

## 0.4.0 — 2026-06-28

- Slice 10: Tool-call policy enforcement and real test runner
- Added `domain-lib/tool_policies.py`: deny-by-default tool-call policy builder and checker
- Replaced `controllers/tool_adapters.py::run_tests_tool()` with a safe subprocess-backed runner guarded by an explicit command allowlist
- Wired policy check in `controllers/runtime_adapters.py::domain_step()` to reject unauthorized tool calls
- Added `tests/test_coding_agent_tool_policies.py` covering policy logic and safe test runner behavior

## 0.5.0 — 2026-06-28

- Slice 11 (start): Three-tier execution contracts and Tier-3 dispatcher
- Added `domain-lib/tier_contracts.py`: `PlanDAG`, `PlanNode`, and `TaskSlice` dataclasses
- Added `controllers/tier_dispatcher.py`: initial Tier-3 dispatcher calling existing adapters and emitting `SequentialThinkingTrace`
- Wired dispatcher into `controllers/runtime_adapters.py` to handle `task_slice` evidence
- Added `tests/test_coding_agent_tier_contracts.py` covering basic Tier-3 dispatch path