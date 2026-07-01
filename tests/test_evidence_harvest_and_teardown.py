from __future__ import annotations

import importlib.util
import pathlib

base = pathlib.Path(__file__).resolve().parents[1]
eh_path = base / "model-packs" / "coding-agent" / "domain-lib" / "evidence_harvest.py"
spec = importlib.util.spec_from_file_location("coding_agent_evidence_harvest", str(eh_path))
evidence_harvest = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = evidence_harvest
spec.loader.exec_module(evidence_harvest)

td_path = base / "model-packs" / "coding-agent" / "domain-lib" / "teardown_coordinator.py"
spec = importlib.util.spec_from_file_location("coding_agent_teardown_coordinator", str(td_path))
teardown_coordinator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = teardown_coordinator
spec.loader.exec_module(teardown_coordinator)


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
