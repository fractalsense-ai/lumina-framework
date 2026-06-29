---
title: "Slice 14 — DAG-Correct Compute Orchestration"
pack: model-packs/coding-agent/pack.yaml
version: 0.9.0
last_updated: 2026-06-29
sha256: pending
---

Slice 14 makes DAG correctness the efficiency gate for the coding-agent compute tiers.
Terminology is supporting context; the primary goal is that work can be planned,
sliced, and executed without dependency drift or wasted model calls.

## Purpose

The coding-agent stack relies on DAG quality for efficient execution:

- Tier 1 owns the global DAG and system-state references.
- Tier 2 derives dependency-preserving slices and micro-DAG handoffs.
- Tier 3 executes only ready work whose upstream dependencies are satisfied.

## DAG Invariants

1. Node IDs are unique within a DAG.
2. Dependencies point to existing nodes.
3. DAGs are acyclic.
4. Topological ordering is deterministic for equal-ready nodes.
5. Micro-DAG nodes and task slices preserve lineage to global nodes.
6. Task slices preserve dependency context, model class, and tool constraints.
7. Invalid DAGs are rejected before slicing or execution.

## Implementation Scope

- Add a deterministic architect plan contract for Tier 1 global plans.
- Strengthen DAG validation with stable ordering, ready-node calculation, and lineage checks.
- Preserve dependency and parent lineage in generated task slices.
- Wire Tier 1 dispatch to return global plan evidence and reject invalid DAGs.
- Add focused DAG correctness tests for contracts, validation, slicing, and dispatch.

## Acceptance Criteria

- Targeted DAG correctness tests pass.
- Tier 1 dispatch returns global plan evidence with system-state references.
- Tier 2 dispatch rejects invalid DAGs before generating task slices.
- Generated slices preserve dependency context and model routing metadata.
- This document is tracked in `docs/MANIFEST.yaml` and hashes are regenerated with `scripts/manifest-regenerate.ps1`.
