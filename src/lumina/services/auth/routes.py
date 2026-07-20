"""Auth endpoints: register, login, token management, user profile."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from lumina.api import config as _cfg
from lumina.api.middleware import _bearer_scheme, get_current_user, require_auth, require_role
from lumina.api.models import (
    InviteUserRequest,
    LoginRequest,
    OperatingContextSwitchRequest,
    PasswordResetRequest,
    RegisterRequest,
    RevokeRequest,
    SetupPasswordRequest,
    TokenResponse,
    UpdateUserRequest,
    UserInvitationResponse,
    UserResponse,
)
from lumina.auth.auth import (
    VALID_ROLES,
    ADMIN_ROLES,
    DOMAIN_ADMIN_ROLES,
    create_jwt,
    create_scoped_jwt,
    hash_password,
    revoke_token_jti,
    verify_password,
)
from lumina.auth.operating_context import (
    default_operating_context,
    normalize_operating_memberships,
    resolve_operating_context,
)
from lumina.system_log.admin_operations import (
    build_domain_role_assignment,
    build_domain_role_revocation,
    build_trace_event,
    can_govern_domain,
    map_role_to_actor_role,
)
from lumina.system_log.commit_guard import requires_log_commit
from lumina.core.email_sender import send_invite_email
from lumina.core.invite_store import (
    generate_invite_token,
    validate_invite_token,
    _INVITE_TOKEN_TTL_SECONDS as _INVITE_TOKEN_TTL,
)

log = logging.getLogger("lumina-api")

router = APIRouter()


def _token_response(
    user: dict[str, Any],
    *,
    operating_context: dict[str, str | None] | None = None,
    device_id: str | None = None,
) -> TokenResponse:
    """Issue a legacy-compatible user JWT carrying one validated context."""
    context = operating_context or {}
    token = create_jwt(
        user_id=user["user_id"],
        role=user["role"],
        governed_modules=user.get("governed_modules") or [],
        domain_roles=user.get("domain_roles") or {},
        organization_id=context.get("organization_id"),
        site_id=context.get("site_id"),
        device_id=device_id,
        site_role=context.get("site_role"),
    )
    return TokenResponse(
        access_token=token,
        user_id=user["user_id"],
        role=user["role"],
        organization_id=context.get("organization_id"),
        site_id=context.get("site_id"),
        device_id=device_id,
    )


def _user_response(user: dict[str, Any]) -> UserResponse:
    return UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        governed_modules=user.get("governed_modules") or [],
        active=user.get("active", True),
        operating_memberships=user.get("operating_memberships") or [],
    )


@router.post("/api/auth/register", response_model=TokenResponse)
@requires_log_commit
async def register(req: RegisterRequest) -> TokenResponse:
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")

    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await run_in_threadpool(_cfg.PERSISTENCE.get_user_by_username, req.username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already taken")

    all_users = await run_in_threadpool(_cfg.PERSISTENCE.list_users)
    role = req.role
    if _cfg.BOOTSTRAP_MODE and len(all_users) == 0:
        role = "root"
        log.info("Bootstrap mode: first user promoted to root")

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)

    await run_in_threadpool(
        _cfg.PERSISTENCE.create_user, user_id, req.username, pw_hash, role, req.governed_modules,
    )

    token = create_jwt(user_id=user_id, role=role, governed_modules=req.governed_modules or [])

    event = build_trace_event(
        session_id="admin",
        actor_id=user_id,
        event_type="other",
        decision="user_registered",
        evidence_summary={"user_id": user_id, "username": req.username, "role": role},
    )
    try:
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )
    except Exception:
        log.debug("Could not write user_registered trace event")

    log.info("Registered user %s (%s) with role %s", req.username, user_id, role)
    return TokenResponse(access_token=token, user_id=user_id, role=role)


@router.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = await run_in_threadpool(_cfg.PERSISTENCE.get_user_by_username, req.username)
    if user is None or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")

    if user["role"] in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="System-track users must use /api/admin/auth/login",
        )
    if user["role"] in DOMAIN_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Domain authorities must use /api/domain/auth/login",
        )

    return _token_response(user, operating_context=default_operating_context(user.get("operating_memberships")))


@router.get("/api/auth/guest-token", response_model=TokenResponse)
async def guest_token() -> TokenResponse:
    guest_id = f"guest_{uuid.uuid4().hex[:12]}"
    token = create_jwt(user_id=guest_id, role="guest", governed_modules=[], ttl_minutes=30)
    return TokenResponse(access_token=token, user_id=guest_id, role="guest")


@router.post("/api/auth/refresh", response_model=TokenResponse)
async def refresh(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenResponse:
    current = await get_current_user(credentials)
    user_data = require_auth(current)

    user = await run_in_threadpool(_cfg.PERSISTENCE.get_user, user_data["sub"])
    if user is None or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    try:
        context = (
            resolve_operating_context(
                user.get("operating_memberships"),
                organization_id=user_data["organization_id"],
                site_id=user_data["site_id"],
            )
            if user_data.get("organization_id") or user_data.get("site_id")
            else default_operating_context(user.get("operating_memberships"))
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Active operating context is no longer assigned") from exc
    return _token_response(user, operating_context=context, device_id=user_data.get("device_id"))


@router.get("/api/auth/me", response_model=UserResponse)
async def me(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserResponse:
    current = await get_current_user(credentials)
    user_data = require_auth(current)
    user = await run_in_threadpool(_cfg.PERSISTENCE.get_user, user_data["sub"])
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(user)


@router.get("/api/auth/users", response_model=list[UserResponse])
async def list_all_users(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> list[UserResponse]:
    current = await get_current_user(credentials)
    user_data = require_auth(current)
    require_role(user_data, "root", "super_admin")
    users = await run_in_threadpool(_cfg.PERSISTENCE.list_users)
    return [
        _user_response(u)
        for u in users
    ]


# ── User management (root only) ──


@router.patch("/api/auth/users/{user_id}", response_model=UserResponse)
@requires_log_commit
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserResponse:
    current = await get_current_user(credentials)
    user_data = require_auth(current)
    require_role(user_data, "root")

    if req.role is not None and req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")

    if req.governed_modules is not None and req.role != "admin":
        if req.role is not None:
            raise HTTPException(
                status_code=400,
                detail="governed_modules can only be set for admin role",
            )

    target = await run_in_threadpool(_cfg.PERSISTENCE.get_user, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = target["role"]
    new_role = req.role or old_role
    new_governed = req.governed_modules if req.governed_modules is not None else target.get("governed_modules")

    updated = await run_in_threadpool(_cfg.PERSISTENCE.update_user_role, user_id, new_role, new_governed)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")

    if req.domain_roles is not None:
        dr_updated = await run_in_threadpool(
            _cfg.PERSISTENCE.update_user_domain_roles, user_id, req.domain_roles
        )
        if dr_updated is not None:
            updated = dr_updated
        for module_id, domain_role in req.domain_roles.items():
            prev_role = (target.get("domain_roles") or {}).get(module_id)
            if prev_role and prev_role != domain_role:
                record = build_domain_role_revocation(
                    actor_id=user_data["sub"],
                    actor_role=map_role_to_actor_role(user_data["role"]),
                    target_user_id=user_id,
                    module_id=module_id,
                    prev_role=prev_role,
                )
                try:
                    _cfg.PERSISTENCE.append_log_record(
                        "admin", record,
                        ledger_path=_cfg.PERSISTENCE.get_domain_ledger_path(module_id),
                    )
                except Exception:
                    log.debug("Could not write domain_role_revocation System Log record")
            record = build_domain_role_assignment(
                actor_id=user_data["sub"],
                actor_role=map_role_to_actor_role(user_data["role"]),
                target_user_id=user_id,
                module_id=module_id,
                domain_role=domain_role,
            )
            try:
                _cfg.PERSISTENCE.append_log_record(
                    "admin", record,
                    ledger_path=_cfg.PERSISTENCE.get_domain_ledger_path(module_id),
                )
            except Exception:
                log.debug("Could not write domain_role_assignment System Log record")

    if req.operating_memberships is not None:
        try:
            memberships = normalize_operating_memberships(
                [membership.model_dump() for membership in req.operating_memberships]
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        membership_updated = await run_in_threadpool(
            _cfg.PERSISTENCE.update_user_operating_memberships,
            user_id,
            memberships,
        )
        if membership_updated is not None:
            updated = membership_updated
        event = build_trace_event(
            session_id="admin",
            actor_id=user_data["sub"],
            event_type="other",
            decision="operating_memberships_updated",
            evidence_summary={
                "target_user_id": user_id,
                "organization_count": len(memberships),
                "site_count": sum(len(item["site_ids"]) for item in memberships),
            },
        )
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )

    if new_role != old_role:
        event = build_trace_event(
            session_id="admin",
            actor_id=user_data["sub"],
            event_type="other",
            decision=f"role_change: {old_role} -> {new_role}",
            evidence_summary={
                "target_user_id": user_id,
                "old_role": old_role,
                "new_role": new_role,
            },
        )
        try:
            _cfg.PERSISTENCE.append_log_record(
                "admin", event,
                ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
            )
        except Exception:
            log.debug("Could not write role_change trace event")

    return _user_response(updated)


@router.post("/api/auth/operating-context", response_model=TokenResponse)
@requires_log_commit
async def switch_operating_context(
    req: OperatingContextSwitchRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenResponse:
    """Validate a permitted site and replace the caller's active-context token."""
    current = await get_current_user(credentials)
    user_data = require_auth(current)
    if user_data.get("token_scope") != "user":
        raise HTTPException(status_code=403, detail="Operating context is available to user-track tokens only")
    user = await run_in_threadpool(_cfg.PERSISTENCE.get_user, user_data["sub"])
    if user is None or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    try:
        context = resolve_operating_context(
            user.get("operating_memberships"),
            organization_id=req.organization_id,
            site_id=req.site_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    old_jti = user_data.get("jti")
    if old_jti:
        revoke_token_jti(old_jti)
    event = build_trace_event(
        session_id="admin",
        actor_id=user_data["sub"],
        event_type="other",
        decision="operating_context_switched",
        evidence_summary={
            "from_organization_id": user_data.get("organization_id"),
            "from_site_id": user_data.get("site_id"),
            "organization_id": context["organization_id"],
            "site_id": context["site_id"],
            "device_id": req.device_id,
        },
    )
    _cfg.PERSISTENCE.append_log_record(
        "admin", event,
        ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
    )
    return _token_response(user, operating_context=context, device_id=req.device_id)


@router.delete("/api/auth/users/{user_id}", status_code=204)
@requires_log_commit
async def delete_user(
    user_id: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    current = await get_current_user(credentials)
    user_data = require_auth(current)
    require_role(user_data, "root")

    if user_id == user_data["sub"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    success = await run_in_threadpool(_cfg.PERSISTENCE.deactivate_user, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    event = build_trace_event(
        session_id="admin",
        actor_id=user_data["sub"],
        event_type="other",
        decision="user_deactivated",
        evidence_summary={"target_user_id": user_id},
    )
    try:
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )
    except Exception:
        log.debug("Could not write user_deactivated trace event")


@router.post("/api/auth/revoke", status_code=200)
@requires_log_commit
async def revoke_token(
    req: RevokeRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, str]:
    current = await get_current_user(credentials)
    user_data = require_auth(current)

    if req.user_id is not None and req.user_id != user_data["sub"]:
        require_role(user_data, "root", "super_admin")

    jti = user_data.get("jti")
    if jti:
        revoke_token_jti(jti)

    event = build_trace_event(
        session_id="admin",
        actor_id=user_data["sub"],
        event_type="other",
        decision="token_revoked",
        evidence_summary={"target_user_id": req.user_id or user_data["sub"]},
    )
    try:
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )
    except Exception:
        log.debug("Could not write token_revoked trace event")

    return {"status": "revoked"}


@router.post("/api/auth/password-reset", status_code=200)
@requires_log_commit
async def password_reset(
    req: PasswordResetRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, str]:
    current = await get_current_user(credentials)
    user_data = require_auth(current)

    target_user_id = req.user_id or user_data["sub"]
    if target_user_id != user_data["sub"]:
        require_role(user_data, "root", "super_admin")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_hash = hash_password(req.new_password)
    success = await run_in_threadpool(_cfg.PERSISTENCE.update_user_password, target_user_id, new_hash)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    event = build_trace_event(
        session_id="admin",
        actor_id=user_data["sub"],
        event_type="other",
        decision="password_reset",
        evidence_summary={"target_user_id": target_user_id},
    )
    try:
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )
    except Exception:
        log.debug("Could not write password_reset trace event")

    return {"status": "password_updated"}


# ── Invite / onboarding ──────────────────────────────────────


@router.post("/api/auth/invite", response_model=UserInvitationResponse)
@requires_log_commit
async def invite_user(
    req: InviteUserRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserInvitationResponse:
    """Create a pending user account and return a one-time setup URL.

    The invited user follows the setup URL to choose their own password and
    activate the account.  No password is accepted in this request.

    Required roles: ``root``, ``super_admin``.
    ``governed_modules`` is optional for admin (null = all modules).
    """
    current = await get_current_user(credentials)
    user_data = require_auth(current)
    require_role(user_data, "root", "super_admin")

    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")

    if not req.username:
        raise HTTPException(status_code=400, detail="username is required")

    # admin with governed_modules=None means access to ALL
    # modules in their domain. This is intentional — domain admins are the
    # subject-matter experts / domain administrators.

    existing = await run_in_threadpool(_cfg.PERSISTENCE.get_user_by_username, req.username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already taken")

    user_id = str(uuid.uuid4())
    # Create with empty password hash and active=False (pending setup)
    await run_in_threadpool(
        _cfg.PERSISTENCE.create_user,
        user_id,
        req.username,
        "",  # no password until setup-password is called
        req.role,
        req.governed_modules,
        False,  # active=False
    )

    token = generate_invite_token(user_id, req.username)
    _cfg.PERSISTENCE.set_user_invite_token(user_id, token, time.time() + _INVITE_TOKEN_TTL)
    base_url = os.environ.get("LUMINA_BASE_URL", "").rstrip("/")
    setup_url = f"{base_url}/?token={token}"

    email_sent = False
    if req.email:
        sent, _err = await run_in_threadpool(send_invite_email, req.email, req.username, setup_url)
        email_sent = sent

    event = build_trace_event(
        session_id="admin",
        actor_id=user_data["sub"],
        event_type="other",
        decision="user_invited",
        evidence_summary={
            "invited_user_id": user_id,
            "invited_username": req.username,
            "invited_role": req.role,
            "governed_modules": req.governed_modules or [],
            "email_sent": email_sent,
        },
    )
    try:
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )
    except Exception:
        log.debug("Could not write user_invited trace event")

    log.info("Invited user %s (%s) with role %s", req.username, user_id, req.role)
    return UserInvitationResponse(
        user_id=user_id,
        username=req.username,
        role=req.role,
        governed_modules=req.governed_modules or [],
        setup_token=token,
        setup_url=setup_url,
        email_sent=email_sent,
    )


@router.post("/api/auth/setup-password", response_model=TokenResponse)
@requires_log_commit
async def setup_password(req: SetupPasswordRequest) -> TokenResponse:
    """Activate a pending user account by setting a password.

    The ``token`` field must be the one-time setup token returned by
    ``POST /api/auth/invite``.  No JWT authentication is required — the token
    is the credential.  On success the account is activated and a JWT is
    returned so the user is immediately logged in.
    """
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_id = validate_invite_token(req.token)
    if user_id is None:
        raise HTTPException(status_code=403, detail="Invalid or expired setup token")

    new_hash = hash_password(req.new_password)
    pw_ok = await run_in_threadpool(_cfg.PERSISTENCE.update_user_password, user_id, new_hash)
    if not pw_ok:
        raise HTTPException(status_code=404, detail="User not found")

    await run_in_threadpool(_cfg.PERSISTENCE.activate_user, user_id)

    user = await run_in_threadpool(_cfg.PERSISTENCE.get_user, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found after activation")

    event = build_trace_event(
        session_id="admin",
        actor_id=user_id,
        event_type="other",
        decision="account_activated",
        evidence_summary={"user_id": user_id},
    )
    try:
        _cfg.PERSISTENCE.append_log_record(
            "admin", event,
            ledger_path=_cfg.PERSISTENCE.get_system_ledger_path("admin"),
        )
    except Exception:
        log.debug("Could not write account_activated trace event")

    token = create_scoped_jwt(
        user_id=user["user_id"],
        role=user["role"],
        governed_modules=user.get("governed_modules") or [],
        domain_roles=user.get("domain_roles") or {},
    )
    log.info("Account activated for user %s", user_id)
    return TokenResponse(access_token=token, user_id=user["user_id"], role=user["role"])
