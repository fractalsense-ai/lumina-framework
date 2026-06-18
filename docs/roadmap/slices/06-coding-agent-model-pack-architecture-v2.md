---
version: 1.0.0
last_updated: 2026-06-18
---

# Slice 6: Coding Agent Model Pack Architecture V2

**Version:** 1.0.0
**Status:** Active
**Last updated:** 2026-06-18
**PR:** This document is itself the primary deliverable of Slice 6.

---

## Purpose

Preserve the Coding Agent Model Pack V2 architecture as an authoritative
roadmap contract before implementation begins.

The Coding Agent is a highly isolated, secure forge within the Lumina
Framework. It does not handle daily decentralised operations. This slice
captures the full internal architecture — ingestion, routing, proving, recovery,
and memory — so that implementation slices (Slice 7+) have a stable,
governance-reviewed reference.

This document is documentation-only. No runtime code is implemented in this
slice.

---

## Scope

- Document the Coding Agent Model Pack V2 internal architecture across all
  seven areas: Micro-Context Injector, Model Manifest/Registry, Template
  Engine dependency, Execution Swarm/Model Routing, Proving Ground/CI-CD,
  3-Strike Error Recovery Loop, and Experiential Memory Pipeline.
- Define conceptual contracts for each architectural area.
- Preserve the System Pack-only ingress invariant established in Slice 5.
- Keep the architecture hardware-neutral and provider-neutral.
- Update roadmap discoverability and manifest entries for this slice.

---

## Out of Scope

- Creating the `model-packs/coding-agent/` directory skeleton (Slice 7+).
- Implementing any runtime code, executable controllers, or schemas.
- Implementing physics proposal flows (reserved for later slices).
- Removing or moving existing domain packs.
- Mentioning or depending on specific hardware components or compute
  configurations.
- Hard-coding a dependency on any single model provider or vendor.

---

## Required Changes

### New files

| File | Purpose |
|------|---------|
| `docs/roadmap/slices/06-coding-agent-model-pack-architecture-v2.md` | This file — Slice 6 architecture contract record |

### Updated files

| File | Change |
|------|--------|
| `docs/roadmap/README.md` | Added Slice 6 row to the Slice Index table |
| `docs/MANIFEST.yaml` | Added entry for this file and updated hashes for changed docs |

---

## Architecture Overview

The Coding Agent Model Pack receives a fully scoped `CodingAgentJob` from the
System Pack only. It manufactures and stages artifacts; it does not activate,
register, or deploy them. Governance approval and registration remain with the
System Pack.

```text
System Pack
  -> creates fully scoped CodingAgentJob
  -> invokes Coding Agent (sole allowed ingress)
     -> Micro-Context Injector
     -> Model Manifest / routing decision
     -> Template Engine (template reference injected)
     -> Execution Swarm (code generation)
     -> Proving Ground (ephemeral sandbox CI-CD)
       -> pass: produce CodingAgentBuildResult (staged, not activated)
       -> fail: 3-Strike Error Recovery Loop
         -> attempt 1 and 2: constrained repair via System Pack/planning layer
         -> attempt 3 failure: hard stop + human-in-the-loop escalation
     -> Experiential Memory Pipeline (harvest lessons)
  -> return CodingAgentBuildResult to System Pack
System Pack governs approval / registration / activation
```

---

## Architecture Areas

### 1. Micro-Context Injector

Responsibility: strip macro-system noise from the inbound `CodingAgentJob` and
produce a `MicroContextPacket` that exposes only the minimum required context to
the generating model.

Key behaviours:

- Accepts only a fully scoped `CodingAgentJob`; never accepts raw
  natural-language requests or unclassified inputs.
- Exposes only immediate prerequisites: allowed boundaries, required logic,
  constraints, and expected output schema.
- Explicitly excludes raw chat history, unrelated domain state, and
  framework-wide operational context from the model's context window.
- Produces a `MicroContextPacket` that is the sole context surface presented to
  the generating model.

Governance invariant:

```text
Raw chat history and macro-system state never become direct operational context
for the generating model. Context is structured, scoped, and deterministic.
```

---

### 2. Model Manifest / Model Registry

Responsibility: maintain a local structured registry of available model
capabilities so that job routing is deterministic and provider-neutral.

Key behaviours:

