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


tier_contracts = _load("coding_agent_tier_contracts_slice17", DOMAIN / "tier_contracts.py")
turn_budget = _load("coding_agent_turn_budget_slice17", DOMAIN / "turn_budget.py")
orchestration_loop = _load("coding_agent_orchestration_loop_slice17", CONTROLLERS / "orchestration_loop.py")
runtime = _load("coding_agent_runtime_slice17", CONTROLLERS / "runtime_adapters.py")


def _install_lumina_slm(monkeypatch, call_slm):
    slm_mod = types.SimpleNamespace()
    slm_mod.slm_available = lambda: True
    slm_mod.call_slm = call_slm

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


def _plan_dict(nodes):
    return {
        "plan_id": "plan-17",
        "nodes": [
            {
                "node_id": node_id,
                "description": description,
                "depends_on": list(depends_on),
                "tier_hint": 3,
            }
            for node_id, description, depends_on in nodes
        ],
        "created_at": "now",
    }


def _slice(node_id: str, depends_on=None):
    return {
        "slice_id": f"{node_id}-slice",
        "node_id": node_id,
        "task_description": f"Execute node {node_id}",
        "allowed_tools": [],
        "tier": 3,
        "model_class": "slm",
        "depends_on": list(depends_on or []),
    }


def test_orchestration_loop_executes_deterministic_diamond(monkeypatch):
    _install_lumina_slm(monkeypatch, lambda system, user, model=None, max_tokens=None: "SLM_OK")

    plan = _plan_dict(
        [
            ("A", "root", []),
            ("B", "left", ["A"]),
            ("C", "right", ["A"]),
            ("D", "join", ["B", "C"]),
        ]
    )
    slices = [_slice("A"), _slice("B", ["A"]), _slice("C", ["A"]), _slice("D", ["B", "C"])]
    budget = turn_budget.TurnBudget(max_slices_per_turn=10)

    result = orchestration_loop.execute_dag_until(plan, {}, slices, budget)

    assert result.halt_reason == "all_completed"
    assert result.executed_slice_ids == ["A-slice", "B-slice", "C-slice", "D-slice"]
    assert result.completed_node_ids == ["A", "B", "C", "D"]


def test_orchestration_loop_halts_on_permanent_failure(monkeypatch):
    def _fail_validation(system, user, model=None, max_tokens=None):
        raise ValueError("validation error")

    _install_lumina_slm(monkeypatch, _fail_validation)

    plan = _plan_dict([("A", "root", [])])
    budget = turn_budget.TurnBudget(max_slices_per_turn=5)

    result = orchestration_loop.execute_dag_until(plan, {}, [_slice("A")], budget)

    assert result.halt_reason == "permanent_failure"
    assert result.failed_node_id == "A"
    assert result.executed_slice_ids == ["A-slice"]


def test_orchestration_loop_halts_on_retry_scheduled(monkeypatch):
    def _timeout_once(system, user, model=None, max_tokens=None):
        raise TimeoutError("temporary timeout")

    _install_lumina_slm(monkeypatch, _timeout_once)

    plan = _plan_dict([("A", "root", []), ("B", "next", ["A"])])
    slices = [_slice("A"), _slice("B", ["A"])]
    budget = turn_budget.TurnBudget(max_slices_per_turn=5)

    result = orchestration_loop.execute_dag_until(plan, {}, slices, budget)

    assert result.halt_reason == "retry_scheduled"
    assert result.executed_slice_ids == ["A-slice"]
    assert result.completed_node_ids == []


def test_orchestration_loop_respects_slice_budget(monkeypatch):
    _install_lumina_slm(monkeypatch, lambda system, user, model=None, max_tokens=None: "SLM_OK")

    plan = _plan_dict([("A", "root", []), ("B", "next", ["A"])])
    slices = [_slice("A"), _slice("B", ["A"])]
    budget = turn_budget.TurnBudget(max_slices_per_turn=1)

    result = orchestration_loop.execute_dag_until(plan, {}, slices, budget)

    assert result.halt_reason == "budget_exhausted"
    assert result.executed_slice_ids == ["A-slice"]
    assert result.completed_node_ids == ["A"]


def test_runtime_domain_step_orchestrates_and_resumes(monkeypatch):
    _install_lumina_slm(monkeypatch, lambda system, user, model=None, max_tokens=None: "SLM_OK")

    plan = _plan_dict([("A", "root", []), ("B", "next", ["A"])])
    slices = [_slice("A"), _slice("B", ["A"])]

    evidence = {
        "job_scope_valid": True,
        "use_orchestration_loop": True,
        "plan": plan,
        "task_slices": slices,
    }
    params = {"max_slices_per_turn": 1}

    state_1, out_1 = runtime.domain_step({"turn_count": 0}, {"task_id": "plan-17"}, evidence, params)

    assert out_1.get("action") == "orchestrated"
    first_result = out_1.get("dispatch_result") or {}
    assert first_result.get("executed_slice_ids") == ["A-slice"]
    assert first_result.get("halt_reason") == "budget_exhausted"
    assert "execution_state_store" in state_1

    state_2, out_2 = runtime.domain_step(state_1, {"task_id": "plan-17"}, evidence, params)

    assert out_2.get("action") == "orchestrated"
    second_result = out_2.get("dispatch_result") or {}
    assert second_result.get("executed_slice_ids") == ["B-slice"]
    assert second_result.get("halt_reason") == "all_completed"
