from pathlib import Path
import importlib.util

BASE = Path(__file__).resolve().parents[1] / "model-packs" / "coding-agent" / "controllers"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_runtime_calls_tier2_decompose_via_dispatcher():
    rt = _load("runtime_adapters", BASE / ".." / "controllers" / ".." / "controllers" / "runtime_adapters.py")
    # craft evidence requesting tier 2 with a job payload and scope_valid True
    job = {
        "job_id": "job-123",
        "summary": "Run code tests",
        "task_graph": [
            {"task_id": "A", "task_type": "read", "tier": 3, "allowed_tools": ["adapter/ca/read-file/v1"], "blocked_by": []},
        ],
    }

    evidence = {"micro_context": {"execution_tier": 2, "scope_valid": True}, "job": job}
    state = {"turn_count": 0}
    task_spec = {"task_id": "ts-1"}

    new_state, result = rt.domain_step(state, task_spec, evidence, {})

    assert isinstance(result, dict)
    assert result.get("action") == "decompose_job"
    dr = result.get("dispatch_result")
    assert dr and dr.get("tier") == 2
    assert dr.get("dispatched") is True
    assert "plan" in dr and "task_slices" in dr


def test_dispatcher_handles_direct_tier2_call():
    td = _load("tier_dispatcher", BASE / "tier_dispatcher.py")
    job = {"job_id": "j9", "summary": "smoke", "task_graph": []}
    res = td.dispatch_to_tier(2, job)
    assert res.get("tier") == 2
    assert res.get("dispatched") is True
    assert "plan" in res


def test_dispatch_to_tier_2_from_runtime():
    runtime = _load("runtime_adapters", BASE / ".." / "controllers" / "runtime_adapters.py")
    evidence = {"micro_context": {"execution_tier": 2, "scope_valid": True}, "job": {"job_id": "j-test", "summary": "run tests", "task_graph": [{"task_id": "A", "task_type": "tests", "allowed_tools": ["adapter/ca/run-tests/v1"], "blocked_by": []}]}}
    state = {"turn_count": 0}
    task_spec = {"task_id": "synth"}
    new_state, out = runtime.domain_step(state, task_spec, evidence, {})
    assert isinstance(out, dict)
    assert out.get("action") == "decompose_job"
    dr = out.get("dispatch_result")
    assert dr and dr.get("tier") == 2 and dr.get("dispatched") is True
    assert "plan" in dr and "task_slices" in dr


def test_dispatch_task_slice_to_tier_3():
    td = _load("tier_dispatcher", BASE / "tier_dispatcher.py")
    ts = {"slice_id": "s1", "node_id": "A", "task_description": "run tests", "allowed_tools": ["adapter/ca/run-tests/v1"], "context_budget_tokens": 512, "tier": 3}
    result = td.dispatch_to_tier(3, ts)
    assert result.get("tier") == 3
    assert result.get("dispatched") is True
    assert "scratchpad" in result
