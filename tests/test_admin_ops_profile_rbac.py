"""Tests for admin operation handlers: admin_profile.execute and admin_rbac.execute.

Uses a mocked AdminOperationContext to avoid live persistence or API services.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from lumina.api.admin_context import AdminOperationContext
from lumina.api.routes.ops import admin_profile, admin_rbac


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_ctx() -> AdminOperationContext:
    """Build a minimal AdminOperationContext with mocked services."""
    persistence = MagicMock()
    persistence.load_profile.return_value = None
    persistence.load_subject_profile.return_value = {}
    persistence.save_profile.return_value = None
    persistence.save_subject_profile.return_value = None
    persistence.append_log_record.return_value = None
    persistence.get_system_ledger_path.return_value = "/tmp/test.jsonl"
    persistence.get_domain_ledger_path.return_value = "/tmp/domain.jsonl"
    persistence.get_user.return_value = {
        "sub": "user-target", "username": "target", "role": "user",
        "domain_roles": {"education/algebra-v1": "student"},
    }
    persistence.update_user_role.return_value = None
    persistence.deactivate_user.return_value = None
    persistence.update_user_domain_roles.return_value = None

    domain_registry = MagicMock()
    domain_registry.resolve_default_for_user.return_value = "education"

    return AdminOperationContext(
        persistence=persistence,
        domain_registry=domain_registry,
        can_govern_domain=MagicMock(return_value=True),
        build_commitment_record=MagicMock(
            return_value={"record_id": "test-record-001"}
        ),
        map_role_to_actor_role=MagicMock(return_value="domain_authority"),
        build_trace_event=MagicMock(return_value={}),
        build_domain_role_assignment=MagicMock(
            return_value={"record_id": "role-assign-001"}
        ),
        build_domain_role_revocation=MagicMock(
            return_value={"record_id": "role-revoke-001"}
        ),
        canonical_sha256=MagicMock(return_value="abc123"),
        resolve_user_profile_path=MagicMock(return_value="/tmp/profile.yaml"),
        has_domain_capability=MagicMock(return_value=False),
        has_escalation_capability=MagicMock(return_value=False),
    )


def _root_user(sub: str = "root-001") -> dict[str, Any]:
    return {"sub": sub, "role": "root"}


def _admin_user(sub: str = "admin-001") -> dict[str, Any]:
    return {"sub": sub, "role": "admin"}


def _teacher_user(sub: str = "teacher-001") -> dict[str, Any]:
    return {"sub": sub, "role": "teacher"}


def _student_user(sub: str = "student-001") -> dict[str, Any]:
    return {"sub": sub, "role": "user"}


def _run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# admin_profile.execute
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestViewMyProfile:
    def test_view_my_profile_returns_user_id(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_profile.execute(
            "view_my_profile", {}, _student_user(), ctx,
        ))
        assert result is not None
        assert result["operation"] == "view_my_profile"
        assert result["user_id"] == "student-001"

    def test_view_my_profile_with_domain_key(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_profile.execute(
            "view_my_profile",
            {"domain_id": "education"},
            _student_user(),
            ctx,
        ))
        assert result is not None
        assert "preferences" in result

    def test_view_my_profile_has_assigned_modules(self) -> None:
        ctx = _make_ctx()
        ctx.persistence.load_profile.return_value = {
            "preferences": {"theme": "dark"},
            "modules": {"algebra-v1": {"turn_count": 5}},
        }
        result = _run(admin_profile.execute(
            "view_my_profile", {}, _student_user(), ctx,
        ))
        assert result is not None
        assert "algebra-v1" in result["assigned_modules"]
        assert result["module_summaries"]["algebra-v1"]["turn_count"] == 5

    def test_view_my_profile_unknown_operation_returns_none(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_profile.execute(
            "totally_unknown_op", {}, _student_user(), ctx,
        ))
        assert result is None


@pytest.mark.unit
class TestUpdateUserPreferences:
    def test_self_update_allowed(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_profile.execute(
            "update_user_preferences",
            {"updates": {"theme": "dark"}, "domain_id": "education"},
            _student_user(),
            ctx,
        ))
        assert result is not None
        assert result["operation"] == "update_user_preferences"
        assert "theme" in result["updated_fields"]

    def test_cross_user_update_requires_elevated_role(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_profile.execute(
                "update_user_preferences",
                {"target_user_id": "other-user", "updates": {"theme": "dark"}},
                _student_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 403

    def test_root_can_update_other_user(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_profile.execute(
            "update_user_preferences",
            {"target_user_id": "other-user", "updates": {"lang": "en"}},
            _root_user(),
            ctx,
        ))
        assert result is not None
        assert result["user_id"] == "other-user"

    def test_empty_updates_raises_422(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_profile.execute(
                "update_user_preferences",
                {"updates": {}},
                _student_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 422

    def test_note_added_for_cross_user_update(self) -> None:
        ctx = _make_ctx()
        ctx.persistence.load_profile.return_value = {}
        result = _run(admin_profile.execute(
            "update_user_preferences",
            {
                "target_user_id": "other-user",
                "updates": {"pref": "val"},
                "note": "Admin override",
            },
            _root_user(),
            ctx,
        ))
        assert result is not None
        # load_profile was called for the target user
        ctx.persistence.save_profile.assert_called()


# ═══════════════════════════════════════════════════════════════════════════════
# admin_rbac.execute
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestUpdateUserRole:
    def test_root_can_update_user_role(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_rbac.execute(
            "update_user_role",
            {"user_id": "user-target", "new_role": "operator"},
            _root_user(),
            ctx,
        ))
        assert result is not None
        assert result["new_role"] == "operator"

    def test_non_root_cannot_update_role(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "update_user_role",
                {"user_id": "user-target", "new_role": "teacher"},
                _admin_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 403

    def test_invalid_role_raises_422(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "update_user_role",
                {"user_id": "user-target", "new_role": "superduper"},
                _root_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 422

    def test_update_role_with_governed_modules(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_rbac.execute(
            "update_user_role",
            {"user_id": "user-target", "new_role": "admin",
             "governed_modules": ["education/algebra-v1"]},
            _root_user(),
            ctx,
        ))
        assert result is not None
        assert result["governed_modules"] == ["education/algebra-v1"]


@pytest.mark.unit
class TestDeactivateUser:
    def test_root_can_deactivate(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_rbac.execute(
            "deactivate_user",
            {"user_id": "other-user"},
            _root_user(),
            ctx,
        ))
        assert result is not None
        assert result["user_id"] == "other-user"

    def test_non_root_cannot_deactivate(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "deactivate_user",
                {"user_id": "other-user"},
                _admin_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 403

    def test_cannot_deactivate_self(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "deactivate_user",
                {"user_id": "root-001"},
                _root_user("root-001"),
                ctx,
            ))
        assert exc_info.value.status_code == 400

    def test_missing_user_id_raises_422(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "deactivate_user",
                {},
                _root_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 422


@pytest.mark.unit
class TestAssignDomainRole:
    def test_admin_can_assign_domain_role(self) -> None:
        ctx = _make_ctx()
        ctx.domain_registry.resolve_domain_id.side_effect = KeyError("not found")
        result = _run(admin_rbac.execute(
            "assign_domain_role",
            {
                "user_id": "user-target",
                "module_id": "education/algebra-v1",
                "domain_role": "student",
            },
            _root_user(),
            ctx,
        ))
        assert result is not None
        assert result["module_id"] == "education/algebra-v1"
        assert result["domain_role"] == "student"

    def test_missing_params_raises_422(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "assign_domain_role",
                {"user_id": "user-target"},  # missing module_id and domain_role
                _root_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 422

    def test_insufficient_permissions_raises_403(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "assign_domain_role",
                {"user_id": "u", "module_id": "edu/m1", "domain_role": "student"},
                _student_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 403

    def test_user_not_found_raises_404(self) -> None:
        ctx = _make_ctx()
        ctx.persistence.get_user.return_value = None
        ctx.domain_registry.resolve_domain_id.side_effect = KeyError("not found")
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "assign_domain_role",
                {"user_id": "ghost", "module_id": "edu/m1", "domain_role": "student"},
                _root_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 404


@pytest.mark.unit
class TestRevokeDomainRole:
    def test_root_can_revoke_domain_role(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_rbac.execute(
            "revoke_domain_role",
            {"user_id": "user-target", "module_id": "education/algebra-v1"},
            _root_user(),
            ctx,
        ))
        assert result is not None
        assert result["module_id"] == "education/algebra-v1"

    def test_missing_params_raises_422(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "revoke_domain_role",
                {"user_id": "user-target"},  # missing module_id
                _root_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 422

    def test_insufficient_permissions_raises_403(self) -> None:
        ctx = _make_ctx()
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "revoke_domain_role",
                {"user_id": "u", "module_id": "edu/m1"},
                _student_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 403

    def test_user_not_found_raises_404(self) -> None:
        ctx = _make_ctx()
        ctx.persistence.get_user.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            _run(admin_rbac.execute(
                "revoke_domain_role",
                {"user_id": "ghost", "module_id": "edu/m1"},
                _root_user(),
                ctx,
            ))
        assert exc_info.value.status_code == 404

    def test_unknown_operation_returns_none(self) -> None:
        ctx = _make_ctx()
        result = _run(admin_rbac.execute(
            "unknown_op", {}, _root_user(), ctx,
        ))
        assert result is None
