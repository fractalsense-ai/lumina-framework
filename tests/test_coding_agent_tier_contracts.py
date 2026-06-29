from __future__ import annotations

import importlib.util
import sys
import pathlib


ROOT = pathlib.Path(__file__).parent.parent


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Support two execution contexts: when the repo is installed as a package
# tests can import `model_packs...`; in CI or local dev the test may load
# modules directly from files. Try package import first, then fallback.
try:
    from model_packs.coding_agent.domain_lib import tier_contracts as tier_contracts
    from model_packs.coding_agent.controllers import tier_dispatcher as tier_dispatcher
except Exception:
    tc = load_module(str(ROOT / "model-packs" / "coding-agent" / "domain-lib" / "tier_contracts.py"), "tc")
    td = load_module(str(ROOT / "model-packs" / "coding-agent" / "controllers" / "tier_dispatcher.py"), "td")
    tier_contracts = tc
    tier_dispatcher = td


def test_task_slice_from_dict_and_to_dict():
    data = {
        "slice_id": "s1",
        "node_id": "n1",
        "task_description": "read README",
        "allowed_tools": ["adapter/ca/read-file/v1"],
        "context_budget_tokens": 512,
        "tier": 3,
    }
    ts = tier_contracts.TaskSlice.from_dict(data)
    assert ts.slice_id == "s1"
    d = ts.to_dict()
    assert d["node_id"] == "n1"


def test_dispatch_to_tier_3_runs_allowed_tools():
    task_slice = {
        "slice_id": "s2",
        "node_id": "n2",
        "task_description": "tests",
        "allowed_tools": ["adapter/ca/run-tests/v1"],
        "tier": 3,
    }

    result = tier_dispatcher.dispatch_to_tier(3, task_slice)
    assert result.get("tier") == 3
    assert result.get("dispatched") is True
    assert "allowed_tools" in result and "adapter/ca/run-tests/v1" in result["allowed_tools"]
    # scratchpad should be present and contain steps
    sp = result.get("scratchpad")
    assert sp and isinstance(sp.get("steps"), list)


def test_execution_context_round_trip():
    ctx = tier_contracts.ExecutionContext(
        completed_node_ids=["A"],
        failed_node_ids=["B"],
        retry_counts={"C": 1},
        max_retries_per_node=3,
        base_backoff_seconds=2.0,
        max_backoff_seconds=40.0,
    )

    restored = tier_contracts.ExecutionContext.from_dict(ctx.to_dict())

    assert restored.completed_node_ids == ["A"]
    assert restored.failed_node_ids == ["B"]
    assert restored.retry_counts == {"C": 1}
    assert restored.max_retries_per_node == 3
    assert restored.base_backoff_seconds == 2.0
    assert restored.max_backoff_seconds == 40.0