- Implemented as a local structured store (SQLite or equivalent); no dependency
  on a single external registry service.
- Each record (`ModelCapabilityRecord`) captures: language proficiency,
  context-window limits, latency/cost profile, local-or-cloud availability, and
  cognitive weight / routing tier.
- Selection is driven by job requirements, not hard-coded provider preference.
- Registry is updatable without runtime code changes to the Coding Agent core.

Governance invariant:

```text
Model selection is provider-neutral. No single model provider is a hard
dependency of the Coding Agent Model Pack.
```

---

### 3. Template Engine / Template Pack Dependency

Responsibility: ensure that the generating model fills an approved structural
template rather than inventing architecture from a blank context.

Key behaviours:

- Template selection is mediated by the System Pack and/or the Template Model
  Pack before the job reaches the Coding Agent.
- The `CodingAgentJob` carries a `TemplateSelectionRef` that identifies the
  approved template context to inject.
- Template examples include (but are not limited to): sensor-data parser,
  text chunker, API endpoint, slash command, module workflow, validation
  scaffold, and test scaffold.
- The Coding Agent does not select or override templates autonomously.

Governance invariant:

```text
Template selection is a governed decision made upstream (System Pack /
Template Model Pack). The Coding Agent consumes the template reference;
it does not author template policy.
```

---

### 4. Execution Swarm / Model Routing

Responsibility: route code-generation sub-tasks to the appropriate model tier
based on cognitive weight and task complexity.

Key behaviours:

- Complex architecture work, deep refactoring, or high-risk logic changes are
  routed to higher-capability (frontier-class) models, which may be cloud-based
  or local depending on deployment posture.
- Boilerplate generation, unit-test creation, JSON formatting, curation, and
  low-risk transformations are routed to lightweight or local small-language
  models to reduce latency and cost.
- Routing decisions are driven by the `ModelCapabilityRecord` cognitive-weight
  tier, not hard-coded model names.
- Hybrid local/cloud deployment is an optional posture, not a base requirement.
  The Coding Agent operates correctly in local-only, cloud-only, or hybrid
  configurations.

Governance invariant:

```text
Execution routing is hardware-neutral and provider-neutral. Deployment
posture (local, cloud, hybrid) is a configuration concern, not an
architectural constraint of this pack.
```

---

### 5. Proving Ground / Automated CI-CD

Responsibility: validate every generated artifact in an ephemeral isolated
environment before any result is surfaced to the System Pack.

Key behaviours:

- No generated code touches the live framework directly.
- A temporary isolated sandbox (container, worktree, or equivalent ephemeral
  environment) is created for each build attempt.
- Validation includes: schema checks, import/dependency checks, unit and
  integration tests, permission/secret boundary checks, and regression checks
  where a prior baseline exists.
- Sandbox teardown is mandatory after every attempt (pass or fail) to release
  resources and prevent state leakage.
- Teardown failure is a ledgered escalation event, not a silently ignored error.
- A passing `SandboxRunResult` stages the artifact and produces the
  `CodingAgentBuildResult`; it does not activate or register the artifact.

Governance invariant:

```text
Mechanical success (passing tests in the sandbox) does not equal activation.
Activation authority rests with the System Pack, not with the Coding Agent.
Sandbox teardown failure is always escalated and ledgered.
```

---

### 6. 3-Strike Error Recovery Loop

Responsibility: provide a deterministic, bounded error-recovery mechanism that
prevents infinite retry loops, uncontrolled compute spending, and unfiltered
error injection into generating models.

Key behaviours:

**Attempt 1:** The generated artifact is built and tested in the sandbox.

**Attempts 2 and 3 (constrained repair):**
- If attempt 1 fails, the raw failure evidence is routed upstream to the System
  Pack or planning layer.
- The System Pack/planning layer analyses the failure (syntax error, logic
  error, schema violation, constraint violation, etc.) and produces a
  constrained repair prompt/job with tightened boundaries.
- Raw stack traces and build logs are not dumped unfiltered into the generating
  model. They are normalised and summarised into actionable constraints before
  being re-presented as a new `CodingAgentJob`.
- Each repair attempt produces a `RepairAttemptRecord` that is logged.

**Hard stop (attempt 3 failure):**
- If all three attempts fail, the Coding Agent enters a hard-stop state.
- Token and compute spending halts immediately.
- The Coding Agent packages the failed artifact, the complete task graph /
  `CodingAgentJob` context, all build artifacts, and all error evidence into
  a structured escalation packet for developer intervention.
