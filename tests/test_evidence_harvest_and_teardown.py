from __future__ import annotations

from model_packs.coding_agent.domain_lib import evidence_harvest, teardown_coordinator


def test_build_evidence_from_orchestration_minimal():
    slice_result = {
        "slice_id": "slice-1",
        "node_id": "node-1",
        "artifacts": [{"path": "out.txt", "sha256": "abc"}],
        "tests": {"passed": True, "summary": "ok"},
        "checksums": {"out.txt": "abc"},
    }
    packet = evidence_harvest.build_evidence_from_orchestration("plan-123", slice_result)
    assert packet.plan_id == "plan-123"
    assert packet.slice_id == "slice-1"
    assert packet.node_id == "node-1"
    d = packet.to_dict()
    assert d["artifacts"][0]["path"] == "out.txt"


def test_execute_teardown_simulated():
    ctx = {"slice_id": "slice-1", "temp_paths": ["/tmp/x", "/tmp/y"]}
    res = teardown_coordinator.execute_teardown("plan-123", ctx)
    assert "/tmp/x" in res.removed
    assert res.failed == []
