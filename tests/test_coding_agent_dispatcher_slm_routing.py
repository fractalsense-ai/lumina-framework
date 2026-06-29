import importlib.util
import pathlib
import sys
import types

# Load the tier_dispatcher module via file-based import to avoid package issues
base = pathlib.Path(__file__).parent.parent / "model-packs" / "coding-agent" / "controllers"
spec = importlib.util.spec_from_file_location("coding_agent_tier_dispatcher", str(base / "tier_dispatcher.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["coding_agent_tier_dispatcher"] = mod
spec.loader.exec_module(mod)

dispatcher = mod


def _make_task_slice(model_class: str):
    return {
        "slice_id": "s1",
        "node_id": "doc-1",
        "task_description": "Write README docs",
        "allowed_tools": [],
        "context_budget_tokens": 1024,
        "tier": 3,
        "model_class": model_class,
    }


def test_slm_routing_when_available(monkeypatch):
    # create fake lumina.core.slm
    slm_mod = types.SimpleNamespace()
    slm_mod.slm_available = lambda: True
    slm_mod.call_slm = lambda system, user, model=None, max_tokens=None: "SLM_OK"

    lumina = types.ModuleType("lumina")
    core = types.ModuleType("lumina.core")
    core.slm = slm_mod
    lumina.core = core

    # Use monkeypatch so fake modules are reverted after this test.
    monkeypatch.setitem(sys.modules, "lumina", lumina)
    monkeypatch.setitem(sys.modules, "lumina.core", core)
    monkeypatch.setitem(sys.modules, "lumina.core.slm", slm_mod)

    res = dispatcher.dispatch_to_tier(3, _make_task_slice("slm"))
    assert res.get("dispatched") is True
    assert res.get("model_class") == "slm"
    assert res.get("slm_output") == "SLM_OK"


def test_slm_fallback_when_unavailable(monkeypatch):
    # Inject a fake SLM that reports unavailable, so dispatcher falls through
    # without polluting module state for other tests.
    slm_mod = types.SimpleNamespace()
    slm_mod.slm_available = lambda: False

    lumina = types.ModuleType("lumina")
    core = types.ModuleType("lumina.core")
    core.slm = slm_mod
    lumina.core = core

    monkeypatch.setitem(sys.modules, "lumina", lumina)
    monkeypatch.setitem(sys.modules, "lumina.core", core)
    monkeypatch.setitem(sys.modules, "lumina.core.slm", slm_mod)

    res = dispatcher.dispatch_to_tier(3, _make_task_slice("slm"))
    # When SLM is not available, dispatcher should fallthrough and not return slm_output
    assert "slm_output" not in res
    assert res.get("dispatched") is False