- A human-in-the-loop escalation is raised and ledgered.
- No further automated retry occurs until a developer resolves and re-authorises
  the job.

Governance invariant:

```text
The Coding Agent makes at most three attempts per job.
Raw error evidence is never injected unfiltered into a generating model.
Token and compute spending stops on hard-stop.
Hard-stop escalation is always ledgered and requires human resolution before
any re-attempt.
```

---

### 7. Experiential Memory Pipeline

Responsibility: harvest and curate architectural lessons from build outcomes so
that future System Pack planning can incorporate past constraints.

Key behaviours:

- Both successful builds and 3-strike failures are candidates for lesson
  harvesting.
- Raw build logs are parsed, summarised, and distilled by the pipeline into
  dense, actionable architectural constraints (e.g., "pattern X caused Y
  failure in context Z").
- Curated lessons are stored in a structured registry (vector store, SQLite, or
  equivalent) as `CodingAgentMemoryLesson` records.
- Future System Pack planning may query this registry to inject curated
  constraints into new job generation, reducing the risk of repeating known
  failure patterns.
- Memory lessons do not autonomously mutate the system, trigger builds, or
  activate any artifact. Memory informs future planning; it does not directly
  activate anything.

Governance invariant:

```text
Memory lessons inform future planning only. They do not autonomously trigger
code generation, artifact mutation, registration, or activation.
Autonomous mutation from memory is explicitly forbidden.
```

---

## New/Changed Contracts

This slice is planning-level documentation. No executable runtime contracts are
implemented.

### `CodingAgentJob` (conceptual — extends Slice 5 definition)

Expected fields/concepts:

```text
job_id
source_request_id
authority_decision_id
requester_context            (from System Pack only)
target_artifact_type
requested_scope
selected_template_refs       (TemplateSelectionRef list)
scoped_context_refs
allowed_file_boundaries
validation_requirements
registration_expectation
activation_policy_ref
created_by_system_pack       (always true; enforced invariant)
created_at
```

### `MicroContextPacket` (conceptual)

Expected fields/concepts:

```text
job_id
immediate_prerequisites
allowed_boundaries
required_logic
constraints
expected_output_schema
injected_template_ref
```

### `ModelCapabilityRecord` (conceptual)

Expected fields/concepts:

```text
model_id
provider_ref                 (provider-neutral identifier)
language_proficiencies
context_limit
latency_profile
cost_profile
availability                 (local | cloud | hybrid)
cognitive_weight_tier        (lightweight | standard | frontier)
last_verified
```

### `TemplateSelectionRef` (conceptual)

Expected fields/concepts:

```text
template_id
template_type
template_version
selected_by                  (system_pack | template_model_pack)
```

### `SandboxRunResult` (conceptual)

Expected fields/concepts:

```text
run_id
job_id
attempt_number
outcome                      (pass | fail)
schema_check_result
import_check_result
test_results
permission_boundary_check
regression_check_result
teardown_status              (success | failure)
teardown_failure_escalation_id
artifacts_path
created_at
```

### `RepairAttemptRecord` (conceptual)

Expected fields/concepts:

```text
repair_id
job_id
attempt_number
prior_failure_summary
constrained_repair_job_ref
produced_by                  (system_pack | planning_layer)
created_at
```

### `CodingAgentBuildResult` (conceptual)

Expected fields/concepts:

```text
build_result_id
job_id
outcome                      (staged | hard_stop)
staged_artifact_path
all_sandbox_run_results
repair_attempts
hard_stop_escalation_id
activation_status            (always: not_activated)
created_at
```

### `CodingAgentMemoryLesson` (conceptual)

Expected fields/concepts:

```text
lesson_id
source_job_id
source_outcome               (success | 3_strike_failure)
distilled_constraints
raw_evidence_ref
stored_at
queryable_by                 (system_pack_planning | authorised_roles)
```

---

## Files Likely Touched

```text
docs/
  roadmap/
    README.md                                                      ← UPDATED (Slice 6 row added)
    slices/
      06-coding-agent-model-pack-architecture-v2.md               ← NEW (this file)
  MANIFEST.yaml                                                    ← UPDATED (new entry + hashes)
```

---

## Acceptance Criteria

- [ ] Slice 6 documentation exists and is discoverable from the roadmap/docs
      structure.
- [ ] Documentation preserves the System Pack-only ingress invariant: the
      Coding Agent may only be invoked by the System Pack.
- [ ] Documentation is hardware-neutral; it does not depend on or mention
      specific hardware components.
- [ ] Documentation is provider-neutral; no single model provider is a hard
      dependency.
- [ ] Documentation covers all seven architecture areas:
  - Micro-Context Injector
  - Model Manifest / Model Registry
  - Template Engine / Template Pack dependency
  - Execution Swarm / Model Routing
  - Proving Ground / Automated CI-CD
  - 3-Strike Error Recovery Loop
  - Experiential Memory Pipeline
- [ ] Documentation states that no runtime code is implemented in this slice.
- [ ] Documentation preserves governance separation: Coding Agent
      manufactures/stages; System Pack governs approval/registration/activation.
- [ ] Documentation states that mechanical success (passing sandbox tests) does
      not equal activation.
- [ ] Documentation states that memory lessons do not autonomously mutate the
      system.
- [ ] All eight conceptual contracts are documented:
  - `CodingAgentJob`
  - `MicroContextPacket`
  - `ModelCapabilityRecord`
  - `TemplateSelectionRef`
  - `SandboxRunResult`
  - `RepairAttemptRecord`
  - `CodingAgentBuildResult`
  - `CodingAgentMemoryLesson`
- [ ] `docs/roadmap/README.md` includes a Slice 6 row in the Slice Index table.
- [ ] `docs/MANIFEST.yaml` includes an entry for this file.

---

## Tests

This slice is documentation-only. No new automated tests are created.

Validation performed:

1. Manual review for all required Slice 6 contract sections and invariants.
2. Manual verification that roadmap discoverability and manifest entries are
   updated.
3. Repository integrity checks run where practical
   (`python model-packs/system/controllers/verify_repo.py` if available).
4. Manifest hash validation run/updated according to repository convention
   (`python model-packs/system/controllers/manifest_integrity.py check`).

If markdown linting or document checks are added in a later slice, this file
should be included in that validation.

---

## Ledger/Governance Impact

This slice performs no runtime mutations and no ledger writes.

Governance invariants locked or reinforced by this slice:

```text
The Coding Agent has exactly one ingress: the System Pack. (reinforced from Slice 5)
The Coding Agent receives only fully scoped CodingAgentJob records.
The Coding Agent manufactures and stages artifacts only; it does not activate,
  register, or deploy artifacts.
Template selection is a governed upstream decision; the Coding Agent consumes
  the template reference and does not author template policy.
Model routing is provider-neutral and hardware-neutral.
No generated code touches the live framework directly.
Sandbox teardown is mandatory; teardown failure is a ledgered escalation.
Mechanical success (passing sandbox tests) does not equal activation.
The 3-strike loop bounds retry attempts; compute spending halts on hard stop.
Raw error evidence is never injected unfiltered into a generating model.
Hard-stop escalation requires human resolution before re-authorisation.
Memory lessons inform future planning only; they do not autonomously trigger
  any mutation, build, activation, or registration.
```

---

## Governance and Safety Invariants

```text
System Pack-only ingress is enforced. No other caller may invoke the Coding Agent.
The Coding Agent has no activation authority.
The Coding Agent has no registration authority.
The Coding Agent has no deployment authority.
Mechanical correctness does not equal governance approval.
Memory lessons do not autonomously mutate the system.
Sandbox teardown failure is always escalated and ledgered.
Compute spending is bounded by the 3-strike limit and hard-stop.
Context presented to generating models is always structured, scoped, and
  deterministic — never raw chat history or unfiltered error logs.
```

---

## Follow-Up Slices

| Slice | Anticipated Title |
|-------|-------------------|
| 07 | Coding Agent Pack Skeleton |
| 08 | CodingAgentJob Schema and Ingress Contract |
| 09 | Micro-Context Injector Contract |
| 10 | Model Manifest Registry |
| 11 | Template Injection Interface |
| 12 | Ephemeral Sandbox Harness |
| 13 | 3-Strike Error Recovery Loop |
| 14 | BuildResult and Staging Contract |
| 15 | Coding Agent Experiential Memory Pipeline |
