"""POST /api/chat — domain-resolved chat endpoint."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from lumina.api import config as _cfg
from lumina.api.dependencies import get_institutional_indexer
from lumina.api.middleware import _bearer_scheme, get_current_user
from lumina.api.models import ChatRequest, ChatResponse
from lumina.api.processing import process_message
from lumina.api.session import _session_containers
from lumina.core.domain_registry import DomainNotFoundError
from lumina.core.permissions import Operation, check_permission
from lumina.system_log.commit_guard import requires_log_commit
from lumina.thread_routing.bindings import load_thread_session_binding
from lumina.thread_routing.policy import load_thread_routing_policy
from lumina.thread_routing.summaries import record_thread_recap

log = logging.getLogger("lumina-api")

router = APIRouter()

_THREAD_ROUTING_POLICY_PATH = _cfg._REPO_ROOT / "model-packs" / "business-ops" / "cfg" / "thread-routing-policy.yaml"
def _get_accessible_domain_ids(
    user: dict[str, Any],
    routing_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Return domain IDs the user has EXECUTE access to."""
    if user.get("role") == "root":
        return list(routing_map.keys())

    accessible: list[str] = []
    user_domain_roles = user.get("domain_roles") or {}
    for domain_id in routing_map:
        try:
            runtime = _cfg.DOMAIN_REGISTRY.get_runtime_context(domain_id)
            domain_physics_path = runtime["domain_physics_path"]
            domain = _cfg.PERSISTENCE.load_domain_physics(str(domain_physics_path))
            module_perms = domain.get("permissions")
            if module_perms is None:
                accessible.append(domain_id)
                continue
            # Resolve the user's domain role for this module
            mod_id = runtime.get("module_id", domain_id)
            user_dr = user_domain_roles.get(mod_id) or user_domain_roles.get(domain_id)
            if check_permission(
                user_id=user["sub"],
                user_role=user["role"],
                module_permissions=module_perms,
                operation=Operation.EXECUTE,
                domain_role=user_dr,
                domain_roles_config=domain.get("domain_roles"),
                groups_config=domain.get("groups"),
            ):
                accessible.append(domain_id)
        except Exception:
            continue
    return accessible


