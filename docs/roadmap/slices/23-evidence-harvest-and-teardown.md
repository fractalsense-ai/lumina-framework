---
title: "Slice 23 — Evidence Harvest & Teardown"
slice: 23
status: delivered
version: 0.1.0
last_updated: 2026-07-01
---

This slice implements minimal evidence harvesting and teardown coordination
for the Coding Agent. It intentionally avoids self-activation and delegates
real persistence and resource removal to the System Pack.

Goals:
- Add a serialization-friendly `EvidencePacket` contract.
- Add a conservative `TeardownCoordinator` stub for simulated cleanup.
- Wire a minimal harvest trigger in the orchestration loop to expose
  `evidence_commit` and `teardown_result` in the orchestration envelope.
