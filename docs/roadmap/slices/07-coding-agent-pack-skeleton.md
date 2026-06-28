---
version: 1.0.0
last_updated: 2026-06-28
---

# Slice 7: Coding Agent Pack Skeleton

**Version:** 1.0.0
**Status:** Active
**Last updated:** 2026-06-28
**PR:** Adds the initial `model-packs/coding-agent/` skeleton.

---

## Purpose

Create the first concrete Coding Agent model-pack scaffold while preserving the Slice 5 and Slice 6 authority boundaries. The pack is a bounded artifact factory that can later host coding-agent workflows, but this slice only establishes structure, contracts, and deterministic validation stubs.

---

## Scope

- Add `model-packs/coding-agent/` with manifest, runtime config, UI config, profile defaults, core module physics, adapters, prompts, and domain-library contracts.
- Register the pack in the System Pack domain registry.
- Add focused structural tests for adapter behavior, domain physics schema compliance, registry discoverability, and manifest coverage.
- Keep the skeleton provider-neutral, forge-neutral, and free of live model or deployment calls.

---

## Out of Scope

- Implementing Hermes operational services inside the pack.
- Adding forge credentials, deployment automation, or provider-specific CI/CD routes.
- Changing `src/lumina/` runtime behavior.
- Authorizing work outside the System Pack authority gate.

---

## Acceptance Criteria

- The `coding-agent` pack has the required HMVC files and three runtime adapter callables.
- The core `domain-physics.json` validates against `standards/domain-physics-schema-v1.json`.
- `model-packs/system/cfg/domain-registry.yaml` contains the `coding-agent` domain entry.
- New model-pack YAML files and this roadmap document are tracked in `docs/MANIFEST.yaml` with current hashes.
- Focused pytest coverage passes without live SLM, LLM, network, forge, or credential access.