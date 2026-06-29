---
version: 1.0.0
last_updated: 2026-06-28
---

# Slice 8: Job Intake and Micro-Context Injector

**Version:** 1.0.0
**Status:** Delivered
**Last updated:** 2026-06-28
**PR:** #64

---

## Purpose

Provide lightweight, deterministic job-payload validation and a micro-context
builder so the coding-agent's pre-interpreter can produce authoritative routing
signals before any SLM call.

The coding-agent pack must classify incoming jobs and select a routing tier
(`critical`, `ok`, `minor`) without touching live models, credentials, or
network calls. This slice gives the pre-interpreter the vocabulary it needs.

---

## Scope

- `model-packs/coding-agent/domain-lib/job_intake.py`:
  `ValidationResult` class, `validate_job(payload) -> ValidationResult`
- `model-packs/coding-agent/domain-lib/micro_context.py`:
  `build_micro_context(normalized_job, extras) -> dict`
- `model-packs/coding-agent/controllers/nlp_pre_interpreter.py` (updated):
  extract JSON job from input text; call `validate_job` + `build_micro_context`;
  expose `job_validation` and `micro_context` keys in the `pre_interpret()` output
- `model-packs/coding-agent/controllers/runtime_adapters.py` (updated):
  `domain_step()` reads `evidence["micro_context"]` to prefer `scope_valid` and
  `tier` for routing decisions over raw evidence flags
- `tests/test_coding_agent_job_intake.py`: 3 focused tests

---

## Out of Scope

- Live model calls, network calls, credential use
- Changing `src/lumina/` core code
- Forge or deployment automation
- Hermes prototype services (deferred to Slice 9)

---

## Required Changes

| File | Change |
|------|--------|
| `domain-lib/job_intake.py` | CREATE — `ValidationResult`, `validate_job()` |
| `domain-lib/micro_context.py` | CREATE — `build_micro_context()` |
| `controllers/nlp_pre_interpreter.py` | UPDATE — add JSON extraction, validation, micro-context building |
| `controllers/runtime_adapters.py` | UPDATE — `domain_step()` reads `micro_context` dict |
| `tests/test_coding_agent_job_intake.py` | CREATE — 3 tests |
| `docs/MANIFEST.yaml` | UPDATE — add pending entries, regen |

---

## New / Changed Contracts

| Symbol | Location | Description |
|--------|----------|-------------|
| `ValidationResult` | `domain-lib/job_intake.py` | `.valid: bool`, `.errors: list[str]`, `.normalized: dict` |
| `validate_job(payload)` | `domain-lib/job_intake.py` | Title required and non-empty; description ≥ 10 chars; priority ∈ `{low, normal, high}` (optional) |
| `build_micro_context(norm, extras)` | `domain-lib/micro_context.py` | Returns dict: `job_id`, `tier`, `scope_valid`, `files`, `created_at`, `extras` |
| `pre_interpret()` output | `controllers/nlp_pre_interpreter.py` | Adds `job_validation: dict\|None` and `micro_context: dict\|None` keys |
| `domain_step()` routing | `controllers/runtime_adapters.py` | Reads `evidence["micro_context"]` when present; prefers `scope_valid` and `tier` over raw flags |

### Priority → Tier Mapping

| Priority | Tier |
|----------|------|
| `high` | `critical` |
| `normal` | `ok` |
| `low` | `minor` |

---

## Files Touched

```
model-packs/coding-agent/
  domain-lib/
    job_intake.py          ← new
    micro_context.py       ← new
  controllers/
    nlp_pre_interpreter.py ← updated
    runtime_adapters.py    ← updated
tests/
  test_coding_agent_job_intake.py ← new
docs/
  MANIFEST.yaml            ← updated (regen)
```

---

## Acceptance Criteria

- `validate_job({})` returns `valid=False` with at least one error in `.errors`.
- `validate_job({"title": "Add README", "description": "Add a README explaining usage.", "priority": "normal"})` returns `valid=True` and `.normalized["priority"] == "normal"`.
- `build_micro_context(normalized)` maps `priority="high"` → `tier="critical"`, `"normal"` → `"ok"`, `"low"` → `"minor"`.
- `pre_interpret(text_containing_json_job)` returns a dict where `micro_context` is not `None`.
- `domain_step()` uses `micro_context["scope_valid"]` when `evidence["micro_context"]` is present, in preference to the raw `job_scope_valid` evidence flag.

---

## Tests

**File:** `tests/test_coding_agent_job_intake.py`

| Test | Description |
|------|-------------|
| `test_validate_job_ok` | Valid payload passes; normalized priority returned correctly |
| `test_validate_job_missing_fields` | Empty title and short description both produce errors |
| `test_pre_interpret_extracts_micro_context` | JSON job embedded in input text → `micro_context["tier"] == "critical"` for high priority |

All tests: no network, no live model, no credentials.

---

## Ledger / Governance Impact

None. This slice adds deterministic domain-lib helpers inside the coding-agent pack
boundary. It does not change authority gate logic, domain registry, or core engine
invariants.

---

## Follow-Up Slices

**Slice 9:** Context Staging and Job Interpretation — abstract Hermes prototype patterns
(`context_staging.py`, `job_interpreter.py`, `change_request.py`) into neutral,
authority-air-gapped coding-agent pack contracts.
