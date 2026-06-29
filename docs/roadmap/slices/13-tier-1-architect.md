---
title: "Slice 13 — Tier-1 Architect & SLM Routing"
pack: model-packs/coding-agent/pack.yaml
version: 0.8.0
last_updated: 2026-06-29
sha256: pending
---

This slice implements the Tier-1 Architect which classifies plan nodes by action type
(e.g., `document` vs `code`) and routes documentation-style tasks to the lumina SLM.

Implementation details and tests live in `model-packs/coding-agent/domain-lib/tier1_architect.py`.
