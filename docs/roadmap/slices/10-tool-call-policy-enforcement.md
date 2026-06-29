---
version: 0.1.0
last_updated: 2026-06-28
status: Delivered
---

# Slice 10 — Tool-Call Policy Enforcement & Real Test Runner

## Purpose

Enforce a deny-by-default policy for tool adapters and replace the simulated
`run_tests_tool()` with a safe subprocess-backed runner. This slice closes an
authority gap so the coding agent cannot call adapters outside an allowlist.

## Scope

- Implement `domain-lib/tool_policies.py` for deterministic policy checks
- Implement a safe `run_tests_tool()` in `controllers/tool_adapters.py`
- Wire policy checks into `controllers/runtime_adapters.py::domain_step()`
- Add unit tests exercising the policy and runner

## Out of Scope

- Any networked forge/deploy operations
- Changing prompts or altering slice 9 artifacts

## Required Changes

- New file: `model-packs/coding-agent/domain-lib/tool_policies.py`
- Update: `model-packs/coding-agent/controllers/tool_adapters.py` (run_tests_tool)
- Update: `model-packs/coding-agent/controllers/runtime_adapters.py` (policy gate)
- New tests: `tests/test_coding_agent_tool_policies.py`

## Acceptance Criteria

- Tool calls with `tool_id` not in the registered adapter list are rejected
- The `run_tests_tool()` enforces a command allowlist and returns structured output
- Unit tests cover allowlist, deny, timeout, and success paths
- Manifest regenerated and manifest check passes
