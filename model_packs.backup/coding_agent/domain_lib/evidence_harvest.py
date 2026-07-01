"""Compatibility shim — load canonical implementation from model-packs.

This file is a small shim so `import model_packs.coding_agent.domain_lib.*`
works in test runs while the authoritative implementation lives under
`model-packs/coding-agent/domain-lib/` (the repository canonical layout).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3]
_CANONICAL = _REPO_ROOT / "model-packs" / "coding-agent" / "domain-lib" / "evidence_harvest.py"

spec = importlib.util.spec_from_file_location("coding_agent_evidence_harvest", str(_CANONICAL))
module = importlib.util.module_from_spec(spec)
sys.modules[__name__] = module
spec.loader.exec_module(module)
