---
version: 1.3.0
last_updated: 2026-05-07
---

# Section 7 — Concepts

**Version:** 1.3.0
**Status:** Active
**Last updated:** 2026-05-07

---

This section is Lumina's architectural rationale layer. It explains *why* scoped context, deterministic turn data, state management, and governed action boundaries exist — not just how individual components are implemented.

## Start here

- [`context-is-not-conversation(7)`](context-is-not-conversation.md) — core thesis: conversation logs are not operational context
- [`ai-governance-principles(7)`](ai-governance-principles.md) — ten governing constraints for well-scoped AI interaction systems
- [`prompt-packet-assembly(7)`](prompt-packet-assembly.md) — runtime pipeline that assembles task-complete context packets
- [`domain-pack-anatomy(7)`](domain-pack-anatomy.md) — model-pack structure and isolation boundaries
- [`edge-vectorization(7)`](edge-vectorization.md) — per-domain retrieval isolation and scoped context delivery

## Reading paths

- **Philosophy + governance path**
  - [`context-is-not-conversation.md`](context-is-not-conversation.md)
  - [`ai-governance-principles.md`](ai-governance-principles.md)
  - [`zero-trust-architecture.md`](zero-trust-architecture.md)

- **Model-pack authoring path**
  - [`domain-pack-anatomy.md`](domain-pack-anatomy.md)
  - [`domain-adapter-pattern.md`](domain-adapter-pattern.md)
  - [`prompt-packet-assembly.md`](prompt-packet-assembly.md)

- **Retrieval + scoped-context path**
  - [`edge-vectorization.md`](edge-vectorization.md)
  - [`rag-contracts.md`](rag-contracts.md)
  - [`slm-compute-distribution.md`](slm-compute-distribution.md)

- **Audit + ledger path**
  - [`state-change-commit-policy.md`](state-change-commit-policy.md)
  - [`ledger-tier-separation.md`](ledger-tier-separation.md)
  - [`command-execution-pipeline.md`](command-execution-pipeline.md)

For a full concepts inventory, browse this directory directly.
