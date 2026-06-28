# Coding Agent Model Pack

The Coding Agent pack is the initial Slice 7 skeleton for Lumina's bounded artifact factory. It defines the pack manifest, runtime configuration, core domain physics, required runtime adapters, prompt contract, and minimal job-result dataclasses.

This pack is intentionally local and non-operational. It does not call live models, contact forge providers, access credentials, or deploy artifacts. All executable work must enter through the System Pack authority gate.

## Contents

- `pack.yaml` declares the HMVC layer map and entry points.
- `cfg/runtime-config.yaml` binds required adapters and the core module.
- `modules/core/domain-physics.json` defines authority-boundary invariants.
- `controllers/runtime_adapters.py` provides deterministic adapter stubs.
- `domain-lib/job_contracts.py` documents the System Pack handoff shape.

## Validation

Run the focused Slice 7 checks with:

```powershell
pytest tests/test_coding_agent_pack.py tests/test_domain_pack_structure.py -q
```