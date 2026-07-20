---
title: "Slice 29 — Decision Precedent, Confidence, and Escalation"
slice: 29
status: planned
version: 0.2.0
last_updated: 2026-07-20
---

## Purpose

Codify scoped institutional decision-precedent retrieval and deterministic
confidence scoring so Lumina can make an auditable recommendation when policy
permits and create a human-approval packet when confidence or risk requires it.

## Scope

- Consume only Slice 28 institutional `ThreadSummaryRecord` evidence through a
  hard organization/site filter; raw user messages, assistant responses, and
  transcripts are never precedent inputs or persisted evidence.
- Define a pure, deterministic confidence evaluation from policy-owned inputs:
  - strongest same-scope precedent similarity,
  - bounded recency band derived from record metadata,
  - policy-declared risk class,
  - explicit missing-evidence penalties.
- Define policy tiers with deterministic precedence:
  - `suggest_only`,
  - `require_confirmation`,
  - `mandatory_escalation`.
- Define a transcript-free business escalation packet that references precedent
  record IDs, policy version, component scores, and selected tier.
- Reuse existing System Log `EscalationRecord` lifecycle for mandatory
  escalation; Slice 29 creates evidence and a pending approval request only.

## Out of Scope

- Push-notification transport implementation.
- Final mobile UX.
- Connector resolution, provider-specific APIs, or ERP mutations (Slices 30-34).
- Automated execution, final approval, or commitment of any business action.
- LLM-generated confidence, implicit risk classification, or unbounded transcript
  summarization.

## Required Changes

- Add a policy-only Business Ops `decision-precedent-policy.yaml` with default,
  organization, and site overrides. System code resolves policy but cannot relax
  scope, audit, or escalation requirements.
- Add pure `decision_precedent` evaluation logic that retrieves eligible
  same-scope summaries, calculates component scores, chooses a policy tier, and
  emits no side effect.
- Add an authenticated scoped preflight endpoint that persists a transcript-free
  `TraceEvent` for every evaluation.
- Add a confirmation endpoint only for `require_confirmation`; it records
  explicit operator intent but must not execute a business operation.
- For `mandatory_escalation`, create a pending existing `EscalationRecord` whose
  evidence summary carries the schema-valid business escalation packet and whose
  organization/site scope matches the active JWT context.
- Add deterministic fixtures for high-confidence/low-risk recommendation,
  ambiguous or stale precedent confirmation, missing-precedent escalation, and
  high-risk escalation.

## New/Changed Contracts

- New `precedent_match` contract containing only scope, summary record identity,
  thread identity, similarity, recency band, and rank.
- New `decision_confidence_score` contract containing versioned component scores,
  penalties, final score, selected policy tier, and deterministic rationale codes.
- New `business_escalation_packet` contract for targeted owner/manager approval;
  it references decision and precedent record IDs and forbids raw transcript,
  prompt, credential, and provider-specific mutation data.
- New `decision_precedent_policy` contract with threshold bands, risk-class
  precedence, recency bands, candidate limits, and confirmation/escalation rules.
- Existing `EscalationRecord` remains the lifecycle record. Slice 29 extends
  only its allowed structured evidence/metadata payload, avoiding a breaking
  change to the generic escalation schema.

## Files Likely Touched

- `model-packs/business-ops/cfg/decision-precedent-policy.yaml` (new)
- `standards/precedent-match-schema-v1.json` (new)
- `standards/decision-confidence-score-schema-v1.json` (new)
- `standards/business-escalation-packet-schema-v1.json` (new)
- `standards/decision-precedent-policy-schema-v1.json` (new)
- `src/lumina/decision_precedent/` (new pure policy, scorer, and retrieval service)
- `src/lumina/api/routes/decision_precedent.py` (new scoped preflight/confirm API)
- `src/lumina/api/models.py` and `src/lumina/api/server.py`
- `tests/test_decision_precedent_policy.py` (new)
- `tests/test_decision_precedent_service.py` (new)
- `tests/test_decision_precedent_api.py` (new)
- `docs/roadmap/slices/29-decision-precedent-confidence-and-escalation.md`

## Acceptance Criteria

