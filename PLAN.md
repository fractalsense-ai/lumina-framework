# PLAN.md — Lumina Framework Execution Plan
# Slice 7: Coding Agent Model Pack — Directory Skeleton

> **Architect:** Lead Architect (read-only authority — do not modify this file during execution)
> **Target Agent:** DeepSeek-Coder-V2-Lite (MoE), 64k context window
> **Available Tools:** `context7` (API/doc fetching), `sequential_thinking` (logic verification)
> **Date:** 2026-06-25

---

## Objective

Implement the `model-packs/coding-agent/` directory skeleton as specified in
[`docs/roadmap/slices/06-coding-agent-model-pack-architecture-v2.md`](docs/roadmap/slices/06-coding-agent-model-pack-architecture-v2.md).

This is the first implementation slice for the Coding Agent Model Pack. The
deliverable is a **runnable, registered, stub pack** — not a complete
implementation. All architectural areas (Micro-Context Injector, Model
Manifest, Execution Swarm, Proving Ground, 3-Strike Recovery, Experiential
Memory) are scaffolded with correct contracts but non-operational stubs.

**Hard invariants that cannot be violated in any step:**

- Zero domain-specific names may appear in `src/lumina/`.
- The Coding Agent has exactly one ingress: the System Pack (`CodingAgentJob`).
  No raw user input, JWT, or production credential may reach the pack or
  be injected into any prompt context.
- No generated artifact is activated without System Pack authorization.
- All new tests must carry the `base_framework` pytest marker.
- The System Log append-only hash-chain must not be broken.

---

## Context Needed

Query the following via `context7` before writing any code. Retrieve the
stable API signatures, field names, and schema structures you will need to
satisfy the contracts below. Do not guess field names — verify them.

| # | What to Fetch | Why |
|---|---------------|-----|
| 1 | `docs/roadmap/slices/06-coding-agent-model-pack-architecture-v2.md` | Full architecture contract for all 7 areas |
| 2 | `docs/roadmap/slices/01-framework-boundary.md` | Three-pack base framework invariants and build state machine |
| 3 | `docs/7-concepts/framework-boundary.md` | Authoritative boundary contract (base packs, activation gates) |
| 4 | `docs/7-concepts/domain-adapter-pattern.md` | Engine contract field reference; authoring rules for `runtime_adapters.py` |
| 5 | `docs/7-concepts/prompt-packet-assembly.md` | Full PPA pipeline — understand what the Coding Agent is injected into |
| 6 | `model-packs/template/pack.yaml` | Canonical `pack.yaml` shape to follow |
| 7 | `model-packs/template/cfg/runtime-config.yaml` | Canonical `runtime-config.yaml` shape |
| 8 | `model-packs/template/controllers/runtime_adapters.py` | The three required callables: `build_system_state`, `interpret_turn_input`, `domain_step` |
| 9 | `model-packs/system/pack.yaml` | How a base framework pack identity card is structured |
| 10 | `src/lumina/core/runtime_loader.py` | How the runtime loader resolves packs; discover required top-level keys |
| 11 | `src/lumina/core/domain_registry.py` | How packs are registered in `cfg/domain-registry.yaml` |
| 12 | `src/lumina/orchestrator/ppa_orchestrator.py` | What the orchestrator expects from `interpret_turn_input` and `domain_step` |
| 13 | `src/lumina/system_log/__init__.py` | `LogLevel`, `LogEvent`, `create_event` — use these for stub emission |
| 14 | `standards/domain-physics-schema-v1.json` | JSON schema that `domain-physics.json` must validate against |
| 15 | `tests/test_template_pack.py` | Pattern to follow when writing pack-structure tests |
| 16 | `tests/test_domain_pack_structure.py` | Cross-pack structural assertions — new pack will be asserted here |
| 17 | `docs/MANIFEST.yaml` | Manifest schema; all new files must be registered here |

---

## Execution Steps

Work through these steps **in order**. Each step is atomic: complete it and
verify it before proceeding to the next. Use `sequential_thinking` to verify
logic at steps marked *(verify)*.

