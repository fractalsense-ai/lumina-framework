---
version: 1.0.0
last_updated: 2026-06-19
---

# Slice 6: Coding Agent Model Pack Architecture V2

**Version:** 1.0.0
**Status:** Active
**Last updated:** 2026-06-19
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

### Authority Air Gap

The Coding Agent Model Pack is authority-air-gapped from the rest of the
system. It receives only a fully scoped `CodingAgentJob` created by the System
Pack. It never receives raw operator requests, user JWTs, developer JWTs,
production secrets, deployment credentials, ledger signing authority,
registration authority, or activation authority.

Operator and developer credentials are used by the System Pack and surrounding
runtime to authenticate users, evaluate tool-call access, constrain allowed
paths/actions, and record authority decisions in the ledger. Those credentials
are not included in model prompts, micro-context packets, repair prompts, build
logs presented to models, or generated artifact instructions.

The Coding Agent may manufacture, test, and stage artifacts. It may produce a
pull request, patch, build result, provenance manifest, or escalation packet. It
cannot promote its output to production. A generated artifact remains
`not_activated` until an authorized developer approves it and the System Pack
records the approval/activation decision.

"Air-gapped" in this slice means authority/credential air-gapped. It does not
require every deployment to be physically network-air-gapped. GitHub Actions,
local CLI execution, Forgejo/Gitea, self-hosted runners, internal model
gateways, and future decentralized runner systems are all valid deployment
postures when authority-bearing credentials and production rights do not reach
the generating model or Coding Agent generation layer.

Intended request/update flow:

```text
Operator request
  -> user JWT authenticates operator
  -> System Pack checks role/scope/tool-call authority
  -> System Pack writes/consults ledger authority records
  -> System Pack scopes request into CodingAgentJob
  -> Coding Agent receives scoped job only
  -> Coding Agent builds/stages/test-validates artifact
  -> PR, patch, BuildResult, provenance manifest, or escalation packet is produced
  -> developer reviews/signs off
  -> System Pack records approval
  -> only then can activation/registration/production promotion happen
```

The model does not receive:

```text
user JWT
developer JWT
GitHub token
production secrets
deployment credentials
ledger signing authority
activation authority
registration authority
raw operator auth context
```

The model receives:

```text
scoped job
allowed paths
selected template references
validation requirements
constraints
expected output shape
```

Generated pull requests should preserve a normal developer review experience:
inspect the diff, inspect CI checks and test output, inspect provenance/risk
summaries, then approve, request changes, or merge according to policy. Lumina
metadata such as `CodingAgentJob` ID, authority decision ID, allowed
boundaries, model/routing policy, commands run, test evidence, provenance
manifest, and `activation_status: not_activated` is supporting evidence. A PR
or passing CI result is never production activation.

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

#### CI/CD Provider and Forge-Neutral Adapter Posture

The Proving Ground is not itself a replacement for existing CI/CD systems. The
Coding Agent Model Pack should integrate with mature CI/CD control planes
through thin provider adapters while keeping execution, model selection, policy,
and artifact governance under Lumina control.

GitHub Actions is the first/reference adapter because it is widely used by
open-source and private development teams, supports pull-request checks, logs,
artifacts, branch protection, workflow dispatch, and self-hosted runners. This
does not make GitHub a required Lumina backend.

The Coding Agent architecture remains forge-neutral:

```text
Lumina task contract = source of truth
CI/CD provider = adapter
Runner = replaceable execution node
Repo host / forge = replaceable
Model provider = local, cloud, internal, or hybrid configuration
Artifact store = local or provider-specific
Policy = Lumina-owned
```

Supported and anticipated execution postures include:

```text
GitHub repository + GitHub Actions + GitHub-hosted runner
GitHub private repository + GitHub Actions + self-hosted runner
GitHub Enterprise + internal runner + internal model gateway
Local CLI + local git working tree + local model
Forgejo/Gitea + self-hosted runner + local/internal model
Future decentralized runner systems with signed tasks and signed results
```

Using GitHub integration must not imply:

```text
source code is public
source code is sent to cloud model providers
GitHub-hosted runners are required
GitHub is the only supported forge
GitHub Actions is the only possible CI/CD control plane
```

The reference GitHub adapter should treat GitHub as an event bus, PR/check UI,
artifact index, and audit surface. The actual execution may occur on a
self-hosted runner controlled by the repository owner or organization.

Corporate and privacy-sensitive deployments must be able to run:

```text
private repository
self-hosted runner
local or internal model endpoint
restricted network policy
explicit secrets policy
Lumina provenance manifest
human approval gate
```

without sending source code to external inference providers.

Provider adapters are expected to translate the neutral Coding Agent task
contract into provider-specific operations such as checkout, status reporting,
artifact upload, PR comments, or branch/PR creation. Core Coding Agent logic
must not depend directly on GitHub environment variables, GitHub APIs, or
GitHub-only concepts.

Provider credentials used by CI/CD adapters, forge adapters, or runners are
adapter-layer credentials. They may be used to check out code, post statuses,
upload artifacts, or open pull requests according to configured policy. They
must not be passed into model prompts, model tool calls, generated code
instructions, or unfiltered repair context.

