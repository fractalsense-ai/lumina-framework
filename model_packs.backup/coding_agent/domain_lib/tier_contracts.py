import importlib.util
import sys
from pathlib import Path

# Shim loader: re-export the real module at model-packs/coding-agent/domain-lib/tier_contracts.py
repo_root = Path(__file__).resolve().parents[3]
real_path = repo_root / "model-packs" / "coding-agent" / "domain-lib" / "tier_contracts.py"
_spec = importlib.util.spec_from_file_location("dp_coding_agent_tier_contracts", str(real_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["dp_coding_agent_tier_contracts"] = _mod
_spec.loader.exec_module(_mod)

# copy public attrs into this shim module
for _k in dir(_mod):
    if not _k.startswith("__"):
        globals()[_k] = getattr(_mod, _k)
