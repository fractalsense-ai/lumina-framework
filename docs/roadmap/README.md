---
version: 1.2.0
last_updated: 2026-07-11
---

# Lumina Framework Roadmap

**Version:** 1.2.0
**Status:** Active
**Last updated:** 2026-07-11

---

## Overview

The Lumina Framework roadmap is delivered one slice at a time. Each slice is
a focused, reviewable unit of work with explicit scope, contracts, and
acceptance criteria.

Slices are numbered sequentially. Each slice is documented in its own file
under `docs/roadmap/slices/` and delivered as a focused PR.

---

## Slice Index

| Slice | Title | Status |
|-------|-------|--------|
| [01](slices/01-framework-boundary.md) | Framework Boundary and Final Shape Documentation | Active |
| [02](slices/02-system-update-vocabulary.md) | System Update Vocabulary | Active |
| [03](slices/03-request-intake-and-classification.md) | Request Intake and Classification | Active |
| [04](slices/04-system-pack-authority-gate.md) | System Pack Authority Gate | Active |
| [05](slices/05-system-pack-sole-coding-agent-ingress.md) | System Pack as Sole Coding Agent Ingress | Active |
| [06](slices/06-coding-agent-model-pack-architecture-v2.md) | Coding Agent Model Pack Architecture V2 | Active |
| [07](slices/07-coding-agent-pack-skeleton.md) | Coding Agent Pack Skeleton | Delivered |
| [08](slices/08-job-intake-micro-context.md) | Job Intake and Micro-Context Injector | Delivered |
| [09](slices/09-context-staging-and-job-interpretation.md) | Context Staging and Job Interpretation | Delivered |
| [10](slices/10-tool-call-policy-enforcement.md) | Tool-Call Policy Enforcement & Real Test Runner | Delivered |
| [11](slices/11-three-tier-execution-interface.md) | Three-tier Execution Interface | Delivered |
| [12](slices/12-tier-2-decomposer.md) | Tier-2 Decomposer & DAG Planner | Delivered |
| [13](slices/13-tier-1-architect.md) | Tier-1 Architect & SLM Routing | Delivered |
| [14](slices/14-dag-correct-compute-orchestration.md) | DAG-Correct Compute Orchestration | Delivered |
| [15](slices/15-tier3-execution-gating.md) | Tier-3 Execution Gating and Retry Policy | Delivered |
| [16](slices/16-execution-state-persistence.md) | Execution State Persistence & Checkpoint Recovery | Delivered |
| [17](slices/17-multi-slice-orchestration-loop.md) | Multi-Slice Orchestration Loop | Delivered |
| [18](slices/18-orchestration-hardening-and-determinism.md) | Orchestration Hardening and Determinism | Delivered |
| [19](slices/19-execution-telemetry-and-trace-export.md) | Execution Telemetry and Trace Export | Delivered |
| [20](slices/20-tiered-model-and-api-key-routing.md) | Tiered Model and API Key Routing | Delivered |
| [21](slices/21-framework-boundary-reconciliation.md) | Framework Boundary Reconciliation | Delivered |
| [22](slices/22-system-pack-activation-gate.md) | System Pack Approval / Activation Gate | Delivered |
| [23](slices/23-evidence-harvest-and-teardown.md) | Evidence Harvest and Teardown | Delivered |
| [24](slices/24-system-led-evidence-commit-and-teardown-confirmation.md) | System-Led Evidence Commit and Teardown Confirmation | Delivered |
| [25](slices/25-b2b-workstream-boundary-and-task-graph.md) | B2B Workstream Boundary and Global Task Graph | Planned |
| [26](slices/26-tenant-site-actor-memory-contracts.md) | Tenant/Site/Actor Memory Contracts | Planned |
| [27](slices/27-institutional-vector-memory-layer.md) | Institutional Vector Memory Layer | Planned |
| [28](slices/28-semantic-thread-routing-and-forking.md) | Semantic Thread Routing and Context Forking | Planned |
| [29](slices/29-decision-precedent-confidence-and-escalation.md) | Decision Precedent, Confidence, and Escalation | Planned |
| [30](slices/30-erpnext-adapter-foundation-and-fixtures.md) | ERPNext Adapter Foundation and Deterministic Fixtures | Planned |
| [31](slices/31-business-ops-pack-bootstrap.md) | Business Ops Pack Bootstrap | Planned |
| [32](slices/32-auto-repair-mvp-and-single-box-deployment.md) | Auto Repair MVP and Single-Box Deployment Topology | Planned |

---

## Alignment Note

Slice 1 preserved the initial follow-up roadmap as the planning record at that
time. This index is the active discoverability surface for the implementation
sequence that actually followed. When the two differ, use this index for current
slice ordering and use Slice 1 for the authoritative framework-boundary
invariants it established.

---

## Roadmap Posture

The repository is being finalised into the reusable base framework. The final
base framework consists of exactly three model packs:

- **System Model Pack** — sole governance/authority/ingress layer
- **Coding Agent Model Pack** — bounded artifact factory
- **Template Model Pack** — reusable approved framework template shapes

Domain packs currently in the repository (education, agriculture, assistant)
are provisional scaffolding used while validating the framework shape. They
will be extracted, moved, or removed in later PRs.

See [`docs/7-concepts/framework-boundary.md`](../7-concepts/framework-boundary.md)
for the authoritative framework boundary contract.

---

## Convention

Each slice document uses the following structure:

```markdown
## Purpose
## Scope
## Out of Scope
## Required Changes
## New/Changed Contracts
## Files Likely Touched
## Acceptance Criteria
## Tests
## Ledger/Governance Impact
## Follow-Up Slices
```
