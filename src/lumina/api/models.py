"""Pydantic request/response models for the Lumina API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Chat ─────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str | None = None
    thread_id: str | None = None
    message: str
    deterministic_response: bool = False
    turn_data_override: dict[str, Any] | None = None
    domain_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    holodeck: bool = False
    # ── Journal SVA ───────────────────────────────────────────
    # Device-local 32-byte hex salt used to hash named entities before
    # they reach the orchestrator.  Never persisted server-side.
    journal_entity_salt: str | None = None
    # Flag indicating this turn is in journal mode.  When True the server
    # extracts SVA heuristics from the text even if no salt is provided.
    journal_mode: bool = False


class ChatResponse(BaseModel):
    session_id: str
    response: str
    action: str
    prompt_type: str
    escalated: bool
    tool_results: list[dict[str, Any]] | None = None
    domain_id: str | None = None
    structured_content: dict[str, Any] | None = None
    transcript_seal: str | None = None
    transcript_seal_metadata: dict[str, Any] | None = None
    transcript_snapshot: list[dict[str, Any]] | None = None


# ── Thread routing ───────────────────────────────────────────

class ThreadRoutingPreflightRequest(BaseModel):
    message: str = Field(min_length=1)
    active_thread_id: str | None = None
    session_id: str | None = None


class ThreadRoutingCandidateResponse(BaseModel):
    thread_id: str
    summary_record_id: str
    score: float


class ThreadRoutingPreflightResponse(BaseModel):
    decision_id: str
    organization_id: str
    site_id: str
    actor_id: str
    decision: str
    thread_id: str
    source_thread_id: str | None = None
    policy_version: int
    confidence: float
    rationale_code: str
    operator_confirmation_required: bool
    operator_override: bool = False
    candidates: list[ThreadRoutingCandidateResponse]


class ThreadRoutingConfirmationRequest(BaseModel):
    action: str = "accept"


class ThreadRoutingConfirmationResponse(BaseModel):
    application_id: str
    decision_id: str
    thread_id: str
    source_thread_id: str | None = None
    decision: str
    operator_override: bool
    session_id: str


# ── Decision precedent ───────────────────────────────────────

class DecisionPrecedentPreflightRequest(BaseModel):
    message: str = Field(min_length=1)
    risk_class: str = Field(min_length=1)
    session_id: str | None = None


class DecisionPrecedentPreflightResponse(BaseModel):
    confidence_record_id: str
    organization_id: str
    site_id: str
    actor_id: str
    policy_version: int
    risk_class: str
    final_score: float
    tier: str
    rationale_codes: list[str]
    confirmation_required: bool
    escalation_record_id: str | None = None


class DecisionPrecedentConfirmationResponse(BaseModel):
    confirmation_id: str
    confidence_record_id: str
    tier: str


# ── Holodeck Sandbox ─────────────────────────────────────────

class HolodeckSimulateRequest(BaseModel):
    """Run a test message through the pipeline with proposed physics changes.

    Provide *either* ``staged_id`` (referencing a pending HITL staged command
    whose operation is ``update_domain_physics``) *or* ``physics_override``
    (an inline dict of physics fields to merge onto the live physics).
    """
    staged_id: str | None = None
    physics_override: dict[str, Any] | None = None
    domain_id: str
    message: str
    turn_data_override: dict[str, Any] | None = None
    deterministic_response: bool = True


class HolodeckSimulateResponse(BaseModel):
    session_id: str
    response: str
    action: str
    prompt_type: str
    escalated: bool
    tool_results: list[dict[str, Any]] | None = None
    domain_id: str | None = None
    structured_content: dict[str, Any] | None = None
    sandbox_physics: dict[str, Any] | None = None
    physics_diff: dict[str, Any] | None = None
    live_physics_hash: str | None = None
    sandbox_physics_hash: str | None = None
    staged_id: str | None = None


# ── Tools ────────────────────────────────────────────────────

class ToolRequest(BaseModel):
    payload: dict[str, Any]


class ToolResponse(BaseModel):
    tool_id: str
    result: dict[str, Any]


class ToolRequestWithDomain(BaseModel):
    payload: dict[str, Any]
    domain_id: str | None = None


# ── System Log / Manifest ───────────────────────────────────────────

class SystemLogValidateResponse(BaseModel):
    result: dict[str, Any]


class ManifestCheckResponse(BaseModel):
    passed: bool
    ok_count: int
    pending_count: int
    missing_count: int
    mismatch_count: int
    entries: list[dict[str, Any]]


class ManifestRegenResponse(BaseModel):
    updated_count: int
    missing_paths: list[str]
    manifest_path: str


# ── Auth ─────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    governed_modules: list[str] | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    organization_id: str | None = None
    site_id: str | None = None
    device_id: str | None = None


class OperatingMembership(BaseModel):
    """One organization and the sites an actor may operate from."""

    organization_id: str
    site_ids: list[str] = Field(min_length=1)
    site_roles: dict[str, str] = Field(default_factory=dict)


class OperatingContextSwitchRequest(BaseModel):
    organization_id: str
    site_id: str
    device_id: str | None = None


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: str
    governed_modules: list[str]
    active: bool
    operating_memberships: list[OperatingMembership] = Field(default_factory=list)


# ── Admin ────────────────────────────────────────────────────

class UpdateUserRequest(BaseModel):
    role: str | None = None
    governed_modules: list[str] | None = None
    domain_roles: dict[str, str] | None = None  # module_id → domain_role_id
    operating_memberships: list[OperatingMembership] | None = None


class RevokeRequest(BaseModel):
    user_id: str | None = None


class PasswordResetRequest(BaseModel):
    user_id: str | None = None
    new_password: str


class DomainCommitRequest(BaseModel):
    domain_id: str
    actor_id: str | None = None
    summary: str | None = None


class DomainPhysicsUpdateRequest(BaseModel):
    updates: dict[str, Any]
    summary: str


class SessionUnlockRequest(BaseModel):
    pin: str


class SessionResumeRequest(BaseModel):
    """Client-side transcript + HMAC seal for session resumption."""
    transcript: list[dict[str, Any]]
    metadata: dict[str, Any]
    seal: str


class EscalationResolveRequest(BaseModel):
    decision: str  # "approve", "reject", "defer"
    reasoning: str
    generate_pin: bool = False          # generate OTP so child can self-unlock
    intervention_notes: str | None = None  # teacher's description of what they did
    generate_proposal: bool = False     # trigger domain-physics proposal from notes


class AdminCommandRequest(BaseModel):
    instruction: str = ""
    operation: str | None = None
    params: dict[str, Any] | None = None
    domain_id: str | None = None


class CommandResolveRequest(BaseModel):
    action: str  # "accept" | "reject" | "modify"
    modified_schema: dict[str, Any] | None = None


class LogicScrapeRequest(BaseModel):
    prompt: str
    iterations: int | None = None
    domain_id: str


# ── Invite / onboarding ──────────────────────────────────────

class InviteUserRequest(BaseModel):
    username: str
    role: str = "user"
    governed_modules: list[str] | None = None
    email: str | None = None  # used for SMTP dispatch only; never persisted


class SetupPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserInvitationResponse(BaseModel):
    user_id: str
    username: str
    role: str
    governed_modules: list[str]
    setup_token: str
    setup_url: str
    email_sent: bool