Where a provider requires a token, the adapter must expose only the minimal
operation result to the Coding Agent core, not the credential itself.

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
authority_decision_ref
requester_identity_ref       (opaque reference only; no JWT/token)
target_artifact_type
requested_scope
selected_template_refs       (TemplateSelectionRef list)
scoped_context_refs
allowed_file_boundaries
allowed_tool_calls
forbidden_credentials
validation_requirements
registration_expectation
activation_policy_ref
requires_developer_approval
created_by_system_pack       (always true; enforced invariant)
created_at
```

### `AuthorityBoundaryRecord` (conceptual)

Expected fields/concepts:

```text
authority_decision_id
requester_identity_ref          (opaque reference only; no JWT/token)
authorized_scope
allowed_actions
denied_actions
allowed_file_boundaries
allowed_tool_calls
credential_exposure_policy      (never_expose_to_model)
activation_requires_developer
ledger_ref
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

### `CiCdProviderAdapter` (conceptual)

Expected fields/concepts:

```text
provider_id
provider_type                  (github_actions | local_cli | forgejo | gitea | other)
supported_triggers
status_reporting_capability
artifact_capability
pull_request_capability
runner_binding_model
requires_external_network
```

### `ForgeProviderAdapter` (conceptual)

Expected fields/concepts:

```text
forge_id
forge_type                     (github | github_enterprise | forgejo | gitea | local_git | other)
repository_ref
change_request_ref             (pull_request | merge_request | patch | none)
branch_management_capability
comment_capability
status_capability
authentication_boundary
```

### `RunnerCapabilityProfile` (conceptual)

Expected fields/concepts:

```text
runner_id
runner_kind                    (github_hosted | self_hosted | local_cli | decentralized)
labels
available_tools
network_policy
secrets_policy
model_access                   (none | local | internal | cloud | hybrid)
artifact_storage
is_ephemeral
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
provenance_manifest_ref
activation_status            (always: not_activated)
requires_developer_approval  (true)
created_at
```

### `CodingAgentProvenanceManifest` (conceptual)

Expected fields/concepts:

```text
manifest_id
job_id
provider_adapter
forge_adapter
runner_profile
base_ref
head_ref
base_sha
head_sha
model_policy
network_policy
secrets_policy
commands_run
files_changed
artifacts_produced
human_approval_required
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
- [ ] Documentation defines the Coding Agent authority air gap.
- [ ] Documentation states that user JWTs, developer JWTs, production secrets,
  deployment credentials, and ledger signing authority are never exposed to
  model context.
- [ ] Documentation states that operator/developer credentials are used by the
  System Pack/runtime for authentication, authorization, tool-call access,
  scoping, and ledgering, not by the generating model.
- [ ] Documentation states that generated PRs or passing CI checks are staged
  evidence, not production approval.
- [ ] Documentation states that developer sign-off plus System Pack ledger
  approval is required before activation/registration/production promotion.
- [ ] Documentation states that GitHub Actions is a reference CI/CD adapter,
  not a required Lumina backend.
- [ ] Documentation preserves forge-neutrality: GitHub, GitHub Enterprise,
  Forgejo/Gitea, local CLI, and future decentralized runners are treated as
  adapter postures.
- [ ] Documentation states that self-hosted runners are supported for private,
  local, corporate, and decentralized execution.
- [ ] Documentation states that GitHub integration must not imply public code,
  GitHub-hosted execution, or external model inference.
- [ ] Documentation identifies Lumina-owned responsibilities: task contract,
  policy, provenance, and activation boundary.
- [ ] Documentation adds conceptual contracts for authority boundaries, CI/CD
  provider adapters, forge adapters, runner capability profiles, and
  provenance manifests.
- [ ] Documentation states that memory lessons do not autonomously mutate the
      system.
- [ ] All thirteen conceptual contracts are documented:
  - `CodingAgentJob`
  - `AuthorityBoundaryRecord`
  - `MicroContextPacket`
  - `ModelCapabilityRecord`
  - `CiCdProviderAdapter`
  - `ForgeProviderAdapter`
  - `RunnerCapabilityProfile`
  - `TemplateSelectionRef`
  - `SandboxRunResult`
  - `RepairAttemptRecord`
  - `CodingAgentBuildResult`
  - `CodingAgentProvenanceManifest`
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
Authority is never delegated to the generating model.
User JWTs, developer JWTs, production secrets, deployment credentials, and
  ledger signing authority are never exposed to model context.
The Coding Agent receives scoped jobs only; it cannot activate, register,
  deploy, or promote its own output.
A PR or passing CI result is staged evidence, not production approval.
Developer sign-off and System Pack ledger approval are required before
  activation.
GitHub Actions may be the reference CI/CD adapter, but GitHub is not the Coding
  Agent architecture. CI/CD control planes, forge hosts, runners, model
  providers, and artifact stores are replaceable adapters. Lumina owns the task
  contract, policy, provenance, and activation boundary.
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
| 16 | CI/CD Provider Adapter Contract |
| 17 | Forge Provider Adapter Contract |
| 18 | Runner Capability Profile and Execution Postures |
| 19 | Coding Agent Provenance Manifest Contract |