### Phase 1 — Schema and Identity

**1.** Read `model-packs/template/pack.yaml` and `model-packs/system/pack.yaml`
in full. Derive the required top-level keys (`pack_id`, `version`, `description`,
`layers`, `modules`, `entry_points`). Do not invent new top-level keys.

**2.** Create `model-packs/coding-agent/pack.yaml` with:
- `pack_id: coding-agent`
- `version: "0.1.0"`
- `description`: one sentence capturing the authority-air-gapped artifact
  factory role (see Slice 6 §Authority Air Gap).
- `layers.model`, `layers.controller`, `layers.domain_lib`, `layers.view`
  referencing paths that will exist after all steps in this plan are done.
- `modules: [coding-agent-core]`
- `entry_points.runtime_config`, `entry_points.runtime_adapter` pointing to
  paths created in later steps.

**3.** *(verify with `sequential_thinking`)* Confirm `pack.yaml` satisfies all
keys required by `src/lumina/core/runtime_loader.py`. If a required key is
missing, add it now.

---

### Phase 2 — Domain Physics

**4.** Read `standards/domain-physics-schema-v1.json` in full. Note required
fields: `domain_id`, `version`, `invariants`, `standing_orders`,
`escalation_triggers`, `tool_call_policies`, and `permissions`.

**5.** Create `model-packs/coding-agent/modules/coding-agent-core/domain-physics.json`
with the following content:
- `domain_id: "coding-agent"`
- `version: "0.1.0"`
- Exactly one invariant: `"No generated artifact may be activated without
  explicit System Pack authorization."`
- One standing order: `"Accept only fully scoped CodingAgentJob inputs from
  the System Pack. Reject all other ingress."`
- One escalation trigger for `three_strike_failure` (hard stop + HITL).
- `permissions.mode: "770"` (same governance posture as the system pack —
  restricted to `root` and `super_admin`).
- Empty `tool_call_policies: {}` stub — policies will be added in later slices.

**6.** *(verify with `sequential_thinking`)* Validate `domain-physics.json`
against `standards/domain-physics-schema-v1.json`. If any required field is
absent or incorrectly typed, fix it before continuing.

---

### Phase 3 — Runtime Configuration

**7.** Read `model-packs/template/cfg/runtime-config.yaml` in full to understand
all top-level keys (`pack_id`, `adapters`, `modules`, `tool_call_policies`,
`slm`, `llm`, `rag`).

**8.** Create `model-packs/coding-agent/cfg/runtime-config.yaml` with:
- `pack_id: coding-agent`
- `adapters.runtime: controllers/runtime_adapters.py`
- `adapters.tools: []` (stub — no direct tool adapters in this slice)
- `modules.coding-agent-core.domain_physics:
  modules/coding-agent-core/domain-physics.json`
- `tool_call_policies: {}` stub
- `slm.enabled: false` (stub — routing logic is Slice 8+)
- `llm.enabled: false` (stub — no LLM calls from this pack in this slice)

**9.** Create `model-packs/coding-agent/cfg/domain-profile-extension.yaml` as a
minimal stub: one comment explaining the `CodingAgentJob` profile fields that
will be defined in a later slice. No functional content required now.

---

### Phase 4 — Runtime Adapters (Stub Callables)

**10.** Read `model-packs/template/controllers/runtime_adapters.py` in full.
Identify the three required callables and their exact signatures:
`build_system_state(payload: dict) -> dict`,
`interpret_turn_input(payload: dict) -> dict`,
`domain_step(payload: dict, state: dict) -> dict`.

**11.** Create `model-packs/coding-agent/controllers/__init__.py` (empty).

**12.** Create `model-packs/coding-agent/controllers/runtime_adapters.py`
implementing all three callables as authoritative stubs:
- `build_system_state`: return a minimal state dict with
  `{"job_id": None, "activation_status": "not_activated",
  "build_state": "Requested", "strike_count": 0}`.
- `interpret_turn_input`: validate that `payload` contains a `coding_agent_job`
  key. If absent, raise `ValueError("CodingAgentJob required — direct
  invocation forbidden.")`. Return `{"problem_solved": False,
  "problem_status": "awaiting_job"}`.