- Candidate retrieval cannot cross organization/site scope and never emits raw
  transcript content in a response, System Log record, persisted packet, or
  vector metadata.
- Fixed fixtures produce identical ordered precedent matches, component scores,
  tier, rationale code, and packet identity inputs across runs.
- Policy precedence is site override, organization override, then Business Ops
  default; invalid thresholds, invalid risk classes, and cross-scope overrides
  are rejected.
- High-risk and missing-precedent evaluations always select `mandatory_escalation`
  regardless of similarity score; `require_confirmation` never executes an action.
- Every preflight appends a scoped, transcript-free `TraceEvent`; mandatory
  escalation appends a schema-valid pending `EscalationRecord` that references
  the decision evidence.
- A user cannot view, confirm, or resolve a packet outside their active scope or
  authority; the existing escalation resolver remains the only approval lifecycle.
- Slice 28 routing, chat, transcript-resume, and existing escalation regression
  tests remain green.

## Tests

- Unit: score component arithmetic, penalty application, stable candidate ordering,
  and rationale/tier selection using fixed metadata fixtures.
- Unit: default/organization/site policy precedence; malformed policy, unsafe
  threshold ordering, and unsupported risk class rejection.
- Service: same-site retrieval success; cross-site and non-institutional record
  exclusion; stale/missing precedent handling without raw-text persistence.
- API: active-context requirement, preflight trace evidence, confirmation replay
  protection, mandatory-escalation packet creation, and cross-actor/scope denial.
- Schema: positive and negative validation for all four new contracts, including
  explicit rejection of transcript, credential, and provider mutation fields.
- Regression: existing escalation list/detail/resolve behavior, Slice 28 routing
  API/recap behavior, and transcript resume scope mismatch rejection.

## Ledger/Governance Impact

- Adds formal, transcript-free precedent and confidence traces plus pending
  approval packets to the System Log.
- Business Ops owns configurable score/risk thresholds; the System layer owns
  scope validation, authorization, append-only evidence, and escalation lifecycle.
- Recommendations, confirmations, and escalations never grant connector,
  mutation, approval, or commitment authority.

## Follow-Up Slices

- Slice 30: canonical business-system contracts and capability taxonomy.
- Slice 31: connector registry and capability routing.

## Implementation Plan

1. Define and validate the four contracts plus the Business Ops policy file;
  register them in `docs/MANIFEST.yaml` before adding runtime behavior.
2. Implement pure policy resolution and scoring with fixed fixtures. No API,
  persistence, or System Log mutation is permitted in this phase.
3. Add scope-filtered precedent retrieval over Slice 28 summary records and
  produce schema-valid evaluation evidence without retaining query text.
4. Add authenticated preflight/confirmation routes, System Log trace events,
  and pending `EscalationRecord` creation. Reuse existing escalation resolution
  rather than creating a parallel approval system.
5. Add frontend transport only after the API and policy matrix pass; the initial
  UI is a compact recommendation/confirmation/escalation state, not a redesign.
6. Run focused policy/service/API/schema tests, then the full Python, frontend,
  Docker Compose Linux, and manifest-integrity suites before marking delivered.

## PR Handoff

**Proposed title:** `Add scoped decision precedent escalation`

**Scope:** Add deterministic, policy-configured precedent evaluation over Slice
28 summaries; expose scoped recommendation/confirmation/escalation preflight;
write transcript-free audit evidence; create no connector or business mutation.

**Acceptance checklist:**

- [ ] Score and tier are deterministic for fixed fixtures.
- [ ] Scope filtering prevents cross-organization/site precedent or packet access.
- [ ] High-risk and missing-precedent cases always create a pending escalation.
- [ ] Confirmation is explicit, replay-protected, and cannot execute a business action.
- [ ] All evidence is schema-valid, transcript-free, and System-log committed.
- [ ] Existing Slice 28 routing and escalation lifecycle regressions pass.

**Test checklist:**

- [ ] Policy, scoring, service, API, and schema tests.
- [ ] Existing routing, auth, transcript-resume, and escalation regression tests.
- [ ] Full Python suite, frontend suite/build, Docker Compose Linux backend/unit/E2E,
    manifest integrity, and `git diff --check`.
