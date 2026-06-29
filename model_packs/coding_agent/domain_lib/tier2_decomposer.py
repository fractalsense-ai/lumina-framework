import importlib.util
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
real_path = repo_root / "model-packs" / "coding-agent" / "domain-lib" / "tier2_decomposer.py"
_spec = importlib.util.spec_from_file_location("dp_coding_agent_tier2_decomposer", str(real_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["dp_coding_agent_tier2_decomposer"] = _mod
_spec.loader.exec_module(_mod)

for _k in dir(_mod):
    if not _k.startswith("__"):
        globals()[_k] = getattr(_mod, _k)
