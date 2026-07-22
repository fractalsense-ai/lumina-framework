---
title: "Slice 29 Completion Handoff - Decision Precedent Frontend Transport"
slice: 29
status: delivered
version: 0.1.0
last_updated: 2026-07-20
---

## Slice 29 Completion Handoff

## Read This First

This is a narrow completion task for Slice 29, not a redesign and not the
beginning of Slice 30. The Slice 29 backend, contracts, review fixes, and PR
are complete. The remaining roadmap item is a compact authenticated frontend
transport for the existing decision-precedent API, followed by final delivery
validation.

Do not mark Slice 29 as delivered until this handoff work and the validation
checklist below are complete.

## Current State

- Repository: `fractalsense-ai/lumina-framework`
- Slice 29 branch: `feat/slice-29-decision-precedent`
- Active PR: #88, `Add scoped decision precedent escalation`
- Latest Slice 29 review-fix commit: `1021425 Restrict precedent evidence to summaries`
- Prior Slice 29 commits: `3f2c61b`, `3756b22`
- Slice 28 is delivered; Slice 29 depends on its scoped `ThreadSummaryRecord`
  institutional-memory evidence.
- The local working tree contains unrelated user-owned changes to `.coverage`,
  `docs/MANIFEST.yaml`, and the Slice 32 roadmap document. Do not stage,
  reformat, revert, or include those changes.

Before editing, confirm whether PR #88 has been merged. Prefer a fresh branch
from the post-merge `main`; if it has not merged, work from the current Slice
29 branch and keep this work isolated in a follow-up commit.

## What Is Already Delivered

### Backend and Security Boundaries

The backend is the source of truth and must not be weakened or bypassed by the
frontend.

- Active JWT `organization_id` and `site_id` are mandatory.
- Retrieval filters organization and site before ranking.
- Only timestamped institutional `ThreadSummaryRecord` entries are eligible
  precedent evidence. Other institutional record types are explicitly rejected.
- Raw messages, assistant responses, and transcripts are not persisted in
  precedent evidence, trace events, escalation packets, or vector metadata.
- Scoring is deterministic. Similarity, timestamp-derived recency, and
  policy-declared risk determine the tier. No model chooses authority.
- `mandatory_escalation` appends a pending existing `EscalationRecord`; it does
  not perform an approval, connector call, provider action, or business
  mutation.
- `require_confirmation` records explicit intent only. It is scoped to the
  actor and active operating context, expires after five minutes, and is replay
  protected.

### Existing API Contract

`POST /api/decision-precedent/preflight`

Request:

```json
{
  "message": "string, required and non-empty",
  "risk_class": "string, required and non-empty",
  "session_id": "string or null"
}
```

Response:

```json
{
  "confidence_record_id": "string",
  "organization_id": "string",
  "site_id": "string",
  "actor_id": "string",
  "policy_version": 1,
  "risk_class": "string",
  "final_score": 0.0,
  "tier": "suggest_only | require_confirmation | mandatory_escalation",
  "rationale_codes": ["string"],
  "confirmation_required": false,
  "escalation_record_id": "string or null"
}
```

`POST /api/decision-precedent/{confidence_record_id}/confirm`

- Requires the same authenticated actor and active organization/site context.
- Has no request body.
- Returns `{ "confirmation_id", "confidence_record_id", "tier" }`.
- Valid only for an in-memory pending `require_confirmation` decision.
- Treat `403`, `404`, `409`, and `410` as terminal error states. Do not retry
  automatically.

The API implementation and Pydantic models are in:

- `src/lumina/api/routes/decision_precedent.py`
- `src/lumina/api/models.py`
- `src/lumina/decision_precedent/`

## Frontend Integration Point

Use the established Slice 28 interaction pattern in `src/web/app.tsx`.

The app already:

- decodes the JWT only to determine whether an operating context exists;
- calls `/api/thread-routing/preflight` before the normal `/api/chat` call for
  a scoped first chat turn;
