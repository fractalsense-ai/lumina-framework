"""Authenticated, scope-safe thread-routing preflight API."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from lumina.api import config as _cfg
from lumina.api.dependencies import (
    get_active_operating_context,
    get_authenticated_user,
    get_institutional_indexer,
)
from lumina.api.models import (
    ThreadRoutingCandidateResponse,
    ThreadRoutingConfirmationRequest,
    ThreadRoutingConfirmationResponse,
    ThreadRoutingPreflightRequest,
    ThreadRoutingPreflightResponse,
)
from lumina.system_log.commit_guard import requires_log_commit
from lumina.system_log.admin_operations import build_trace_event
from lumina.thread_routing.policy import load_thread_routing_policy
from lumina.thread_routing.router import ThreadRoutingDecision
from lumina.thread_routing.service import preflight_thread_route
from lumina.thread_routing.bindings import (
    create_thread_session_binding,
    load_thread_session_binding,
)

router = APIRouter()

_POLICY_PATH = _cfg._REPO_ROOT / "model-packs" / "business-ops" / "cfg" / "thread-routing-policy.yaml"
_PENDING_DECISION_TTL_SECONDS = 300


@dataclass(frozen=True)
class _PendingDecision:
    decision: ThreadRoutingDecision
    session_id: str
    active_thread_id: str | None
    expires_at: float


_pending_decisions: dict[str, _PendingDecision] = {}
_consumed_decision_ids: dict[str, float] = {}


def _prune_expired_decisions(now: float | None = None) -> None:
    """Bound in-memory routing state to the confirmation TTL."""
    current_time = time.monotonic() if now is None else now
    for decision_id, pending in list(_pending_decisions.items()):
        if pending.expires_at <= current_time:
            del _pending_decisions[decision_id]
    for decision_id, expires_at in list(_consumed_decision_ids.items()):
        if expires_at <= current_time:
            del _consumed_decision_ids[decision_id]


def _response_from_record(record: dict[str, object]) -> ThreadRoutingPreflightResponse:
    candidates = [
        ThreadRoutingCandidateResponse(
            thread_id=str(candidate["thread_id"]),
            summary_record_id=str(candidate["summary_record_id"]),
            score=float(candidate["score"]),
        )
        for candidate in record["candidates"]  # type: ignore[index]
    ]
    return ThreadRoutingPreflightResponse(
        decision_id=str(record["decision_id"]),
        organization_id=str(record["organization_id"]),
        site_id=str(record["site_id"]),
        actor_id=str(record["actor_id"]),
        decision=str(record["decision"]),
        thread_id=str(record["thread_id"]),
        source_thread_id=record["source_thread_id"] if isinstance(record["source_thread_id"], str) else None,
        policy_version=int(record["policy_version"]),
        confidence=float(record["confidence"]),
        rationale_code=str(record["rationale_code"]),
        operator_confirmation_required=bool(record["operator_confirmation_required"]),
        operator_override=bool(record["operator_override"]),
        candidates=candidates,
    )


def _resolve_confirmation(
    pending: _PendingDecision,
    action: str,
) -> ThreadRoutingDecision:
    decision = pending.decision
    if action == "accept":
        return decision
    if action == "attach_existing":
        if not decision.candidates:
            raise HTTPException(status_code=422, detail="No scoped candidate is available to attach")
        candidate = decision.candidates[0]
        binding = load_thread_session_binding(
            _cfg.PERSISTENCE,
            thread_id=candidate.thread_id,
            organization_id=decision.organization_id,
            site_id=decision.site_id,
        )
        if binding is None:
            raise HTTPException(status_code=409, detail="Candidate thread has no runtime session binding")
        if binding.actor_id != decision.actor_id:
            raise HTTPException(status_code=403, detail="Candidate thread belongs to another actor")
        return replace(
            decision,
            decision="attach_existing",
            thread_id=candidate.thread_id,
            source_thread_id=None,
            operator_override=True,
        )
    if action == "create_new":
        return replace(
            decision,
            decision="create_new",
            thread_id=f"thread-{uuid.uuid4()}",
            source_thread_id=None,
            operator_override=True,
        )
    if action == "fork_from":
        if not pending.active_thread_id:
            raise HTTPException(status_code=422, detail="An active thread is required to fork")
        return replace(
            decision,
            decision="fork_from",
            thread_id=f"thread-{uuid.uuid4()}",
            source_thread_id=pending.active_thread_id,
            operator_override=True,
        )
    raise HTTPException(status_code=422, detail="Unsupported routing confirmation action")


@router.post("/api/thread-routing/preflight", response_model=ThreadRoutingPreflightResponse)
@requires_log_commit
async def preflight(
    req: ThreadRoutingPreflightRequest,
    user: dict[str, object] = Depends(get_authenticated_user),
    context: dict[str, str | None] = Depends(get_active_operating_context),
) -> ThreadRoutingPreflightResponse:
    """Return an auditable attach/new/fork recommendation without mutating a session."""
    try:
        policy = load_thread_routing_policy(
            _POLICY_PATH,
            organization_id=str(context["organization_id"]),
            site_id=str(context["site_id"]),
        )
        preflight_result = await run_in_threadpool(
            preflight_thread_route,
            req.message,
            indexer=get_institutional_indexer(),
            policy=policy,
            actor_id=str(user["sub"]),
            active_thread_id=req.active_thread_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = preflight_result.decision.as_record()
    routing_session_id = req.session_id or "thread-routing"
    _prune_expired_decisions()
    _pending_decisions[preflight_result.decision.decision_id] = _PendingDecision(
        decision=preflight_result.decision,
        session_id=routing_session_id,
        active_thread_id=req.active_thread_id,
        expires_at=time.monotonic() + _PENDING_DECISION_TTL_SECONDS,
    )
    await run_in_threadpool(
        _cfg.PERSISTENCE.append_log_record,
        routing_session_id,
        record,
        _cfg.PERSISTENCE.get_system_ledger_path(routing_session_id),
    )
    return _response_from_record(record)


@router.post(
    "/api/thread-routing/{decision_id}/confirm",
    response_model=ThreadRoutingConfirmationResponse,
)
@requires_log_commit
async def confirm(
    decision_id: str,
    req: ThreadRoutingConfirmationRequest,
    user: dict[str, object] = Depends(get_authenticated_user),
    context: dict[str, str | None] = Depends(get_active_operating_context),
) -> ThreadRoutingConfirmationResponse:
    """Confirm or override a preflight decision as auditable routing intent."""
    current_time = time.monotonic()
    for consumed_id, expires_at in list(_consumed_decision_ids.items()):
        if expires_at <= current_time:
            del _consumed_decision_ids[consumed_id]
    if decision_id in _consumed_decision_ids:
        raise HTTPException(status_code=409, detail="Thread routing decision has already been applied")
    pending = _pending_decisions.get(decision_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Thread routing decision was not found")
    if pending.expires_at <= current_time:
        del _pending_decisions[decision_id]
        raise HTTPException(status_code=410, detail="Thread routing decision has expired")
    _prune_expired_decisions(current_time)
    decision = pending.decision
    if decision.actor_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Thread routing decision belongs to another actor")
    if (
        decision.organization_id != context["organization_id"]
        or decision.site_id != context["site_id"]
    ):
        raise HTTPException(status_code=403, detail="Thread routing decision is outside the active context")

    selected = _resolve_confirmation(pending, req.action)
    binding = load_thread_session_binding(
        _cfg.PERSISTENCE,
        thread_id=selected.thread_id,
        organization_id=selected.organization_id,
        site_id=selected.site_id,
    )
    if binding is None:
        if selected.decision == "attach_existing":
            raise HTTPException(status_code=409, detail="Candidate thread has no runtime session binding")
        binding = create_thread_session_binding(
            _cfg.PERSISTENCE,
            thread_id=selected.thread_id,
            session_id=str(uuid.uuid4()),
            organization_id=selected.organization_id,
            site_id=selected.site_id,
            actor_id=selected.actor_id,
        )
    elif binding.actor_id != selected.actor_id:
        raise HTTPException(status_code=403, detail="Thread binding belongs to another actor")
    application_id = str(uuid.uuid4())
    evidence = selected.as_record()
    event = build_trace_event(
        session_id=pending.session_id,
        actor_id=str(user["sub"]),
        event_type="other",
        decision="thread_routing_confirmed",
        evidence_summary={
            "application_id": application_id,
            "preflight_decision_id": decision_id,
            "routing_decision": evidence,
            "session_id": binding.session_id,
        },
    )
    await run_in_threadpool(
        _cfg.PERSISTENCE.append_log_record,
        pending.session_id,
        event,
        _cfg.PERSISTENCE.get_system_ledger_path(pending.session_id),
    )
    del _pending_decisions[decision_id]
    _consumed_decision_ids[decision_id] = time.monotonic() + _PENDING_DECISION_TTL_SECONDS
    return ThreadRoutingConfirmationResponse(
        application_id=application_id,
        decision_id=decision_id,
        thread_id=selected.thread_id,
        source_thread_id=selected.source_thread_id,
        decision=selected.decision,
        operator_override=selected.operator_override,
        session_id=binding.session_id,
    )