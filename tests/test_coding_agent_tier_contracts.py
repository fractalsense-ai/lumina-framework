from __future__ import annotations

from model_packs.coding_agent.domain_lib import tier_contracts
from model_packs.coding_agent.controllers import tier_dispatcher


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
