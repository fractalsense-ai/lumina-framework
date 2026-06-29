# Coding Agent Pack Changelog

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