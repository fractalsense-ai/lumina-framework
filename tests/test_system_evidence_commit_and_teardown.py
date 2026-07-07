from __future__ import annotations

import importlib.util
import pathlib
import sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = pathlib.Path(__file__).resolve().parents[1]
CONTROLLERS = BASE / "model-packs" / "system" / "controllers"

evidence_commit_teardown = _load_module(
    "system_evidence_commit_teardown_slice24",
    CONTROLLERS / "evidence_commit_teardown.py",
)
system_log_validator = _load_module(
    "system_log_validator_slice24",
    CONTROLLERS / "system_log_validator.py",
)


def _payload(*, failed: list[dict[str, str]] | None = None) -> dict:
    return {
        "actor_id": "system-pack",
        "actor_role": "system",
        "evidence_commit": {
            "plan_id": "plan-24",
            "slice_id": "slice-24",
            "node_id": "node-24",
            "artifacts": [{"path": "tmp/out.txt", "sha256": "abc"}],
            "test_summary": {"passed": True, "summary": "ok"},
            "checksums": {"tmp/out.txt": "abc"},
            "collected_at": "2026-07-07T00:00:00Z",
        },
        "teardown_result": {
            "plan_id": "plan-24",
            "slice_id": "slice-24",
            "removed": ["tmp/build"],
            "failed": list(failed or []),
            "started_at": "2026-07-07T00:01:00Z",
            "completed_at": "2026-07-07T00:02:00Z",
        },
    }


def test_commit_and_confirm_teardown_success(tmp_path):
    ledger = tmp_path / "system-log-ledger.jsonl"
    payload = _payload()
    payload["ledger_path"] = str(ledger)

    result = evidence_commit_teardown.commit_evidence_and_confirm_teardown(payload)

    assert result["status"] == "ok"
    assert result["transaction"]["state"] == "FINALIZED"
    assert result["lifecycle"] == ["EvidenceCommitted", "TearingDown", "TeardownConfirmed"]

    records = system_log_validator.load_ledger(ledger)
    assert len(records) == 2
    assert records[0]["commitment_type"] == "evidence_commit"
    assert records[1]["commitment_type"] == "teardown_confirmation"


def test_commit_and_confirm_teardown_escalates_on_failure(tmp_path):
    ledger = tmp_path / "system-log-ledger.jsonl"
    payload = _payload(failed=[{"path": "tmp/build", "error": "permission denied"}])
    payload["ledger_path"] = str(ledger)

    result = evidence_commit_teardown.commit_evidence_and_confirm_teardown(payload)

    assert result["status"] == "escalated"
    assert result["transaction"]["state"] == "FINALIZED"
    assert result["lifecycle"][-2:] == ["TeardownFailed", "CleanupEscalated"]

    records = system_log_validator.load_ledger(ledger)
    assert len(records) == 2
    assert records[0]["commitment_type"] == "evidence_commit"
    assert records[1]["commitment_type"] == "cleanup_escalated"


def test_commit_and_confirm_teardown_is_idempotent_for_finalized(tmp_path):
    ledger = tmp_path / "system-log-ledger.jsonl"
    payload = _payload()
    payload["ledger_path"] = str(ledger)

    first = evidence_commit_teardown.commit_evidence_and_confirm_teardown(payload)
    second = evidence_commit_teardown.commit_evidence_and_confirm_teardown(
        {
            **payload,
            "transaction": first["transaction"],
        }
    )

    assert first["status"] == "ok"
    assert second["status"] == "already_finalized"

    records = system_log_validator.load_ledger(ledger)
    assert len(records) == 2


def test_commit_and_confirm_teardown_rejects_invalid_payload():
    result = evidence_commit_teardown.commit_evidence_and_confirm_teardown({})
    assert result["status"] == "error"
    assert "evidence_commit" in result["error"]
