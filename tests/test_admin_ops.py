"""Unit tests for admin ops execute() handlers.

Covers operation branches in:
  - lumina.api.routes.ops.admin_ingestion
  - lumina.api.routes.ops.admin_escalations
  - lumina.api.routes.ops.admin_physics
  - lumina.api.routes.ops.admin_invite

All tests use a deterministic fake AdminOperationContext and mock
service/persistence objects.  No live model, persistence, network, or secrets.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lumina.api.admin_context import AdminOperationContext


# ─── helpers ─────────────────────────────────────────────────────────────────


def _run(coro) -> Any:
    return asyncio.run(coro)


def _user(role: str = "root", governed: list | None = None) -> dict:
    u: dict[str, Any] = {"sub": f"{role}-1", "role": role}
    if governed is not None:
        u["governed_modules"] = governed
    return u


async def _passthrough_threadpool(fn, *args, **kwargs):
    """Sync threadpool shim — calls the function directly."""
    return fn(*args, **kwargs)


def _fake_ctx(
    *,
    persistence: Any = None,
    domain_registry: Any = None,
    can_govern: bool = True,
) -> AdminOperationContext:
    """Build a minimal AdminOperationContext for unit tests."""
    p = persistence or MagicMock()
    dr = domain_registry or MagicMock()
    return AdminOperationContext(
        persistence=p,
        domain_registry=dr,
        can_govern_domain=lambda user, domain_id, registry=None: can_govern,
        build_commitment_record=MagicMock(return_value={"record_id": "rec-1"}),
        map_role_to_actor_role=lambda role: role,
        build_trace_event=MagicMock(return_value={"record_id": "ev-1"}),
        build_domain_role_assignment=MagicMock(),
        build_domain_role_revocation=MagicMock(),
        canonical_sha256=MagicMock(return_value="sha256-fake"),
        resolve_user_profile_path=MagicMock(),
        has_domain_capability=MagicMock(return_value=True),
        has_escalation_capability=MagicMock(return_value=True),
        run_in_threadpool=_passthrough_threadpool,
    )


# ═══════════════════════════════════════════════════════════════════════════
# admin_ingestion.execute
# ═══════════════════════════════════════════════════════════════════════════

from lumina.api.routes.ops.admin_ingestion import execute as ingest_execute


def _ingest_svc(records: list | None = None, record: dict | None = None, updated: dict | None = None):
    svc = MagicMock()
    svc.list_records.return_value = records or []
    svc.get_record.return_value = record
    svc.review_interpretation.return_value = updated or {"status": "approved"}
    return svc


class TestAdminIngestionExecute:

    @pytest.mark.unit
    def test_list_ingestions_root_returns_all(self) -> None:
        records = [
            {"ingestion_id": "a", "domain_id": "education"},
            {"ingestion_id": "b", "domain_id": "agriculture"},
        ]
        svc = _ingest_svc(records=records)
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            result = _run(ingest_execute("list_ingestions", {}, _user("root"), _fake_ctx()))
        assert result["count"] == 2

    @pytest.mark.unit
    def test_list_ingestions_admin_filtered_by_governed(self) -> None:
        records = [
            {"ingestion_id": "a", "domain_id": "education"},
            {"ingestion_id": "b", "domain_id": "agriculture"},
        ]
        svc = _ingest_svc(records=records)
        admin = _user("admin", governed=["education"])
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            result = _run(ingest_execute("list_ingestions", {}, admin, _fake_ctx()))
        assert result["count"] == 1
        assert result["records"][0]["domain_id"] == "education"

    @pytest.mark.unit
    def test_review_ingestion_missing_id_raises_422(self) -> None:
        ctx = _fake_ctx()
        with pytest.raises(HTTPException) as exc:
            _run(ingest_execute("review_ingestion", {}, _user("root"), ctx))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_review_ingestion_not_found_raises_404(self) -> None:
        svc = _ingest_svc(record=None)
        ctx = _fake_ctx()
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_execute("review_ingestion", {"ingestion_id": "x"}, _user("root"), ctx))
        assert exc.value.status_code == 404

    @pytest.mark.unit
    def test_review_ingestion_returns_record(self) -> None:
        record = {"ingestion_id": "doc-1", "status": "pending_review"}
        svc = _ingest_svc(record=record)
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            result = _run(ingest_execute("review_ingestion", {"ingestion_id": "doc-1"}, _user("root"), _fake_ctx()))
        assert result["record"]["ingestion_id"] == "doc-1"

    @pytest.mark.unit
    def test_approve_interpretation_missing_params_raises_422(self) -> None:
        ctx = _fake_ctx()
        with pytest.raises(HTTPException) as exc:
            _run(ingest_execute("approve_interpretation", {}, _user("root"), ctx))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_approve_interpretation_wrong_role_raises_403(self) -> None:
        ctx = _fake_ctx()
        with pytest.raises(HTTPException) as exc:
            _run(ingest_execute(
                "approve_interpretation",
                {"ingestion_id": "doc-1", "interpretation_id": "i-1"},
                _user("user"),
                ctx,
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_approve_interpretation_value_error_raises_400(self) -> None:
        svc = _ingest_svc()
        svc.review_interpretation.side_effect = ValueError("wrong state")
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_execute(
                    "approve_interpretation",
                    {"ingestion_id": "doc-1", "interpretation_id": "i-1"},
                    _user("root"),
                    _fake_ctx(),
                ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_approve_interpretation_success(self) -> None:
        svc = _ingest_svc(updated={"status": "approved"})
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            result = _run(ingest_execute(
                "approve_interpretation",
                {"ingestion_id": "doc-1", "interpretation_id": "i-1"},
                _user("root"),
                _fake_ctx(),
            ))
        assert result["status"] == "approved"

    @pytest.mark.unit
    def test_reject_ingestion_missing_id_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(ingest_execute("reject_ingestion", {}, _user("root"), _fake_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_reject_ingestion_wrong_role_raises_403(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(ingest_execute(
                "reject_ingestion",
                {"ingestion_id": "doc-1"},
                _user("user"),
                _fake_ctx(),
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_reject_ingestion_success(self) -> None:
        svc = _ingest_svc(updated={"status": "rejected"})
        with patch("lumina.api.routes.ops.admin_ingestion._get_ingest_service", return_value=svc):
            result = _run(ingest_execute(
                "reject_ingestion",
                {"ingestion_id": "doc-1", "reason": "out of scope"},
                _user("root"),
                _fake_ctx(),
            ))
        assert result["status"] == "rejected"

    @pytest.mark.unit
    def test_unknown_operation_returns_none(self) -> None:
        result = _run(ingest_execute("delete_everything", {}, _user("root"), _fake_ctx()))
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# admin_escalations.execute
# ═══════════════════════════════════════════════════════════════════════════

from lumina.api.routes.ops.admin_escalations import execute as esc_execute
from lumina.core.domain_registry import DomainNotFoundError


def _esc_ctx(
    *,
    escalations: list | None = None,
    log_records: list | None = None,
    can_govern: bool = True,
    domain_not_found: bool = False,
) -> AdminOperationContext:
    p = MagicMock()
    p.query_escalations.return_value = escalations or []
    p.query_log_records.return_value = log_records or []

    dr = MagicMock()
    if domain_not_found:
        dr.resolve_domain_id.side_effect = DomainNotFoundError("unknown domain", [])
    else:
        dr.resolve_domain_id.return_value = "education"

    ctx = _fake_ctx(persistence=p, domain_registry=dr, can_govern=can_govern)
    return ctx


class TestAdminEscalationsExecute:

    @pytest.mark.unit
    def test_resolve_escalation_invalid_resolution_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(esc_execute(
                "resolve_escalation",
                {"escalation_id": "esc-1", "resolution": "INVALID"},
                _user("root"),
                _esc_ctx(),
            ))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_resolve_escalation_missing_id_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(esc_execute(
                "resolve_escalation",
                {"resolution": "approved"},
                _user("root"),
                _esc_ctx(),
            ))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_resolve_escalation_success(self) -> None:
        result = _run(esc_execute(
            "resolve_escalation",
            {"escalation_id": "esc-1", "resolution": "approved", "rationale": "looks good"},
            _user("root"),
            _esc_ctx(),
        ))
        assert result["escalation_id"] == "esc-1"
        assert result["resolution"] == "approved"

    @pytest.mark.unit
    def test_list_escalations_admin_domain_not_found_raises_400(self) -> None:
        ctx = _esc_ctx(domain_not_found=True)
        with pytest.raises(HTTPException) as exc:
            _run(esc_execute(
                "list_escalations",
                {"domain_id": "unknown"},
                _user("admin"),
                ctx,
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_list_escalations_admin_not_governing_raises_403(self) -> None:
        ctx = _esc_ctx(can_govern=False)
        with pytest.raises(HTTPException) as exc:
            _run(esc_execute(
                "list_escalations",
                {"domain_id": "education"},
                _user("admin"),
                ctx,
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_list_escalations_admin_filtered_by_governed(self) -> None:
        escalations = [
            {"record_id": "e1", "domain_id": "education"},
            {"record_id": "e2", "domain_id": "agriculture"},
        ]
        # get_model_pack_id is called on each escalation — patch it
        with patch(
            "lumina.api.routes.ops.admin_escalations.get_model_pack_id",
            side_effect=lambda r: r.get("domain_id", ""),
        ):
            result = _run(esc_execute(
                "list_escalations",
                {},
                _user("admin", governed=["education"]),
                _esc_ctx(escalations=escalations),
            ))
        assert result["count"] == 1

    @pytest.mark.unit
    def test_list_escalations_root_returns_all(self) -> None:
        escalations = [{"record_id": "e1"}, {"record_id": "e2"}]
        result = _run(esc_execute(
            "list_escalations",
            {},
            _user("root"),
            _esc_ctx(escalations=escalations),
        ))
        assert result["count"] == 2

    @pytest.mark.unit
    def test_explain_reasoning_missing_event_id_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(esc_execute("explain_reasoning", {}, _user("root"), _esc_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_explain_reasoning_not_found_raises_404(self) -> None:
        ctx = _esc_ctx(log_records=[{"record_id": "other"}])
        with pytest.raises(HTTPException) as exc:
            _run(esc_execute(
                "explain_reasoning",
                {"event_id": "missing"},
                _user("root"),
                ctx,
            ))
        assert exc.value.status_code == 404

    @pytest.mark.unit
    def test_explain_reasoning_returns_record(self) -> None:
        ctx = _esc_ctx(log_records=[{"record_id": "ev-1", "event_type": "audit"}])
        result = _run(esc_execute(
            "explain_reasoning",
            {"event_id": "ev-1"},
            _user("root"),
            ctx,
        ))
        assert result["record"]["record_id"] == "ev-1"

    @pytest.mark.unit
    def test_unknown_operation_returns_none(self) -> None:
        result = _run(esc_execute("wipe_log", {}, _user("root"), _esc_ctx()))
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# admin_invite.execute
# ═══════════════════════════════════════════════════════════════════════════

from lumina.api.routes.ops.admin_invite import execute as invite_execute


def _invite_ctx(*, existing_user: dict | None = None) -> AdminOperationContext:
    p = MagicMock()
    p.get_user_by_username.return_value = existing_user
    p.create_user.return_value = None
    p.set_user_invite_token.return_value = None
    p.append_log_record.return_value = None
    p.get_system_ledger_path.return_value = "/fake/ledger.jsonl"
    p.update_user_domain_roles.return_value = None

    ctx = _fake_ctx(persistence=p, domain_registry=None)
    return ctx


class TestAdminInviteExecute:

    @pytest.mark.unit
    def test_non_matching_operation_returns_none(self) -> None:
        result = _run(invite_execute("update_user_role", {}, _user("root"), _invite_ctx()))
        assert result is None

    @pytest.mark.unit
    def test_wrong_role_raises_403(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute("invite_user", {"username": "alice"}, _user("user"), _invite_ctx()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_empty_username_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute("invite_user", {"username": ""}, _user("root"), _invite_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_invalid_role_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute(
                "invite_user",
                {"username": "alice", "role": "god_mode"},
                _user("root"),
                _invite_ctx(),
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_admin_with_governed_modules_empty_raises_400(self) -> None:
        """admin role with governed_modules=[] is explicitly rejected."""
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute(
                "invite_user",
                {"username": "alice", "role": "admin", "governed_modules": []},
                _user("root"),
                _invite_ctx(),
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_admin_inviting_non_user_role_raises_403(self) -> None:
        """Domain admin cannot invite with 'admin' role."""
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute(
                "invite_user",
                {"username": "alice", "role": "admin"},
                _user("admin"),
                _invite_ctx(),
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_admin_inviting_outside_governed_scope_raises_403(self) -> None:
        admin = _user("admin", governed=["edu/algebra"])
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute(
                "invite_user",
                {"username": "alice", "role": "user", "governed_modules": ["agri/crop"]},
                admin,
                _invite_ctx(),
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_username_already_taken_raises_409(self) -> None:
        existing = {"user_id": "u-existing", "username": "alice"}
        with pytest.raises(HTTPException) as exc:
            _run(invite_execute(
                "invite_user",
                {"username": "alice", "role": "user"},
                _user("root"),
                _invite_ctx(existing_user=existing),
            ))
        assert exc.value.status_code == 409

    @pytest.mark.unit
    def test_root_invite_success_returns_user_info(self) -> None:
        with patch("lumina.api.routes.ops.admin_invite.send_invite_email", return_value=(False, None)):
            result = _run(invite_execute(
                "invite_user",
                {"username": "newuser", "role": "user"},
                _user("root"),
                _invite_ctx(),
            ))
        assert result["username"] == "newuser"
        assert result["role"] == "user"
        assert "setup_url" in result
        assert "user_id" in result

    @pytest.mark.unit
    def test_email_sent_when_email_provided(self) -> None:
        with patch("lumina.api.routes.ops.admin_invite.send_invite_email", return_value=(True, None)) as mock_email:
            result = _run(invite_execute(
                "invite_user",
                {"username": "newuser", "role": "user", "email": "new@example.com"},
                _user("root"),
                _invite_ctx(),
            ))
        mock_email.assert_called_once()
        assert result["email_sent"] is True


# ═══════════════════════════════════════════════════════════════════════════
# admin_physics.execute
# ═══════════════════════════════════════════════════════════════════════════

from lumina.api.routes.ops.admin_physics import execute as physics_execute


def _physics_ctx(
    *,
    can_govern: bool = True,
    domain_not_found: bool = False,
    domain_physics: dict | None = None,
    modules: list | None = None,
) -> AdminOperationContext:
    p = MagicMock()
    p.load_domain_physics.return_value = domain_physics or {"id": "edu", "version": "1", "modules": []}
    p.append_log_record.return_value = None
    p.get_domain_ledger_path.return_value = "/fake/ledger.jsonl"

    dr = MagicMock()
    dr._repo_root = "/fake/repo"
    if domain_not_found:
        dr.resolve_domain_id.side_effect = DomainNotFoundError("unknown", [])
    else:
        dr.resolve_domain_id.return_value = "education"
    dr.get_runtime_context.return_value = {"domain_physics_path": "/fake/physics.json"}
    dr.list_modules_for_domain.return_value = modules or []

    return _fake_ctx(persistence=p, domain_registry=dr, can_govern=can_govern)


class TestAdminPhysicsExecute:

    @pytest.mark.unit
    def test_update_domain_physics_missing_params_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute("update_domain_physics", {}, _user("root"), _physics_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_update_domain_physics_admin_not_governing_raises_403(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute(
                "update_domain_physics",
                {"domain_id": "edu", "updates": {"label": "new"}},
                _user("admin"),
                _physics_ctx(can_govern=False),
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_update_domain_physics_domain_not_found_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute(
                "update_domain_physics",
                {"domain_id": "unknown", "updates": {"label": "x"}},
                _user("root"),
                _physics_ctx(domain_not_found=True),
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_update_domain_physics_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            physics_path = Path(tmp) / "physics.json"
            physics_path.write_text('{"id": "edu", "version": "1"}', encoding="utf-8")

            p = MagicMock()
            p.load_domain_physics.return_value = {"id": "edu", "version": "1"}
            p.append_log_record.return_value = None
            p.get_domain_ledger_path.return_value = str(Path(tmp) / "ledger.jsonl")

            dr = MagicMock()
            dr._repo_root = tmp
            dr.resolve_domain_id.return_value = "education"
            dr.get_runtime_context.return_value = {"domain_physics_path": str(physics_path)}

            ctx = _fake_ctx(persistence=p, domain_registry=dr)
            result = _run(physics_execute(
                "update_domain_physics",
                {"domain_id": "edu", "updates": {"label": "Updated"}},
                _user("root"),
                ctx,
                original_instruction="update label",
            ))
        assert "subject_hash" in result
        assert result["record_id"] == "rec-1"

    @pytest.mark.unit
    def test_commit_domain_physics_missing_id_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute("commit_domain_physics", {}, _user("root"), _physics_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_commit_domain_physics_admin_not_governing_raises_403(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute(
                "commit_domain_physics",
                {"domain_id": "edu"},
                _user("admin"),
                _physics_ctx(can_govern=False),
            ))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_commit_domain_physics_domain_not_found_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute(
                "commit_domain_physics",
                {"domain_id": "unknown"},
                _user("root"),
                _physics_ctx(domain_not_found=True),
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_commit_domain_physics_success(self) -> None:
        result = _run(physics_execute(
            "commit_domain_physics",
            {"domain_id": "edu"},
            _user("root"),
            _physics_ctx(),
        ))
        assert result["operation"] == "commit_domain_physics"
        assert "subject_hash" in result

    @pytest.mark.unit
    def test_get_domain_physics_missing_id_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute("get_domain_physics", {}, _user("root"), _physics_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_get_domain_physics_domain_not_found_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute(
                "get_domain_physics",
                {"domain_id": "unknown"},
                _user("root"),
                _physics_ctx(domain_not_found=True),
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_get_domain_physics_no_modules_returns_empty(self) -> None:
        result = _run(physics_execute(
            "get_domain_physics",
            {"domain_id": "edu"},
            _user("root"),
            _physics_ctx(modules=[]),
        ))
        assert result["count"] == 0
        assert result["physics"] == []

    @pytest.mark.unit
    def test_get_domain_physics_module_without_path_skipped(self) -> None:
        modules = [{"module_id": "edu/algebra", "domain_physics_path": ""}]
        result = _run(physics_execute(
            "get_domain_physics",
            {"domain_id": "edu"},
            _user("root"),
            _physics_ctx(modules=modules),
        ))
        assert result["count"] == 0

    @pytest.mark.unit
    def test_get_domain_physics_with_module_reads_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dp_path = Path(tmp) / "algebra.json"
            dp_path.write_text(
                json.dumps({"label": "Algebra", "version": "2", "domain": "education"}),
                encoding="utf-8",
            )
            modules = [{"module_id": "edu/algebra", "domain_physics_path": "algebra.json"}]
            dr = MagicMock()
            dr._repo_root = tmp
            dr.resolve_domain_id.return_value = "education"
            dr.list_modules_for_domain.return_value = modules
            ctx = _fake_ctx(domain_registry=dr)
            result = _run(physics_execute(
                "get_domain_physics",
                {"domain_id": "edu"},
                _user("root"),
                ctx,
            ))
        assert result["count"] == 1
        assert result["physics"][0]["label"] == "Algebra"

    @pytest.mark.unit
    def test_module_status_missing_id_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute("module_status", {}, _user("root"), _physics_ctx()))
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_module_status_domain_not_found_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc:
            _run(physics_execute(
                "module_status",
                {"domain_id": "unknown"},
                _user("root"),
                _physics_ctx(domain_not_found=True),
            ))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_module_status_success(self) -> None:
        result = _run(physics_execute(
            "module_status",
            {"domain_id": "edu"},
            _user("root"),
            _physics_ctx(domain_physics={"id": "edu", "version": "3", "modules": [{"module_id": "edu/algebra"}]}),
        ))
        assert result["operation"] == "module_status"
        assert result["version"] == "3"
        assert "edu/algebra" in result["modules"]

    @pytest.mark.unit
    def test_unknown_operation_returns_none(self) -> None:
        result = _run(physics_execute("delete_physics", {}, _user("root"), _physics_ctx()))
        assert result is None
