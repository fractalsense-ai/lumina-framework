---
version: 1.0.0
last_updated: 2026-05-07
---

# Slice 5: System Pack as Sole Coding Agent Ingress

**Version:** 1.0.0
**Status:** Active
**Last updated:** 2026-05-07
**PR:** This document is itself the primary deliverable of Slice 5.

---

## Purpose

Make the sole-ingress invariant explicit and discoverable:

> The Coding Agent has exactly one ingress: the System Pack.

Slice 5 closes the initial boundary/governance documentation phase started in
Slices [2](02-system-update-vocabulary.md),
[3](03-request-intake-and-classification.md), and
[4](04-system-pack-authority-gate.md). Slice 6+ begins implementation-heavy
work.

---

## Scope

- Define the only allowed invocation path into the Coding Agent.
- Explicitly list forbidden direct invocation paths.
- Document planning-level ingress contracts for future implementation.
- Preserve governance/safety invariants for authority, scoping, templating,
  staging, and activation boundaries.
- Update roadmap discoverability and manifest entries for this slice.

---

## Out of Scope

- Implementing Coding Agent pack behavior or invocation runtime.
- Implementing physics proposal validation or patching.
- Implementing provider/model selection abstraction.
- Implementing template injection logic.
- Implementing ledgers, build state machines, rollback, registration,
  activation, or teardown.
- Removing or moving experimental/domain/test packs.

---

## Required Changes

### New files

| File | Purpose |
|------|---------|
| `docs/roadmap/slices/05-system-pack-sole-coding-agent-ingress.md` | This file — Slice 5 planning and ingress contract record |

### Updated files

| File | Change |
|------|--------|
| `docs/roadmap/README.md` | Added Slice 5 row to the Slice Index table |
| `docs/MANIFEST.yaml` | Added entry for this file and updated hashes for changed docs |

---

## Ingress Flow

```text
Natural language request
  -> SystemUpdateRequest
  -> request classification
  -> System Pack authority gate
  -> System Pack scoping
  -> template/context selection
  -> fully scoped CodingAgentJob
  -> Coding Agent build/stage path
```

The Coding Agent does not receive raw natural-language requests, unclassified
requests, unscoped build desires, or requests that have not passed required
System Pack authority checks.

---

## Allowed and Forbidden Call Paths

### Allowed path (only)

```text
System Pack
  -> validates authority
  -> scopes the request
  -> selects/injects approved template context
  -> creates a fully scoped CodingAgentJob
  -> invokes Coding Agent
```

### Forbidden direct paths

```text
User -> Coding Agent
External caller -> Coding Agent
Domain pack -> Coding Agent
Template pack -> Coding Agent
Module workflow -> Coding Agent
Model provider -> Coding Agent
Test/deployment pack -> Coding Agent
Any model pack other than System Pack -> Coding Agent
```

Denied/invalid ingress attempts become structured denials/escalations in later
implementation slices, not guessed actions or ad hoc behavior.

---

## New/Changed Contracts

This slice is planning-level contract documentation. No runtime contract
implementation is required.

Expected conceptual contracts for later slices:

- `CodingAgentIngressRequest`
- `CodingAgentJob`
- `ScopedBuildJob`
- `IngressDecision`
- `IngressDenial`

Suggested `IngressDecision` outcomes for later implementation:

```text
allowed
denied
needs_authority
needs_scope
needs_template
escalated
```

Suggested `IngressDenial` reasons for later implementation:

```text
direct_coding_agent_access_forbidden
missing_authority_decision
missing_scope
missing_template
invalid_request_type
unknown_caller
```

`CodingAgentJob` must be fully scoped before invocation and is expected to
capture concepts such as:

```text
job_id
source_request_id
authority_decision_id
requester_context
target_artifact_type
requested_scope
selected_template_refs
scoped_context_refs
allowed_file_boundaries
validation_requirements
registration_expectation
activation_policy_ref
created_by_system_pack
created_at
```

---

## Files Likely Touched

```text
docs/
  roadmap/
    README.md                                           ← UPDATED (Slice 5 row added)
    slices/
      05-system-pack-sole-coding-agent-ingress.md       ← NEW (this file)
  MANIFEST.yaml                                         ← UPDATED (new entry + hashes)
```

---

## Acceptance Criteria

- [ ] Slice 5 documentation exists and is discoverable from the roadmap/docs
      structure.
- [ ] Documentation states that the Coding Agent has exactly one ingress: the
      System Pack.
- [ ] Documentation defines the allowed System Pack -> Coding Agent path.
- [ ] Documentation explicitly lists forbidden direct invocation paths.
- [ ] Documentation explains that Coding Agent jobs must be fully scoped before
      invocation.
- [ ] Documentation explains that authority evaluation happens before Coding
      Agent invocation.
- [ ] Documentation explains that template/context selection is mediated by the
      System Pack.
- [ ] Documentation preserves the invariant that the Coding Agent has no direct
      activation, registration, or deployment authority.
- [ ] Documentation preserves the invariant that mechanical correctness/testing
      does not equal governance approval.
- [ ] Documentation references Slices 2–4 where appropriate.
- [ ] Existing roadmap/index docs are updated so Slice 5 is easy to find.
- [ ] The document states that Slice 6+ begins implementation-heavy work.

---

## Tests

This slice is documentation-only. No new automated tests are created.

Validation performed:

1. Manual review for required Slice 5 contract sections and invariants.
2. Manual verification that roadmap discoverability and manifest entries are
   updated.
3. Lightweight repository checks run where practical.

If markdown linting/document checks are added later, this file should be
included in that validation.

---

## Ledger/Governance Impact

This slice performs no runtime mutations and no ledger writes.

Governance invariants locked by this slice:

```text
The Coding Agent has exactly one ingress: the System Pack.
The Coding Agent receives only fully scoped jobs.
The Coding Agent never receives raw/unclassified natural-language update requests directly.
The Coding Agent has no direct activation rights.
The Coding Agent cannot register or deploy artifacts on its own authority.
Template selection/context injection is mediated by the System Pack.
Authority evaluation happens before Coding Agent invocation.
Mechanical correctness/testing stages an artifact; it does not approve activation.
Denied or invalid ingress attempts become structured denials/escalations, not guessed actions.
```

---

## Follow-Up Slices

This slice closes the initial boundary/governance documentation phase. Slice 6+
shifts into implementation-heavy work.

| Slice | Anticipated Title |
|-------|-------------------|
| 06 | Physics Edit Proposal Flow |
| 07 | Physics Proposal Schema and Patch Contract |
| 08 | Physics Validation Harness |
| 09 | Physics Ledger and Rollback |
