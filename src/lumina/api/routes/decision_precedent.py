"""Authenticated, scope-safe decision-precedent preflight API."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from lumina.api import config as _cfg
from lumina.api.dependencies import (
    get_active_operating_context,
    get_authenticated_user,
    get_institutional_indexer,
)
from lumina.api.models import (
    DecisionPrecedentConfirmationResponse,
    DecisionPrecedentPreflightRequest,
    DecisionPrecedentPreflightResponse,
)
from lumina.decision_precedent.policy import load_decision_precedent_policy
from lumina.decision_precedent.scorer import DecisionConfidenceScore
from lumina.decision_precedent.service import evaluate_decision_precedent
from lumina.system_log.admin_operations import build_trace_event
from lumina.system_log.commit_guard import requires_log_commit

router = APIRouter()

_POLICY_PATH = _cfg._REPO_ROOT / "model-packs" / "business-ops" / "cfg" / "decision-precedent-policy.yaml"
_PENDING_CONFIRMATION_TTL_SECONDS = 300
_ESCALATION_TARGET_ROLE = "business-ops:owner-manager"


@dataclass(frozen=True)
class _PendingConfirmation:
    score: DecisionConfidenceScore
    session_id: str
    expires_at: float


_pending_confirmations: dict[str, _PendingConfirmation] = {}
_consumed_confirmation_ids: dict[str, float] = {}


def _prune_expired_confirmations(now: float | None = None) -> None:
    """Bound in-memory confirmation state to its fixed replay-protection TTL."""
    current = time.monotonic() if now is None else now
    for record_id, pending in list(_pending_confirmations.items()):
        if pending.expires_at <= current:
            del _pending_confirmations[record_id]
    for record_id, expires_at in list(_consumed_confirmation_ids.items()):
        if expires_at <= current:
            del _consumed_confirmation_ids[record_id]


def _escalation_session_id(session_id: str | None, confidence_record_id: str) -> str:
    """Produce a schema-valid opaque session identifier for the escalation record."""
    seed = session_id or confidence_record_id
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"decision-precedent:{seed}"))


def _build_escalation_record(
    score: DecisionConfidenceScore,
    *,
    session_id: str | None,
    created_utc: datetime | None = None,
) -> dict[str, object]:
    """Create a standard pending EscalationRecord without business-action content."""
    timestamp = created_utc or datetime.now(UTC)
    packet_id = str(uuid.uuid4())
    packet = {
        "packet_id": packet_id,
        "organization_id": score.organization_id,
        "site_id": score.site_id,
        "actor_id": score.actor_id,
        "confidence_record_id": score.record_id,
        "policy_version": score.policy_version,
        "risk_class": score.risk_class,
        "tier": "mandatory_escalation",
        "target_role": _ESCALATION_TARGET_ROLE,
        "status": "pending",
        "precedent_summary_record_ids": [
            match.summary_record_id for match in score.precedent_matches
        ],
        "created_utc": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    return {
        "record_type": "EscalationRecord",
        "record_id": str(uuid.uuid4()),
        "prev_record_hash": "genesis",
        "timestamp_utc": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "session_id": _escalation_session_id(session_id, score.record_id),
        "escalating_actor_id": score.actor_id,
        "target_meta_authority_id": _ESCALATION_TARGET_ROLE,
        "organization_id": score.organization_id,
        "site_id": score.site_id,
        "trigger": "Decision precedent policy requires human approval.",
        "trigger_type": "other",
        "evidence_summary": {
            "decision_confidence_score": score.as_record(created_utc=timestamp),
            "business_escalation_packet": packet,
        },
        "status": "pending",
        "proposed_action": "Human approval is required before any business action.",
    }


@router.post(
    "/api/decision-precedent/preflight",
    response_model=DecisionPrecedentPreflightResponse,
)
@requires_log_commit
async def preflight(
    req: DecisionPrecedentPreflightRequest,
    user: dict[str, object] = Depends(get_authenticated_user),
    context: dict[str, str | None] = Depends(get_active_operating_context),
) -> DecisionPrecedentPreflightResponse:
    """Evaluate scoped precedent and create audit evidence without executing work."""
    try:
        policy = load_decision_precedent_policy(
            _POLICY_PATH,
            organization_id=str(context["organization_id"]),
            site_id=str(context["site_id"]),
        )
        score = await run_in_threadpool(
            evaluate_decision_precedent,
            req.message,
            indexer=get_institutional_indexer(),
            policy=policy,
            actor_id=str(user["sub"]),
            risk_class=req.risk_class,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ledger_session_id = req.session_id or "decision-precedent"
    score_record = score.as_record()
    trace_event = build_trace_event(
        session_id=ledger_session_id,
        actor_id=str(user["sub"]),
        event_type="other",
        decision="decision_precedent_evaluated",
        evidence_summary={"decision_confidence_score": score_record},
    )
    await run_in_threadpool(
        _cfg.PERSISTENCE.append_log_record,
        ledger_session_id,
        trace_event,
        _cfg.PERSISTENCE.get_system_ledger_path(ledger_session_id),
    )
    escalation_record_id: str | None = None
    if score.tier == "mandatory_escalation":
        escalation = _build_escalation_record(score, session_id=req.session_id)
        escalation_record_id = str(escalation["record_id"])
        await run_in_threadpool(
            _cfg.PERSISTENCE.append_log_record,
            ledger_session_id,
            escalation,
            _cfg.PERSISTENCE.get_system_ledger_path(ledger_session_id),
        )
    elif score.tier == "require_confirmation":
        _prune_expired_confirmations()
        _pending_confirmations[score.record_id] = _PendingConfirmation(
            score=score,
            session_id=ledger_session_id,
            expires_at=time.monotonic() + _PENDING_CONFIRMATION_TTL_SECONDS,
        )
    return DecisionPrecedentPreflightResponse(
        confidence_record_id=score.record_id,
        organization_id=score.organization_id,
        site_id=score.site_id,
        actor_id=score.actor_id,
        policy_version=score.policy_version,
        risk_class=score.risk_class,
        final_score=score.final_score,
        tier=score.tier,
        rationale_codes=list(score.rationale_codes),
        confirmation_required=score.tier == "require_confirmation",
        escalation_record_id=escalation_record_id,
    )


@router.post(
    "/api/decision-precedent/{confidence_record_id}/confirm",
    response_model=DecisionPrecedentConfirmationResponse,
)
@requires_log_commit
async def confirm(
    confidence_record_id: str,
    user: dict[str, object] = Depends(get_authenticated_user),
    context: dict[str, str | None] = Depends(get_active_operating_context),
) -> DecisionPrecedentConfirmationResponse:
    """Record explicit confirmation intent; this endpoint cannot execute a business action."""
    _prune_expired_confirmations()
    if confidence_record_id in _consumed_confirmation_ids:
        raise HTTPException(status_code=409, detail="Decision precedent confirmation has already been applied")
    pending = _pending_confirmations.get(confidence_record_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Decision precedent confirmation was not found")
    if pending.expires_at <= time.monotonic():
        del _pending_confirmations[confidence_record_id]
        raise HTTPException(status_code=410, detail="Decision precedent confirmation has expired")
    score = pending.score
    if score.actor_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Decision precedent confirmation belongs to another actor")
    if score.organization_id != context["organization_id"] or score.site_id != context["site_id"]:
        raise HTTPException(status_code=403, detail="Decision precedent confirmation is outside the active context")
    confirmation_id = str(uuid.uuid4())
    event = build_trace_event(
        session_id=pending.session_id,
        actor_id=str(user["sub"]),
        event_type="other",
        decision="decision_precedent_confirmed",
        evidence_summary={
            "confirmation_id": confirmation_id,
            "confidence_record_id": score.record_id,
            "tier": score.tier,
        },
    )
    await run_in_threadpool(
        _cfg.PERSISTENCE.append_log_record,
        pending.session_id,
        event,
        _cfg.PERSISTENCE.get_system_ledger_path(pending.session_id),
    )
    del _pending_confirmations[confidence_record_id]
    _consumed_confirmation_ids[confidence_record_id] = time.monotonic() + _PENDING_CONFIRMATION_TTL_SECONDS
    return DecisionPrecedentConfirmationResponse(
        confirmation_id=confirmation_id,
        confidence_record_id=score.record_id,
        tier=score.tier,
    )