- holds an explicit `pendingRouting` state when user input is needed;
- uses authenticated `fetch` helpers and local `isLoading` state;
- covers this flow in `src/web/src/app.test.tsx`.

Keep this compact and local to the chat composer. Do not add a dashboard, a
new route, a new global store, or a second escalation resolver.

## Required Implementation

### 1. Add Explicit Frontend Types and One API Helper

In `src/web/app.tsx`, add narrow TypeScript types for the preflight and
confirmation responses. Follow `ThreadRoutingPreflight` and
`ThreadRoutingConfirmation` rather than introducing a generic untyped client.

Add a small authenticated helper beside the existing thread-routing API helper.
It must:

- use `VITE_LUMINA_API_BASE_URL` through the existing API-base convention;
- include the bearer token and JSON content type where a body is sent;
- parse a successful JSON response;
- surface the server `detail` text on a non-success response when available;
- never write the message to browser storage, logs, URL parameters, or an
  action-card payload.

### 2. Preflight Before Normal Chat Dispatch

For a scoped authenticated chat turn, call decision-precedent preflight after
thread routing is resolved and before the normal `/api/chat` request.

Use:

- the trimmed current chat input as `message` only for the preflight request;
- the resolved session ID as `session_id`;
- a deliberately selected initial `risk_class`.

Do not infer risk with an LLM. Until a product-owned risk selector exists, use
one conservative, explicit UI default such as `operational`, document it in
the code, and keep the risk input easy to replace. Do not silently derive risk
from message content.

The agent should inspect the existing UI conventions and select the smallest
control that fits the composer. A compact select/menu is acceptable. It must
offer only plain strings accepted by current Business Ops policy:

- `routine`
- `operational`
- `financial`
- `safety`
- `legal`

This is presentation input, not policy authority. The server decides every
tier.

### 3. Render Three Compact, Non-Authoritative States

Add local state such as `pendingDecisionPrecedent`. Place a compact panel above
the composer beside the existing routing confirmation panel.

#### `suggest_only`

- Continue the normal chat request without requiring another click.
- Show a short, non-sensitive status after the chat turn that identifies the
  returned tier and rationale codes only.
- Do not display raw retrieved summary text, message text, score internals,
  organization/site IDs, or actor ID.

#### `require_confirmation`

- Do not call `/api/chat` yet.
- Show a single explicit `Continue` command that calls the existing decision
  precedent confirmation endpoint.
- Disable duplicate input/actions while the request is pending.
- On success, clear pending precedent state and issue the original `/api/chat`
  request exactly once using the already resolved session/thread IDs.
- On failure, retain the pending UI when appropriate and show a concise error;
  do not replay or regenerate the preflight automatically.

#### `mandatory_escalation`

- Do not call `/api/chat` automatically.
- Show a non-actionable notice that human approval is required.
- It may show the tier and rationale codes, plus whether an escalation record
  was created. It must not expose the record ID as an authority token.
- Do not add Approve, Reject, Resolve, or provider/action buttons. Existing
  System Log escalation lifecycle remains the only resolution authority.
- Provide only a clear local dismissal/new-input behavior; it must not mutate
  the escalation record.

### 4. Preserve Existing Routing and Transcript Behavior

- Thread routing stays first. Decision preflight must use the session/thread
  result selected by Slice 28 before chat dispatch.
- Do not create, bind, fork, or attach threads from decision-precedent code.
- Continue local transcript persistence only after `/api/chat` succeeds.
- Reset all new pending state in `resetChatState`, logout/session-switch paths,
  and any state that already clears `pendingRouting`.
- Preserve existing `sessionFrozen`, error-boundary, accessibility, responsive,
  and button-disabled behavior.

## Test Plan

Extend `src/web/src/app.test.tsx`; reuse its route-aware `fetch` mocks.

Required tests:

1. A scoped turn performs thread-routing preflight/confirmation, then
   decision-precedent preflight, then normal chat for `suggest_only`.
2. A `require_confirmation` preflight blocks `/api/chat` until the user clicks
   `Continue`; confirmation endpoint is called once, then chat is sent once.
3. A `mandatory_escalation` preflight does not call `/api/chat` and renders no
   authority/mutation controls.
4. Preflight or confirmation failure surfaces an error and does not send chat.
5. Existing unscoped and Slice 28 routing tests still pass.
6. Assert the UI never renders the submitted message in the decision-status
   panel solely because of preflight state.

Keep backend contracts covered by their existing test modules. Add backend
tests only if implementation exposes a real contract gap; frontend work should
not rewrite policy, scorer, retrieval, auth, route, or schema code.

## Validation Commands

Run from the repository root unless noted:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_decision_precedent_policy.py tests/test_decision_precedent_scorer.py tests/test_decision_precedent_service.py tests/test_decision_precedent_api.py tests/test_decision_precedent_schemas.py tests/test_thread_routing_api.py tests/test_thread_routing_summaries.py

Push-Location src/web
npm run test:unit
npm run build
Pop-Location

git diff --check
```

Before declaring Slice 29 delivered, also run the repository's standard full
Python regression, Docker Compose Linux/backend/unit/E2E validation, and
manifest-integrity command. Use the existing repository scripts rather than
inventing replacements:

```powershell
.\scripts\run-full-verification.ps1
.\scripts\integrity-check.ps1
```

If Docker Compose is available, run the existing Slice 29-relevant service
checks after the frontend build. Record any environment-only failure precisely;
do not mark the slice delivered without reporting it.

## Explicit Non-Goals

- No connector routing, ERP integration, provider-specific APIs, or business
  mutation.
- No approval or escalation-resolution endpoint/UI.
- No LLM risk inference or LLM authority decision.
- No raw transcript, prompt, retrieved summary, credential, or provider data
  displayed or persisted by this transport.
- No broad chat redesign, new dashboard, or mobile redesign.
- No changes to unrelated Slice 32 files or `.coverage`.

## Completion Criteria

The remaining Slice 29 work is complete only when:

- All three tiers have the behavior above.
- A confirmation cannot result in more than one chat submission.
- A mandatory escalation cannot result in chat submission or a business action.
- The existing security boundaries are preserved by code and tests.
- Focused backend and frontend tests, build, full verification, integrity, and
  Docker Compose validation have been run or clearly reported as blocked.
- `docs/roadmap/slices/29-decision-precedent-confidence-and-escalation.md` is
  updated from `planned` to `delivered` only after those checks pass.
- `docs/MANIFEST.yaml` is regenerated or updated only for the Slice 29 roadmap
  status/version/hash change and any new tracked documentation artifact.

## PR Description Template

**Title:** `Complete Slice 29 decision-precedent transport`

**Scope:** Add a compact, authenticated chat-composer transport for the
existing Slice 29 decision-precedent preflight and confirmation APIs. Preserve
server authority and existing Slice 28 thread routing.

**Acceptance Criteria:**

- [ ] Scoped preflight runs after thread routing and before chat dispatch.
- [ ] `suggest_only` continues normally without exposing sensitive evidence.
- [ ] `require_confirmation` requires one explicit confirmation before exactly
  one chat submission.
- [ ] `mandatory_escalation` blocks chat and exposes no approval/mutation UI.
- [ ] Existing scope, replay-protection, transcript-free, and escalation
  boundaries remain intact.
- [ ] Slice 29 is marked delivered only after the full validation checklist.

**Test Checklist:**

- [ ] Targeted Slice 29 and Slice 28 Python tests.
- [ ] Frontend unit tests for all three tiers and error paths.
- [ ] `npm run build`.
- [ ] Full verification, integrity, and Docker Compose checks.
- [ ] `git diff --check`.