@router.post("/api/chat", response_model=ChatResponse)
@requires_log_commit
async def chat(
    req: ChatRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user = await get_current_user(credentials)
    if req.thread_id is not None:
        if user is None:
            raise HTTPException(status_code=401, detail="Thread routing requires authentication")
        organization_id = user.get("organization_id")
        site_id = user.get("site_id")
        if not isinstance(organization_id, str) or not organization_id or not isinstance(site_id, str) or not site_id:
            raise HTTPException(status_code=403, detail="Thread routing requires an active organization and site context")
        binding = await run_in_threadpool(
            load_thread_session_binding,
            _cfg.PERSISTENCE,
            thread_id=req.thread_id,
            organization_id=organization_id,
            site_id=site_id,
        )
        if binding is None:
            raise HTTPException(status_code=404, detail="Thread routing binding was not found")
        if binding.actor_id != user.get("sub"):
            raise HTTPException(status_code=403, detail="Thread routing binding belongs to another actor")
        if req.session_id is not None and req.session_id != binding.session_id:
            raise HTTPException(status_code=409, detail="session_id does not match the requested thread")
        session_id = binding.session_id
    else:
        session_id = req.session_id or str(uuid.uuid4())

    # ── Domain resolution: semantic routing → explicit → default ──
    routing_record: dict[str, Any] = {
        "event": "routing_decision",
        "explicit_domain": req.domain_id,
        "session_id": session_id,
        "timestamp": time.time(),
    }

    if req.domain_id:
        try:
            resolved_domain_id = _cfg.DOMAIN_REGISTRY.resolve_domain_id(req.domain_id)
        except DomainNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        routing_record["method"] = "explicit"
        routing_record["confidence"] = 1.0
    else:
        try:
            from core_nlp import classify_domain
        except ImportError:
            classify_domain = None  # type: ignore[assignment]

        routing_map = _cfg.DOMAIN_REGISTRY.get_domain_routing_map()
        inferred = None

        if classify_domain is not None and routing_map:
            accessible = None
            if user is not None:
                accessible = _get_accessible_domain_ids(user, routing_map)
            inferred = classify_domain(req.message, routing_map, accessible)

        if inferred is not None:
            resolved_domain_id = inferred["domain_id"]
            routing_record["method"] = inferred.get("method", "keyword")
            routing_record["confidence"] = inferred["confidence"]
            routing_record["inferred_domain"] = inferred["domain_id"]
            log.info(
                "[%s] Semantic routing: %s (confidence=%.3f, method=%s)",
                session_id,
                resolved_domain_id,
                inferred["confidence"],
                inferred.get("method"),
            )
        else:
            try:
                resolved_domain_id = _cfg.DOMAIN_REGISTRY.resolve_default_for_user(user)
            except RuntimeError:
                raise HTTPException(
                    status_code=400,
                    detail="Could not determine domain. Please specify domain_id.",
                )
            routing_record["method"] = "role_default"
            routing_record["confidence"] = 0.0
            log.info(
                "[%s] Role-based default routing: %s (role=%s)",
                session_id,
                resolved_domain_id,
                user.get("role") if user else "unauthenticated",
            )

    routing_record["final_domain"] = resolved_domain_id

    # ── RBAC gate ──
    if user is not None:
        runtime = _cfg.DOMAIN_REGISTRY.get_runtime_context(resolved_domain_id)
        domain_physics_path = runtime["domain_physics_path"]
        domain = await run_in_threadpool(_cfg.PERSISTENCE.load_domain_physics, str(domain_physics_path))
        module_perms = domain.get("permissions")
        if module_perms:
            user_domain_roles = user.get("domain_roles") or {}
            mod_id = runtime.get("module_id", resolved_domain_id)
            user_dr = user_domain_roles.get(mod_id) or user_domain_roles.get(resolved_domain_id)
            # Fallback: domain_roles are keyed by full module path
            # (e.g. "domain/edu/general-education/v1") but mod_id may be
            # just the domain registry key ("education").  Search for any
            # matching entry whose key contains the resolved domain ID.
            if not user_dr:
                for _dr_key, _dr_val in user_domain_roles.items():
                    if resolved_domain_id in _dr_key:
                        user_dr = _dr_val
                        break
            has_access = check_permission(
                user_id=user["sub"],
                user_role=user["role"],
                module_permissions=module_perms,
                operation=Operation.EXECUTE,
                domain_role=user_dr,
                domain_roles_config=domain.get("domain_roles"),
                groups_config=domain.get("groups"),
            )
            if not has_access:
                raise HTTPException(status_code=403, detail="Module access denied")

    # ── Holodeck role gate ──
    if req.holodeck:
        _holodeck_roles = {"root", "admin"}
        if user is None or user.get("role") not in _holodeck_roles:
            raise HTTPException(
                status_code=403,
                detail="Holodeck mode is restricted to root and admin roles.",
            )

    # ── Log routing decision to meta-ledger ──
    try:
        _cfg.PERSISTENCE.append_log_record(
            session_id,
            routing_record,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path(session_id),
        )
    except Exception:
        log.debug("Could not write routing decision to meta-ledger")

    try:
        result = await run_in_threadpool(
            process_message,
            session_id,
            req.message,
            req.turn_data_override,
            req.deterministic_response,
            resolved_domain_id,
            user,
            req.model_id,
            req.model_version,
            req.holodeck,
            None,                      # physics_sandbox
            req.journal_entity_salt,
            req.journal_mode,
        )
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "policy commitment" in msg:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Domain physics have been modified but not yet committed. "
                    "An administrator must run 'commit domain physics' before "
                    "this module can accept conversations."
                ),
            )
        if "system-physics commitment" in msg or "system_physics" in msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    "System physics are not yet committed. "
                    "The system administrator must commit the current "
                    "system-physics.json before the service is available."
                ),
            )
        log.exception("RuntimeError processing message for session %s", session_id)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        log.exception("Error processing message for session %s", session_id)
        raise HTTPException(status_code=500, detail=str(exc))

    if req.thread_id is not None and user is not None:
        try:
            policy = load_thread_routing_policy(
                _THREAD_ROUTING_POLICY_PATH,
                organization_id=str(user["organization_id"]),
                site_id=str(user["site_id"]),
            )
            container = _session_containers.get(session_id)
            turn_count = container.active_context.turn_count if container is not None else 0
            await run_in_threadpool(
                record_thread_recap,
                persistence=_cfg.PERSISTENCE,
                indexer=get_institutional_indexer(),
                policy=policy,
                thread_id=req.thread_id,
                actor_id=str(user["sub"]),
                turn_count=turn_count,
                message=req.message,
                action=str(result["action"]),
                domain_id=result.get("domain_id"),
                device_id=user.get("device_id"),
            )
        except Exception:
            log.warning("Could not record thread recap for %s", req.thread_id, exc_info=True)

    return ChatResponse(
        session_id=session_id,
        response=result["response"],
        action=result["action"],
        prompt_type=result["prompt_type"],
        escalated=result["escalated"],
        tool_results=result.get("tool_results") or None,
        domain_id=result.get("domain_id"),
        structured_content=result.get("structured_content"),
        transcript_seal=result.get("transcript_seal"),
        transcript_seal_metadata=result.get("transcript_seal_metadata"),
        transcript_snapshot=result.get("transcript_snapshot"),
    )
