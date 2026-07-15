"""Additional coverage tests for lumina.orchestrator.system_log_writer.

Covers SystemLogWriter hash utilities, write_commitment_record,
write_trace_event, write_escalation_record (including domain_physics
escalation trigger lookup), and append_provenance_trace.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina.orchestrator.system_log_writer import (
    SystemLogWriter,
    canonical_json,
    hash_payload,
    hash_record,
)


# ── Module-level hash utilities ───────────────────────────────────────────────


@pytest.mark.unit
def test_canonical_json_is_deterministic() -> None:
    rec = {"b": 2, "a": 1}
    assert canonical_json(rec) == canonical_json({"a": 1, "b": 2})


@pytest.mark.unit
def test_hash_record_returns_hex() -> None:
    h = hash_record({"record_type": "test"})
    assert isinstance(h, str) and len(h) == 64


@pytest.mark.unit
def test_hash_payload_matches_hash_record() -> None:
    payload = {"x": 1}
    assert hash_payload(payload) == hash_record(payload)


# ── SystemLogWriter — callback-based construction ─────────────────────────────


def _make_writer(tmp_path: Path, callback=None, profile: dict[str, str] | None = None) -> SystemLogWriter:
    return SystemLogWriter(
        ledger_path=tmp_path / "ledger.jsonl",
        session_id="sess-001",
        profile=profile
        or {
            "subject_id": "student-a",
            "organization_id": "org-default",
            "site_id": "site-default",
        },
        system_physics_hash="abc123",
        log_append_callback=callback,
    )


# ── log_records property ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_log_records_initially_empty(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    assert writer.log_records == []


# ── write_commitment_record ───────────────────────────────────────────────────


@pytest.mark.unit
def test_write_commitment_record_uses_callback(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    domain = {"id": "education", "version": "1.0"}
    policy_commitment = {
        "subject_id": "education",
        "subject_version": "1.0",
        "subject_hash": "hashval",
    }
    writer.write_commitment_record(domain, policy_commitment)
    assert len(appended) == 1
    assert appended[0]["record_type"] == "CommitmentRecord"
    assert appended[0]["subject_id"] == "education"


@pytest.mark.unit
def test_write_commitment_record_writes_file(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    domain = {"id": "education", "version": "1.0",
               "domain_authority": {"pseudonymous_id": "da-001"}}
    policy_commitment = {"subject_id": "education", "subject_version": "1.0",
                         "subject_hash": "hashval"}
    writer.write_commitment_record(domain, policy_commitment)
    ledger = tmp_path / "ledger.jsonl"
    assert ledger.exists()
    records = [json.loads(line) for line in ledger.read_text().strip().split("\n")]
    assert records[0]["record_type"] == "CommitmentRecord"


@pytest.mark.unit
def test_write_commitment_record_includes_scope_fields_from_profile(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(
        tmp_path,
        callback=lambda sid, rec: appended.append(rec),
        profile={
            "subject_id": "student-a",
            "organization_id": "org-001",
            "site_id": "site-nyc",
            "device_id": "device-kiosk-7",
        },
    )
    domain = {"id": "education", "version": "1.0"}
    policy_commitment = {
        "subject_id": "education",
        "subject_version": "1.0",
        "subject_hash": "hashval",
    }
    writer.write_commitment_record(domain, policy_commitment)
    rec = appended[0]
    assert rec["organization_id"] == "org-001"
    assert rec["site_id"] == "site-nyc"
    assert rec["device_id"] == "device-kiosk-7"


@pytest.mark.unit
def test_write_commitment_record_requires_organization_and_site(tmp_path: Path) -> None:
    writer = _make_writer(
        tmp_path,
        profile={
            "subject_id": "student-a",
            "organization_id": "org-001",
        },
    )
    with pytest.raises(ValueError, match="CommitmentRecord requires scope fields"):
        writer.write_commitment_record(
            {"id": "education", "version": "1.0"},
            {
                "subject_id": "education",
                "subject_version": "1.0",
                "subject_hash": "hashval",
            },
        )


@pytest.mark.unit
def test_write_commitment_record_rejects_placeholder_scope_and_invalid_device(tmp_path: Path) -> None:
    writer = _make_writer(
        tmp_path,
        profile={
            "subject_id": "student-a",
            "organization_id": "<ORGANIZATION_ID>",
            "site_id": "site-nyc",
            "device_id": "   ",
        },
    )
    with pytest.raises(ValueError, match="CommitmentRecord requires scope fields"):
        writer.write_commitment_record(
            {"id": "education", "version": "1.0"},
            {
                "subject_id": "education",
                "subject_version": "1.0",
                "subject_hash": "hashval",
            },
        )

    writer = _make_writer(
        tmp_path,
        profile={
            "subject_id": "student-a",
            "organization_id": "org-001",
            "site_id": "site-nyc",
            "device_id": 42,
        },
    )
    appended = []
    writer._log_append_callback = lambda sid, rec: appended.append(rec)
    writer.write_commitment_record(
        {"id": "education", "version": "1.0"},
        {"subject_id": "education", "subject_version": "1.0", "subject_hash": "hashval"},
    )
    assert "device_id" not in appended[0]


# ── write_trace_event ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_write_trace_event_appends_record(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    writer.write_trace_event(
        task_spec={"task_id": "t1"},
        invariant_results=[{"id": "inv-1", "passed": True}],
        domain_lib_decision={"tier": "green"},
        action="proceed",
        prompt_contract={"prompt_type": "default"},
        provenance_metadata={"source": "test"},
        last_standing_order_id=None,
        last_standing_order_attempt=None,
    )
    assert len(appended) == 1
    assert appended[0]["record_type"] == "TraceEvent"
    assert appended[0]["decision"] == "proceed"


@pytest.mark.unit
def test_write_trace_event_includes_novel_synthesis_signal(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    writer.write_trace_event(
        task_spec={"task_id": "t1"},
        invariant_results=[{"id": "inv-1", "passed": False, "signal_type": "novel_cross_domain"}],
        domain_lib_decision={},
        action="flag",
        prompt_contract={},
        provenance_metadata=None,
        last_standing_order_id=None,
        last_standing_order_attempt=None,
    )
    assert appended[0]["metadata"]["novel_synthesis_signal"] == "novel_cross_domain"


# ── write_escalation_record — domain_physics trigger lookup ───────────────────


@pytest.mark.unit
def test_write_escalation_record_default_target_role(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    writer.write_escalation_record(
        task_spec={"task_id": "t1"},
        domain_lib_decision={"tier": "red"},
        trigger="frustration_repeated",
        provenance_metadata=None,
    )
    assert appended[0]["target_role"] == "teacher"
    assert appended[0]["sla_minutes"] == 30


@pytest.mark.unit
def test_write_escalation_record_trigger_lookup_from_physics(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    domain_physics = {
        "id": "education",
        "version": "1.0",
        "auto_freeze_on_escalation": False,
        "escalation_triggers": [
            {"id": "off_topic", "target_role": "admin", "sla_minutes": 60},
            {"id": "frustration_repeated", "target_role": "teacher", "sla_minutes": 15},
        ],
    }
    writer.write_escalation_record(
        task_spec={"task_id": "t2"},
        domain_lib_decision={"tier": "yellow"},
        trigger="off_topic",
        provenance_metadata={"turn": 3},
        domain_physics=domain_physics,
    )
    record = appended[0]
    assert record["target_role"] == "admin"
    assert record["sla_minutes"] == 60


@pytest.mark.unit
def test_write_escalation_record_unmatched_trigger_uses_defaults(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    domain_physics = {
        "auto_freeze_on_escalation": False,
        "escalation_triggers": [
            {"id": "other_trigger", "target_role": "admin", "sla_minutes": 60},
        ],
    }
    writer.write_escalation_record(
        task_spec={},
        domain_lib_decision={},
        trigger="unknown_trigger",
        provenance_metadata=None,
        domain_physics=domain_physics,
    )
    assert appended[0]["target_role"] == "teacher"  # default
    assert appended[0]["sla_minutes"] == 30  # default


@pytest.mark.unit
def test_write_escalation_record_system_physics_hash_in_metadata(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    writer.write_escalation_record(
        task_spec={},
        domain_lib_decision={},
        trigger="t",
        provenance_metadata=None,
        domain_physics={"auto_freeze_on_escalation": False},
    )
    assert appended[0]["metadata"].get("system_physics_hash") == "abc123"


@pytest.mark.unit
def test_write_escalation_record_includes_scope_fields_from_profile(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(
        tmp_path,
        callback=lambda sid, rec: appended.append(rec),
        profile={
            "subject_id": "student-a",
            "organization_id": "org-001",
            "site_id": "site-phx",
            "device_id": "device-frontdesk-2",
        },
    )
    writer.write_escalation_record(
        task_spec={},
        domain_lib_decision={},
        trigger="t",
        provenance_metadata=None,
        domain_physics={"auto_freeze_on_escalation": False},
    )
    rec = appended[0]
    assert rec["organization_id"] == "org-001"
    assert rec["site_id"] == "site-phx"
    assert rec["device_id"] == "device-frontdesk-2"


@pytest.mark.unit
def test_write_escalation_record_requires_organization_and_site(tmp_path: Path) -> None:
    writer = _make_writer(
        tmp_path,
        profile={
            "subject_id": "student-a",
            "site_id": "site-phx",
        },
    )
    with pytest.raises(ValueError, match="EscalationRecord requires scope fields"):
        writer.write_escalation_record(
            task_spec={},
            domain_lib_decision={},
            trigger="t",
            provenance_metadata=None,
            domain_physics={"auto_freeze_on_escalation": False},
        )


# ── append_provenance_trace ────────────────────────────────────────────────────


@pytest.mark.unit
def test_append_provenance_trace(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    writer.append_provenance_trace(
        task_id="task-1",
        action="continue",
        prompt_type="standard",
        metadata={"provider": "openai"},
    )
    record = appended[0]
    assert record["record_type"] == "TraceEvent"
    assert record["event_type"] == "other"
    assert record["task_id"] == "task-1"
    assert record["metadata"]["provider"] == "openai"


# ── hash chain advances ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_hash_chain_advances_with_each_record(tmp_path: Path) -> None:
    appended = []
    writer = _make_writer(tmp_path, callback=lambda sid, rec: appended.append(rec))
    domain = {"id": "education", "version": "1.0"}
    policy = {"subject_id": "education", "subject_version": "1.0", "subject_hash": "h"}
    writer.write_commitment_record(domain, policy)
    writer.append_provenance_trace("t1", "a", "default", {})

    assert len(appended) == 2
    first_hash = hash_record(appended[0])
    assert appended[1]["prev_record_hash"] == first_hash
