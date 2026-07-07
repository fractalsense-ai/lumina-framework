from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina.core.state_machine import StateTransaction, TransactionState
from lumina.system_log.admin_operations import build_commitment_record

try:
    from . import state_transaction_adapter
    from . import system_log_validator
except Exception:
    import importlib.util
    import sys

    _base = Path(__file__).parent

    _sta_path = _base / "state_transaction_adapter.py"
    _spec = importlib.util.spec_from_file_location("system_state_transaction_adapter_slice24", str(_sta_path))
    state_transaction_adapter = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = state_transaction_adapter
    _spec.loader.exec_module(state_transaction_adapter)

    _slv_path = _base / "system_log_validator.py"
    _spec = importlib.util.spec_from_file_location("system_log_validator_slice24", str(_slv_path))
    system_log_validator = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = system_log_validator
    _spec.loader.exec_module(system_log_validator)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _advance_transaction(
    transaction: dict[str, Any],
    target_state: str,
    actor_id: str,
    metadata_update: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    result = state_transaction_adapter.state_transaction_advance(
        {
            "transaction": transaction,
            "target_state": target_state,
            "actor_id": actor_id,
            "metadata_update": metadata_update or {},
        }
    )
    if "error" in result:
        return None, result
    return dict(result.get("transaction") or {}), None


def _next_prev_hash(ledger_path: Path) -> str:
    records = system_log_validator.load_ledger(ledger_path)
    if not records:
        return "genesis"
    return system_log_validator.hash_record(records[-1])


def _append_commitment(
    *,
    ledger_path: Path,
    actor_id: str,
    actor_role: str,
    commitment_type: str,
    subject_id: str,
    summary: str,
    metadata: dict[str, Any],
    subject_hash: str | None = None,
    domain_id: str | None = None,
) -> dict[str, Any]:
    record = build_commitment_record(
        actor_id=actor_id,
        actor_role=actor_role,
        commitment_type=commitment_type,
        subject_id=subject_id,
        summary=summary,
        subject_hash=subject_hash,
        domain_id=domain_id,
        metadata=metadata,
        prev_record_hash=_next_prev_hash(ledger_path),
    )
    system_log_validator.append_record(ledger_path, record)
    return record


def commit_evidence_and_confirm_teardown(payload: dict[str, Any]) -> dict[str, Any]:
    evidence_commit = payload.get("evidence_commit")
    teardown_result = payload.get("teardown_result")
    if not isinstance(evidence_commit, dict):
        return {"status": "error", "error": "Missing or invalid 'evidence_commit' dict in payload"}
    if not isinstance(teardown_result, dict):
        return {"status": "error", "error": "Missing or invalid 'teardown_result' dict in payload"}

    actor_id = str(payload.get("actor_id") or "system-pack")
    actor_role = str(payload.get("actor_role") or "system")
    domain_id = payload.get("domain_id")
    ledger_raw = payload.get("ledger_path") or "data/system/system-log-ledger.jsonl"
    ledger_path = Path(str(ledger_raw))

    transaction_raw = payload.get("transaction")
    if isinstance(transaction_raw, dict) and "transaction_id" in transaction_raw:
        transaction = dict(transaction_raw)
    else:
        operation = str(payload.get("operation") or "system_evidence_commit_teardown")
        transaction = StateTransaction(
            operation=operation,
            actor_id=actor_id,
            metadata={
                "plan_id": evidence_commit.get("plan_id"),
                "slice_id": evidence_commit.get("slice_id"),
                "node_id": evidence_commit.get("node_id"),
                "lifecycle_state": "HarvestingEvidence",
            },
        ).to_dict()

    current_state = str(transaction.get("state") or "")
    if current_state == TransactionState.FINALIZED.value:
        return {
            "status": "already_finalized",
            "transaction": transaction,
            "ledger_path": str(ledger_path),
            "records": [],
            "lifecycle": [str((transaction.get("metadata") or {}).get("lifecycle_state") or "TeardownConfirmed")],
        }

    lifecycle: list[str] = []
    records: list[dict[str, Any]] = []

    if str(transaction.get("state") or "") == TransactionState.PROPOSED.value:
        transaction, err = _advance_transaction(
            transaction,
            TransactionState.VALIDATED.value,
            actor_id,
            {"lifecycle_state": "HarvestingEvidence"},
        )
        if err is not None:
            return {"status": "error", "error": err.get("error", "Failed to validate transaction"), "details": err}

    if str(transaction.get("state") or "") != TransactionState.VALIDATED.value:
        return {
            "status": "error",
            "error": "Transaction must be PROPOSED or VALIDATED for evidence commit",
            "current_state": str(transaction.get("state") or ""),
        }

    evidence_hash = _canonical_sha256(evidence_commit)
    transaction, err = _advance_transaction(
        transaction,
        TransactionState.COMMITTED.value,
        actor_id,
        {"lifecycle_state": "EvidenceCommitted", "evidence_hash": evidence_hash},
    )
    if err is not None:
        return {"status": "error", "error": err.get("error", "Failed to commit transaction"), "details": err}
    lifecycle.append("EvidenceCommitted")

    subject_id = str(evidence_commit.get("node_id") or evidence_commit.get("slice_id") or evidence_commit.get("plan_id") or "unknown")
    evidence_record = _append_commitment(
        ledger_path=ledger_path,
        actor_id=actor_id,
        actor_role=actor_role,
        commitment_type="evidence_commit",
        subject_id=subject_id,
        summary=f"Committed evidence for {subject_id}",
        metadata={
            "plan_id": evidence_commit.get("plan_id"),
            "slice_id": evidence_commit.get("slice_id"),
            "node_id": evidence_commit.get("node_id"),
            "artifacts": list(evidence_commit.get("artifacts") or []),
            "checksums": dict(evidence_commit.get("checksums") or {}),
            "test_summary": dict(evidence_commit.get("test_summary") or {}),
            "collected_at": evidence_commit.get("collected_at"),
        },
        subject_hash=evidence_hash,
        domain_id=str(domain_id) if domain_id is not None else None,
    )
    records.append(evidence_record)

    lifecycle.append("TearingDown")
    failed_paths = list(teardown_result.get("failed") or [])
    if failed_paths:
        lifecycle.append("TeardownFailed")
        escalation_record = _append_commitment(
            ledger_path=ledger_path,
            actor_id=actor_id,
            actor_role=actor_role,
            commitment_type="cleanup_escalated",
            subject_id=subject_id,
            summary=f"Teardown escalation for {subject_id}",
            metadata={
                "plan_id": teardown_result.get("plan_id"),
                "slice_id": teardown_result.get("slice_id"),
                "removed": list(teardown_result.get("removed") or []),
                "failed": failed_paths,
                "started_at": teardown_result.get("started_at"),
                "completed_at": teardown_result.get("completed_at"),
            },
            domain_id=str(domain_id) if domain_id is not None else None,
        )
        records.append(escalation_record)

        transaction, err = _advance_transaction(
            transaction,
            TransactionState.FINALIZED.value,
            actor_id,
            {"lifecycle_state": "CleanupEscalated", "teardown_status": "failed"},
        )
        if err is not None:
            return {"status": "error", "error": err.get("error", "Failed to finalize transaction"), "details": err}

        lifecycle.append("CleanupEscalated")
        return {
            "status": "escalated",
            "transaction": transaction,
            "ledger_path": str(ledger_path),
            "records": records,
            "lifecycle": lifecycle,
        }

    confirmation_record = _append_commitment(
        ledger_path=ledger_path,
        actor_id=actor_id,
        actor_role=actor_role,
        commitment_type="teardown_confirmation",
        subject_id=subject_id,
        summary=f"Teardown confirmed for {subject_id}",
        metadata={
            "plan_id": teardown_result.get("plan_id"),
            "slice_id": teardown_result.get("slice_id"),
            "removed": list(teardown_result.get("removed") or []),
            "failed": [],
            "started_at": teardown_result.get("started_at"),
            "completed_at": teardown_result.get("completed_at"),
        },
        domain_id=str(domain_id) if domain_id is not None else None,
    )
    records.append(confirmation_record)

    transaction, err = _advance_transaction(
        transaction,
        TransactionState.FINALIZED.value,
        actor_id,
        {"lifecycle_state": "TeardownConfirmed", "teardown_status": "confirmed"},
    )
    if err is not None:
        return {"status": "error", "error": err.get("error", "Failed to finalize transaction"), "details": err}

    lifecycle.append("TeardownConfirmed")
    return {
        "status": "ok",
        "transaction": transaction,
        "ledger_path": str(ledger_path),
        "records": records,
        "lifecycle": lifecycle,
    }