- `domain_step`: return `{"response": "Coding Agent stub — not yet
  operational.", "escalate": False}`.
- Import nothing from `src/lumina/`. This file must be self-contained.

**13.** *(verify with `sequential_thinking`)* Confirm `interpret_turn_input`
enforces the ingress guard (rejects payloads without `coding_agent_job`) and
returns only the two engine contract fields `problem_solved` and
`problem_status` without any domain-specific key names leaking into
`src/lumina/`.

---

### Phase 5 — Domain Library Stubs

**14.** Create `model-packs/coding-agent/domain-lib/__init__.py` (empty).

**15.** Create `model-packs/coding-agent/domain-lib/coding_agent_job.py` as a
stub data-class module:
- Define `CodingAgentJob` as a `dataclass` with fields: `job_id: str`,
  `allowed_paths: list[str]`, `template_ref: str`, `validation_requirements:
  list[str]`, `constraints: dict`, `expected_output_shape: str`,
  `activation_status: str = "not_activated"`.
- Add a module-level docstring noting this is the **sole authorised ingress
  payload type** for the Coding Agent.
- Import nothing from `src/lumina/`.

**16.** Create `model-packs/coding-agent/domain-lib/build_result.py` as a stub:
- Define `CodingAgentBuildResult` as a `dataclass` with fields: `job_id: str`,
  `build_state: str`, `artifact_paths: list[str]`, `test_evidence: dict`,
  `provenance_manifest: dict`, `activation_status: str = "not_activated"`.
- Docstring: `"A staged, not-yet-activated artifact output. The System Pack
  governs all activation and registration decisions."`.

---

### Phase 6 — Prompts Stub

**17.** Create `model-packs/coding-agent/prompts/` directory with a single file
`domain-persona-v1.md`:
- Content: a one-paragraph stub persona that explicitly states the Coding
  Agent receives only `CodingAgentJob` inputs, never raw user requests, and
  produces only staged, non-activated artifacts.
- Include a `<!-- TODO Slice 8+: Replace with full Micro-Context Injector
  prompt contract -->` comment at the end.

---

### Phase 7 — Pack Registration

**18.** Read `src/lumina/core/domain_registry.py` and the project's
`cfg/domain-registry.yaml` (or equivalent registry config) to find the exact
YAML structure for registering a new pack.

**19.** Add a `coding-agent` entry to the domain registry config with:
- `pack_id: coding-agent`
- `path: model-packs/coding-agent`
- `access_roles: [root, super_admin]`
- `status: stub` (signals to the runtime this pack is not yet operational)
- `ingress: system_pack_only: true`

**20.** *(verify with `sequential_thinking`)* Confirm the registry entry will be
correctly resolved by `domain_registry.py` without requiring any changes to
`src/lumina/`. If a schema validation step exists, run it mentally against the
new entry.

---

### Phase 8 — Roadmap and Manifest Bookkeeping

**21.** Create `model-packs/coding-agent/CHANGELOG.md` with a single `0.1.0`
entry: `"Initial directory skeleton — all adapters are stubs. Slice 7."`.

**22.** Create `model-packs/coding-agent/README.md` with:
- One-paragraph description of the pack's role.
- A `## Authority Air Gap` section (one paragraph, verbatim from Slice 6).
- A `## Directory Structure` fenced code block listing all files created in
  this plan.
- A `## Status` section: `Stub — not operational. See Slice 8+ for
  implementation.`

**23.** Create `docs/roadmap/slices/07-coding-agent-model-pack-skeleton.md`
following the exact structure of existing slice documents (`version` YAML
frontmatter, `Purpose`, `Scope`, `Out of Scope`, `Required Changes` table).
Fill in only the files changed in this plan. Do not add aspirational content
from Slice 8+.

**24.** Add a `Slice 7` row to `docs/roadmap/README.md` Slice Index table:
`| [07](slices/07-coding-agent-model-pack-skeleton.md) | Coding Agent Model Pack — Directory Skeleton | Active |`

