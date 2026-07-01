---
title: Slice 22 — System Pack Approval / Activation Gate
slice: 22
status: proposed
version: 1.0.0
last_updated: 2026-07-01
---

Summary
-------

Slice 22 adds an explicit activation/approval gate: the Coding Agent may
request activation of validated patches (e.g. `activation_request`), but
the final activation must be authorized by the System Pack. This preserves
the framework invariant that System Pack is the sole activation authority
and prevents the Coding Agent from self-activating changes or holding
deployment credentials.

Design
------

- Introduce a minimal `activation_gate` module that exposes `validate_activation(evidence)`.
- When a turn includes `activation_request: true`, runtime adapters must
  require `system_approval: { approved: true, issuer: 'system_pack' }`.
- If approval is missing, the runtime returns `action: awaiting_system_approval`
  and the request is halted for human or System Pack approval.

Acceptance criteria
-------------------

- The runtime returns `awaiting_system_approval` when an activation is
  requested without System Pack approval.
- When `system_approval` is present and valid, activation flow proceeds
  (the runtime may still stage the patch for review but should surface
  `approved: true` in the dispatch response).
- Unit tests cover both blocked and approved activation flows.

Notes
-----

- This slice is intentionally minimal: it enforces a record-level approval
  check and does not implement a signing or cryptographic workflow.
- For deployments that require stronger attestation, extend the approval
  object to include signatures and validation routines handled by System Pack.
