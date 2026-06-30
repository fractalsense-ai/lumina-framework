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


tier_contracts = _load("coding_agent_tier_contracts_slice15", DOMAIN / "tier_contracts.py")
tier3_ready_scheduler = _load("coding_agent_tier3_ready_scheduler_slice15", DOMAIN / "tier3_ready_scheduler.py")
retry_policy = _load("coding_agent_retry_policy_slice15", DOMAIN / "retry_policy.py")
tier_dispatcher = _load("coding_agent_tier_dispatcher_slice15", CONTROLLERS / "tier_dispatcher.py")


def _make_plan():
    dag = tier_contracts.PlanDAG(
        nodes=[
            tier_contracts.PlanNode("A", "prep docs", []),
            tier_contracts.PlanNode("B", "write docs", ["A"]),
        ],
        created_at="now",
    )
    return dag.to_dict()


def _make_slice(node_id: str = "B"):
    return {
        "slice_id": f"{node_id}-slice",
        "node_id": node_id,
        "task_description": "Write README docs",
        "allowed_tools": ["adapter/ca/write-file/v1"],
        "context_budget_tokens": 1024,
        "tier": 3,
        "model_class": "llm",
        "depends_on": ["A"] if node_id == "B" else [],
    }


def test_ready_scheduler_blocks_unmet_dependencies():
    dag = tier_contracts.PlanDAG.from_dict(_make_plan())
    task_slice = tier_contracts.TaskSlice.from_dict(_make_slice("B"))
    ctx = tier_contracts.ExecutionContext.from_dict({"completed_node_ids": []})

    errors = tier3_ready_scheduler.validate_slice_ready(task_slice, dag, ctx)

    assert any(e.startswith("dependency_not_ready:") for e in errors)


def test_dispatcher_blocks_not_ready_slice_when_plan_provided():
    payload = _make_slice("B")
    payload["plan"] = _make_plan()
    payload["execution_context"] = {"completed_node_ids": []}

    out = tier_dispatcher.dispatch_to_tier(3, payload)

    assert out["dispatched"] is False
    assert out["reason"] == "slice_not_ready"
    assert out["tier3_evidence"]["status"] == "blocked"


def test_dispatcher_runs_ready_slm_slice(monkeypatch):
    slm_mod = types.SimpleNamespace()
    slm_mod.slm_available = lambda: True
    slm_mod.call_slm = lambda system, user, model=None, max_tokens=None: "SLM_OK"

    lumina = types.ModuleType("lumina")
    core = types.ModuleType("lumina.core")
    core.slm = slm_mod
    lumina.core = core

    monkeypatch.setitem(sys.modules, "lumina", lumina)
    monkeypatch.setitem(sys.modules, "lumina.core", core)
    monkeypatch.setitem(sys.modules, "lumina.core.slm", slm_mod)

    payload = {
        "slice_id": "A-slice",
        "node_id": "A",
        "task_description": "Write docs",
        "allowed_tools": [],
        "tier": 3,
        "model_class": "slm",
        "depends_on": [],
        "plan": _make_plan(),
        "execution_context": {"completed_node_ids": []},
    }

    out = tier_dispatcher.dispatch_to_tier(3, payload)

    assert out["dispatched"] is True
    assert out["model_class"] == "slm"
    assert out["tier3_evidence"]["status"] == "success"


def test_dispatcher_schedules_retry_for_retryable_failure(monkeypatch):
    slm_mod = types.SimpleNamespace()
    slm_mod.slm_available = lambda: True

    def _raise_timeout(system, user, model=None, max_tokens=None):
        raise TimeoutError("temporary timeout")

    slm_mod.call_slm = _raise_timeout
    lumina = types.ModuleType("lumina")
    core = types.ModuleType("lumina.core")
    core.slm = slm_mod
    lumina.core = core
    monkeypatch.setitem(sys.modules, "lumina", lumina)
    monkeypatch.setitem(sys.modules, "lumina.core", core)
    monkeypatch.setitem(sys.modules, "lumina.core.slm", slm_mod)

    payload = {
        "slice_id": "A-slice",
        "node_id": "A",
        "task_description": "Write docs",
        "allowed_tools": [],
        "tier": 3,
        "model_class": "slm",
        "depends_on": [],
        "plan": _make_plan(),
        "execution_context": {
            "completed_node_ids": [],
            "retry_counts": {"A": 0},
            "max_retries_per_node": 2,
            "base_backoff_seconds": 1.0,
            "max_backoff_seconds": 30.0,
        },
    }

    out = tier_dispatcher.dispatch_to_tier(3, payload)

    assert out["dispatched"] is False
    assert out["reason"] == "retry_scheduled"
    assert out["retryable"] is True
    assert out["retry_after_seconds"] > 0
    assert out["tier3_evidence"]["status"] == "retry_scheduled"


def test_dispatcher_stops_retry_when_budget_exhausted():
    payload = _make_slice("A")
    payload["plan"] = _make_plan()
    payload["execution_context"] = {
        "completed_node_ids": [],
        "retry_counts": {"A": 2},
        "max_retries_per_node": 2,
    }

    out = tier_dispatcher.dispatch_to_tier(3, payload)

    assert out["dispatched"] is False
    assert out["reason"] == "tier3_execution_failed"
    assert out["retryable"] is False
    assert out["tier3_evidence"]["status"] == "failed"


def test_retry_policy_backoff_is_bounded_and_exponential():
    assert retry_policy.classify_failure("temporary timeout") == "transient"
    assert retry_policy.should_retry("transient", attempt_count=0, max_retries=2) is True
    assert retry_policy.should_retry("validation", attempt_count=0, max_retries=2) is False
    assert retry_policy.next_backoff_seconds(0, 1.0, 30.0) == 1.0
    assert retry_policy.next_backoff_seconds(1, 1.0, 30.0) == 2.0
    assert retry_policy.next_backoff_seconds(10, 1.0, 30.0) == 30.0