**25.** Register all new files in `docs/MANIFEST.yaml`. Follow the existing
entry format exactly (path, sha256 placeholder, version, status). Mark each
new entry `status: stub`.

---

### Phase 9 — Tests

**26.** Read `tests/test_template_pack.py` and `tests/test_domain_pack_structure.py`
in full to understand the structural assertion patterns.

**27.** Create `tests/test_coding_agent_pack.py` with `pytest.mark.base_framework`.
Include the following test functions (all must pass before the PR is submitted):

| Test function | What it asserts |
|---------------|-----------------|
| `test_pack_yaml_keys_present` | `pack.yaml` contains `pack_id`, `version`, `description`, `layers`, `modules`, `entry_points` |
| `test_domain_physics_validates_against_schema` | `domain-physics.json` validates against `standards/domain-physics-schema-v1.json` using `jsonschema` |
| `test_runtime_adapters_callable` | All three callables are importable and return correct types for stub inputs |
| `test_interpret_turn_input_rejects_direct_invocation` | `interpret_turn_input({})` raises `ValueError` (no `coding_agent_job` key) |
| `test_interpret_turn_input_accepts_job` | `interpret_turn_input({"coding_agent_job": {}})` returns dict with `problem_solved` and `problem_status` |
| `test_build_result_not_activated_by_default` | `CodingAgentBuildResult(...)` has `activation_status == "not_activated"` |
| `test_no_lumina_imports_in_pack` | `controllers/runtime_adapters.py` and `domain-lib/*.py` contain no `import lumina` or `from lumina` |
| `test_registry_entry_exists` | The domain registry config contains a `coding-agent` key with `access_roles` including `root` |

**28.** *(verify with `sequential_thinking`)* Mentally run every test against
the files created in steps 2–25. If any test would fail, fix the source file —
do not modify the test to pass around a real defect.

---

## CI/CD Requirements

Run these commands in order from the repository root before marking the PR
ready. All commands must exit with code 0.

```powershell
# 1. Install the package in editable mode with dev extras
pip install -e ".[dev]"

# 2. Validate domain-physics.json against schema (standalone check)
python -c "
import json, jsonschema, pathlib
schema = json.loads(pathlib.Path('standards/domain-physics-schema-v1.json').read_text())
instance = json.loads(pathlib.Path('model-packs/coding-agent/modules/coding-agent-core/domain-physics.json').read_text())
jsonschema.validate(instance, schema)
print('domain-physics.json: OK')
"

# 3. Run only the new pack tests first (fast feedback loop)
python -m pytest tests/test_coding_agent_pack.py -v --tb=short

# 4. Run the full base_framework suite to prove no regressions
python -m pytest -m base_framework -v --tb=short

# 5. Run the full test suite with coverage (must not drop below existing coverage)
python -m pytest --cov=src/lumina --cov-report=term-missing -q

# 6. Verify CLI entry points still load (smoke test)
python -m lumina.cli.cli --help

# 7. Verify domain registry resolves the new pack without error
python -c "
from lumina.core.domain_registry import DomainRegistry
reg = DomainRegistry()
entry = reg.get('coding-agent')
assert entry is not None, 'coding-agent not found in registry'
assert 'root' in entry.get('access_roles', []), 'access_roles misconfigured'
print('Domain registry: coding-agent OK')
"
```

> **Failure policy:** If any command above fails, fix the code — do not
> suppress errors, skip tests, or patch the CI command. A passing suite with
> a suppressed failure is not a passing suite.

---

## Out of Scope for This Slice

The following are explicitly deferred to Slice 8+. Do not implement them:

- Micro-Context Injector runtime logic
- Model Manifest / Model Registry SQLite store
- Execution Swarm routing
- Proving Ground / ephemeral sandbox
- 3-Strike Error Recovery Loop
- Experiential Memory Pipeline
- Any LLM or SLM call from within the Coding Agent pack
- Physics proposal or physics patching flows
- Ledger signing, registration, or activation logic
- Any change to `src/lumina/` core engine code