---
title: "Slice 21 — Framework Boundary Reconciliation"
slice: 21
pack: model-packs/coding-agent/pack.yaml
status: planned
version: 0.1.0
last_updated: 2026-06-30
sha256: pending
---

Summary
-------

This slice reconciles recent Coding Agent implementation slices with the
framework-boundary contracts established in Slices 1, 5, and 6. It updates
roadmap discoverability, expands thin slice records, and restates the boundary
guarantees that must remain true as the Coding Agent grows.

Purpose
-------

Recent work advanced the Coding Agent from skeleton to tiered planning,
execution gating, checkpoint persistence, orchestration, telemetry, and provider
routing. This slice ensures the implementation record remains anchored to the
original framework contract rather than drifting into an autonomous agent or
deployment authority.

Scope
-----

- Update the roadmap index through the current slice sequence.
- Expand thin Slice 13-15 records into boundary-aware roadmap entries.
- Add concise boundary compliance notes to Slices 16-20.
- Document Coding Agent boundary guarantees in the pack README.
- Clarify that direct module calls in tests are validation seams, not runtime
  ingress.
- Regenerate the documentation manifest.

Out of Scope
------------

- Implementing activation approval, registration, production promotion, evidence
  harvest, teardown, or ledger lifecycle machinery.
- Changing runtime authorization behavior unless a concrete boundary violation
  is found.
- Removing or extracting provisional domain packs.
- Introducing new model providers, credential stores, or external telemetry
  sinks.

Required Changes
----------------

- Update `docs/roadmap/README.md` through Slice 21.
- Expand `docs/roadmap/slices/13-tier-1-architect.md`.
- Expand `docs/roadmap/slices/14-dag-correct-compute-orchestration.md`.
- Expand `docs/roadmap/slices/15-tier3-execution-gating.md`.
- Add boundary compliance notes to Slices 16-20.
- Update `model-packs/coding-agent/README.md` with boundary guarantees.
- Update `docs/MANIFEST.yaml` via manifest regeneration.

New/Changed Contracts
---------------------

No executable runtime contracts are added in this slice. The slice clarifies and
preserves the following existing contracts:

- Base framework consists of System, Coding Agent, and Template model packs.
- The Coding Agent has exactly one runtime ingress: the System Pack.
- The Coding Agent manufactures and stages reviewable artifacts; it does not
  activate, register, deploy, or self-authorize them.
- Mechanical tests and local validation do not equal governance approval.
- Raw credentials and production authority do not enter Coding Agent state,
  prompts, checkpoints, telemetry, or provider routing metadata.
- Internal tests may import or call Coding Agent helpers directly as validation
  seams; those calls are not product/runtime ingress.

Files Likely Touched
--------------------

- `docs/roadmap/README.md`
- `docs/roadmap/slices/13-tier-1-architect.md`
- `docs/roadmap/slices/14-dag-correct-compute-orchestration.md`
- `docs/roadmap/slices/15-tier3-execution-gating.md`
- `docs/roadmap/slices/16-execution-state-persistence.md`
- `docs/roadmap/slices/17-multi-slice-orchestration-loop.md`
- `docs/roadmap/slices/18-orchestration-hardening-and-determinism.md`
- `docs/roadmap/slices/19-execution-telemetry-and-trace-export.md`
- `docs/roadmap/slices/20-tiered-model-and-api-key-routing.md`
- `model-packs/coding-agent/README.md`
- `docs/MANIFEST.yaml`

Acceptance Criteria
-------------------

- Roadmap README lists Slices 13-21 and explains active index vs original Slice
  1 follow-up planning.
- Slices 13-15 include Purpose, Scope, Out of Scope, contracts, acceptance
  criteria, tests, governance impact, and follow-up notes.
- Slices 16-20 include concise boundary compliance notes.
- Coding Agent README explicitly states no direct runtime ingress, no activation
  authority, no deployment/registration authority, and no raw credential storage.
- Docs manifest contains all changed/new docs with concrete SHA-256 hashes.
- Documentation/schema integrity tests pass.

Tests
-----

Run the documentation and manifest checks:

```powershell
c:/Users/dxn00/Documents/lumina-framework/.venv/Scripts/python.exe -m pytest -q tests/test_schema_versioning.py tests/test_system_log_integrity.py
```

If additional boundary guard tests are added, run those focused tests as well.

Ledger/Governance Impact
------------------------

This slice writes no ledger records and adds no lifecycle transitions. Its
governance impact is reconciliation: it makes the current roadmap and Coding
Agent documentation explicitly reflect the boundary contract before further
implementation continues.

Follow-Up Slices
----------------

- System Pack approval/activation gate for `Tested -> Staged -> AwaitingApproval -> Registered`.
- Evidence harvest and teardown contract for `HarvestingEvidence -> EvidenceCommitted -> TearingDown -> TeardownConfirmed`.
- Optional lightweight boundary regression tests if future drift becomes likely.