---
title: "Slice 24 — System-Led Evidence Commit and Teardown Confirmation"
slice: 24
status: delivered
version: 0.1.0
last_updated: 2026-07-07
---

This slice implements the System Pack side of the evidence lifecycle after
Coding Agent orchestration emits `evidence_commit` and `teardown_result`.

Goals:
- Commit Coding Agent evidence as System-led `CommitmentRecord` entries.
- Confirm teardown on success and escalate cleanup failures deterministically.
- Preserve governance invariants: Coding Agent still cannot self-commit or self-activate.

Implemented:
- `model-packs/system/controllers/evidence_commit_teardown.py`
  - `commit_evidence_and_confirm_teardown(payload)`
  - Transaction progression using `state_transaction_adapter`
    (`PROPOSED -> VALIDATED -> COMMITTED -> FINALIZED`).
  - Ledger writes for:
    - `evidence_commit`
    - `teardown_confirmation` on success
    - `cleanup_escalated` on teardown failure
- `tests/test_system_evidence_commit_and_teardown.py`
  - Success path
  - Teardown failure escalation path
  - Idempotency for finalized transactions
  - Invalid payload guard

Notes:
- Lifecycle markers emitted by this slice:
  `EvidenceCommitted -> TearingDown -> TeardownConfirmed`
  with failure markers `TeardownFailed -> CleanupEscalated`.
- `HarvestingEvidence` is tracked in transaction metadata before commit.
- Orchestration envelopes remain additive and backward compatible.
