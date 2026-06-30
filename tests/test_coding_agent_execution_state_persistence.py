from __future__ import annotations

import importlib.util
import pathlib
import sys
import types


BASE = pathlib.Path(__file__).parent.parent / "model-packs" / "coding-agent"
DOMAIN = BASE / "domain-lib"
CONTROLLERS = BASE / "controllers"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_tier3_slice(node_id: str = "A"):
    return {
        "slice_id": f"{node_id}-slice",
        "node_id": node_id,
        "task_description": "Write README docs",
        "allowed_tools": [],
        "tier": 3,
        "model_class": "slm",
        "depends_on": [],
        "plan": {
            "plan_id": "plan-1",
            "nodes": [
                {"node_id": node_id, "description": "Write README docs", "depends_on": [], "tier_hint": 3},
            ],
            "created_at": "now",
        },
    }


def test_execution_state_store_round_trip_and_retention():
    store_mod = _load("coding_agent_execution_state_store_slice16", DOMAIN / "execution_state_store.py")

    store = store_mod.ExecutionStateStore(retention_limit=2)
    store.save_checkpoint("plan-1", {"retry_counts": {"A": 0}}, source="first")
    store.save_checkpoint("plan-1", {"retry_counts": {"A": 1}}, source="second")
    store.save_checkpoint("plan-1", {"retry_counts": {"A": 2}}, source="third")

    checkpoints = store.list_checkpoints("plan-1")
    assert len(checkpoints) == 2
    assert checkpoints[-1].execution_context["retry_counts"] == {"A": 2}

    restored = store_mod.ExecutionStateStore.from_dict(store.to_dict())
    latest = restored.load_latest_checkpoint("plan-1")
    assert latest is not None
    assert latest.execution_context["retry_counts"] == {"A": 2}


def test_runtime_tier3_checkpoint_persists_and_recovers(monkeypatch):
    runtime = _load("coding_agent_runtime_slice16", CONTROLLERS / "runtime_adapters.py")

    attempts = {"count": 0}
    slm_mod = types.SimpleNamespace()
    slm_mod.slm_available = lambda: True

    def _flaky_call(system, user, model=None, max_tokens=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("temporary timeout")
        return "SLM_OK"

    slm_mod.call_slm = _flaky_call

    lumina = types.ModuleType("lumina")
    core = types.ModuleType("lumina.core")
    system_log = types.ModuleType("lumina.system_log")
    event_payload = types.ModuleType("lumina.system_log.event_payload")
    log_bus = types.ModuleType("lumina.system_log.log_bus")

    class _LogLevel:
        AUDIT = "AUDIT"

    def _create_event(**kwargs):
        return kwargs

    def _emit(event):
        return None

    event_payload.LogLevel = _LogLevel
    event_payload.create_event = _create_event
    log_bus.emit = _emit

    core.slm = slm_mod
    lumina.core = core
    lumina.system_log = system_log

    monkeypatch.setitem(sys.modules, "lumina", lumina)
    monkeypatch.setitem(sys.modules, "lumina.core", core)
    monkeypatch.setitem(sys.modules, "lumina.core.slm", slm_mod)
    monkeypatch.setitem(sys.modules, "lumina.system_log", system_log)
    monkeypatch.setitem(sys.modules, "lumina.system_log.event_payload", event_payload)
    monkeypatch.setitem(sys.modules, "lumina.system_log.log_bus", log_bus)

    task_spec = {"task_id": "job-16"}

    state = {"turn_count": 0}
    evidence = {
        "job_scope_valid": True,
        "micro_context": {"execution_tier": 3, "scope_valid": True},
        "task_slice": _make_tier3_slice("A"),
    }

    state_after_first, first = runtime.domain_step(state, task_spec, evidence, {})

    first_dispatch = first.get("dispatch_result")
    assert first.get("action") == "dispatched"
    assert first_dispatch and first_dispatch.get("reason") == "retry_scheduled"
    assert "execution_state_store" in state_after_first

    store_payload = state_after_first["execution_state_store"]
    checkpoints = list(store_payload.get("checkpoints") or [])
    assert checkpoints
    assert checkpoints[-1]["execution_context"]["retry_counts"]["A"] == 1

    state_after_second, second = runtime.domain_step(state_after_first, task_spec, evidence, {})

    second_dispatch = second.get("dispatch_result")
    assert second.get("action") == "dispatched"
    assert second_dispatch and second_dispatch.get("dispatched") is True
    assert second_dispatch.get("tier3_evidence", {}).get("status") == "success"

    store_payload_second = state_after_second["execution_state_store"]
    checkpoints_second = list(store_payload_second.get("checkpoints") or [])
    assert len(checkpoints_second) >= 2
    latest_context = checkpoints_second[-1]["execution_context"]
    assert "A" in latest_context.get("completed_node_ids", [])
    assert latest_context.get("retry_counts", {}).get("A") is None
