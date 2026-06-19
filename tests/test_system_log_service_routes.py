"""Unit tests for system-log service routes.

Covers all RBAC and scoping branches in:
  - lumina.services.system_log.routes  (query_log_records, list_log_sessions,
                                        get_log_record, query_warnings,
                                        query_alerts)
  - lumina.services.system_log.events_routes  (get_sse_token, _validate_sse_token,
                                               _event_visible_to_user,
                                               _classify_sse_event, _format_sse)

No live persistence, network, or model.  Auth and persistence calls are
patched or bypassed via monkeypatching.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# ─── system-log routes ───────────────────────────────────────────────────────

from lumina.services.system_log.routes import (
    get_log_record,
    list_log_sessions,
    query_alerts,
    query_log_records,
    query_warnings,
)

# ─── events routes helpers ───────────────────────────────────────────────────

from lumina.services.system_log.events_routes import (
    _SSE_TOKEN_TTL,
    _classify_sse_event,
    _event_visible_to_user,
    _format_sse,
    _sse_tokens,
    _validate_sse_token,
    get_sse_token,
    _hash_token,
)
from lumina.system_log.event_payload import LogEvent, LogLevel


# ─── helpers ─────────────────────────────────────────────────────────────────


def _run(coro) -> Any:
    return asyncio.run(coro)


def _user(role: str = "root", governed: list | None = None, domain_roles: dict | None = None) -> dict:
    u: dict[str, Any] = {"sub": f"{role}-1", "role": role}
    if governed is not None:
        u["governed_modules"] = governed
    if domain_roles is not None:
        u["domain_roles"] = domain_roles
    return u


def _fake_creds() -> Any:
    return SimpleNamespace(credentials="fake-tok")


def _patch_auth(user: dict, route_module: str = "lumina.services.system_log.routes"):
    """Context manager: patch get_current_user + require_auth for a route module."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch(f"{route_module}.get_current_user", new=AsyncMock(return_value=user)),
            patch(f"{route_module}.require_auth", return_value=user),
        ):
            yield

    return _ctx()


async def _run_in_tp_passthrough(fn, *args, **kwargs):
    """Drop-in for run_in_threadpool that calls the function directly."""
    return fn(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# query_log_records
# ═══════════════════════════════════════════════════════════════════════════


class TestQueryLogRecords:

    @pytest.mark.unit
    def test_root_returns_all_records(self) -> None:
        """root role bypasses all scoping and returns records."""
        records = [{"record_id": "r1", "record_type": "TraceEvent"}]
        fake_persistence = MagicMock()
        fake_persistence.query_log_records.return_value = records

        with (
            _patch_auth(_user("root")),
            patch("lumina.services.system_log.routes._cfg") as mock_cfg,
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
        ):
            result = _run(query_log_records(credentials=_fake_creds()))

        assert result == records

    @pytest.mark.unit
    def test_operator_returns_records(self) -> None:
        """operator role is in the allowed set."""
        records = [{"record_id": "r2"}]
        with (
            _patch_auth(_user("operator")),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
        ):
            result = _run(query_log_records(credentials=_fake_creds()))
        assert result == records

    @pytest.mark.unit
    def test_admin_no_governed_modules_passes(self) -> None:
        """admin with no governed_modules sees everything."""
        records = [{"record_id": "r3"}]
        with (
            _patch_auth(_user("admin", governed=[])),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
        ):
            result = _run(query_log_records(credentials=_fake_creds(), domain_id="education"))
        assert result == records

    @pytest.mark.unit
    def test_admin_governed_modules_domain_level_key_passes(self) -> None:
        """admin with governed list: top-level domain key (no '/') is not blocked."""
        records = [{"record_id": "r4"}]
        with (
            _patch_auth(_user("admin", governed=["education"])),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
        ):
            # 'education' has no '/' so the module-level guard is skipped
            result = _run(query_log_records(credentials=_fake_creds(), domain_id="education"))
        assert result == records

    @pytest.mark.unit
    def test_admin_governed_modules_module_outside_scope_raises_403(self) -> None:
        """admin with governed list: module-level domain_id not in governed → 403."""
        with (
            _patch_auth(_user("admin", governed=["edu/algebra"])),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=[])),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(query_log_records(credentials=_fake_creds(), domain_id="agri/crop-planning"))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_user_role_raises_403(self) -> None:
        """Non-admin, non-operator role → 403."""
        with _patch_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(query_log_records(credentials=_fake_creds()))
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# list_log_sessions
# ═══════════════════════════════════════════════════════════════════════════


class TestListLogSessions:

    @pytest.mark.unit
    def test_root_returns_sessions(self) -> None:
        sessions = [{"session_id": "s1"}]
        with (
            _patch_auth(_user("root")),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=sessions)),
        ):
            result = _run(list_log_sessions(credentials=_fake_creds()))
        assert result == sessions

    @pytest.mark.unit
    def test_admin_returns_sessions(self) -> None:
        sessions = [{"session_id": "s2"}]
        with (
            _patch_auth(_user("admin")),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=sessions)),
        ):
            result = _run(list_log_sessions(credentials=_fake_creds()))
        assert result == sessions

    @pytest.mark.unit
    def test_user_role_raises_403(self) -> None:
        with _patch_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(list_log_sessions(credentials=_fake_creds()))
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# get_log_record
# ═══════════════════════════════════════════════════════════════════════════


class TestGetLogRecord:

    @pytest.mark.unit
    def test_root_returns_record(self) -> None:
        records = [{"record_id": "rec-1", "domain_id": "education"}]
        with (
            _patch_auth(_user("root")),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
        ):
            result = _run(get_log_record("rec-1", credentials=_fake_creds()))
        assert result["record_id"] == "rec-1"

    @pytest.mark.unit
    def test_admin_no_governed_returns_record(self) -> None:
        """admin with empty governed_modules can see any record."""
        records = [{"record_id": "rec-2"}]
        with (
            _patch_auth(_user("admin", governed=[])),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
            patch("lumina.services.system_log.routes.get_model_pack_id", return_value="education"),
        ):
            result = _run(get_log_record("rec-2", credentials=_fake_creds()))
        assert result["record_id"] == "rec-2"

    @pytest.mark.unit
    def test_admin_governed_record_in_scope_returns_record(self) -> None:
        records = [{"record_id": "rec-3", "domain_id": "education"}]
        with (
            _patch_auth(_user("admin", governed=["education"])),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
            patch("lumina.services.system_log.routes.get_model_pack_id", return_value="education"),
        ):
            result = _run(get_log_record("rec-3", credentials=_fake_creds()))
        assert result["record_id"] == "rec-3"

    @pytest.mark.unit
    def test_admin_governed_record_outside_scope_raises_403(self) -> None:
        records = [{"record_id": "rec-4", "domain_id": "agriculture"}]
        with (
            _patch_auth(_user("admin", governed=["education"])),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=records)),
            patch("lumina.services.system_log.routes.get_model_pack_id", return_value="agriculture"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_log_record("rec-4", credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_user_role_raises_403(self) -> None:
        with _patch_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(get_log_record("rec-x", credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_record_not_found_raises_404(self) -> None:
        with (
            _patch_auth(_user("root")),
            patch("lumina.services.system_log.routes.run_in_threadpool", new=AsyncMock(return_value=[])),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_log_record("nonexistent", credentials=_fake_creds()))
        assert exc.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# query_warnings + query_alerts
# ═══════════════════════════════════════════════════════════════════════════


class TestQueryWarningsAndAlerts:

    def _mock_warning_store(self, items: list) -> Any:
        store = MagicMock()
        store.query.return_value = items
        return store

    @pytest.mark.unit
    def test_query_warnings_root_returns_results(self) -> None:
        with (
            _patch_auth(_user("root")),
            patch("lumina.services.system_log.routes.warning_store") as ws,
        ):
            ws.query.return_value = [{"msg": "warn1"}]
            result = _run(query_warnings(credentials=_fake_creds()))
        assert result == [{"msg": "warn1"}]

    @pytest.mark.unit
    def test_query_warnings_user_role_raises_403(self) -> None:
        with _patch_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(query_warnings(credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_query_warnings_admin_governed_module_outside_scope_raises_403(self) -> None:
        with (
            _patch_auth(_user("admin", governed=["edu/algebra"])),
            patch("lumina.services.system_log.routes.warning_store"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(query_warnings(credentials=_fake_creds(), domain_id="agri/crop"))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_query_alerts_root_returns_results(self) -> None:
        with (
            _patch_auth(_user("root")),
            patch("lumina.services.system_log.routes.alert_store") as als,
        ):
            als.query.return_value = [{"msg": "alert1"}]
            result = _run(query_alerts(credentials=_fake_creds()))
        assert result == [{"msg": "alert1"}]

    @pytest.mark.unit
    def test_query_alerts_user_role_raises_403(self) -> None:
        with _patch_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(query_alerts(credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_query_alerts_admin_governed_module_outside_scope_raises_403(self) -> None:
        with (
            _patch_auth(_user("admin", governed=["edu/algebra"])),
            patch("lumina.services.system_log.routes.alert_store"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(query_alerts(credentials=_fake_creds(), domain_id="agri/soil"))
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# events_routes helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_event(
    level: LogLevel = LogLevel.INFO,
    category: str = "general",
    data: dict | None = None,
) -> LogEvent:
    return LogEvent(
        timestamp="2026-06-19T00:00:00+00:00",
        source="test",
        level=level,
        category=category,
        message="test event",
        data=data or {},
    )


class TestFormatSSE:

    @pytest.mark.unit
    def test_format_produces_sse_frame(self) -> None:
        frame = _format_sse("warning", '{"msg": "hi"}')
        assert frame.startswith("event: warning\n")
        assert 'data: {"msg": "hi"}' in frame
        assert frame.endswith("\n\n")


class TestClassifySSEEvent:

    @pytest.mark.unit
    def test_category_escalation_maps_to_escalation(self) -> None:
        event = _make_event(category="escalation")
        assert _classify_sse_event(event) == "escalation"

    @pytest.mark.unit
    def test_category_hash_chain_maps_to_audit(self) -> None:
        event = _make_event(category="hash_chain")
        assert _classify_sse_event(event) == "audit"

    @pytest.mark.unit
    def test_warning_level_without_category_maps_to_warning(self) -> None:
        event = _make_event(level=LogLevel.WARNING, category="unknown_cat")
        assert _classify_sse_event(event) == "warning"

    @pytest.mark.unit
    def test_error_level_maps_to_alert(self) -> None:
        event = _make_event(level=LogLevel.ERROR, category="other")
        assert _classify_sse_event(event) == "alert"

    @pytest.mark.unit
    def test_info_level_unknown_category_maps_to_log(self) -> None:
        event = _make_event(level=LogLevel.INFO, category="other")
        assert _classify_sse_event(event) == "log"


class TestEventVisibleToUser:

    @pytest.mark.unit
    def test_root_sees_everything(self) -> None:
        event = _make_event(level=LogLevel.INFO, data={"domain_id": "education"})
        assert _event_visible_to_user(event, _user("root")) is True

    @pytest.mark.unit
    def test_admin_no_governed_sees_all(self) -> None:
        event = _make_event(data={"domain_id": "agriculture"})
        assert _event_visible_to_user(event, _user("admin", governed=[])) is True

    @pytest.mark.unit
    def test_admin_governed_event_outside_scope_hidden(self) -> None:
        event = _make_event(data={"domain_id": "agriculture"})
        with patch("lumina.services.system_log.events_routes.get_model_pack_id", return_value="agriculture"):
            result = _event_visible_to_user(event, _user("admin", governed=["education"]))
        assert result is False

    @pytest.mark.unit
    def test_half_operator_sees_only_warning_and_above(self) -> None:
        warn_event = _make_event(level=LogLevel.WARNING)
        info_event = _make_event(level=LogLevel.INFO)
        user = _user("half_operator")
        assert _event_visible_to_user(warn_event, user) is True
        assert _event_visible_to_user(info_event, user) is False

    @pytest.mark.unit
    def test_domain_role_holder_sees_escalation_for_governed_domain(self) -> None:
        event = _make_event(category="escalation", data={"domain_id": "education"})
        user = _user("user", domain_roles={"education": "teacher"})
        user["role"] = "user"
        assert _event_visible_to_user(event, user) is True

    @pytest.mark.unit
    def test_domain_role_holder_cannot_see_other_domains_escalation(self) -> None:
        event = _make_event(category="escalation", data={"domain_id": "agriculture"})
        user = _user("user", domain_roles={"education": "teacher"})
        user["role"] = "user"
        assert _event_visible_to_user(event, user) is False

    @pytest.mark.unit
    def test_plain_user_no_domain_roles_sees_nothing(self) -> None:
        event = _make_event(level=LogLevel.INFO)
        user = {"sub": "u1", "role": "user"}
        assert _event_visible_to_user(event, user) is False


class TestValidateSSEToken:

    @pytest.mark.unit
    def test_invalid_token_raises_401(self) -> None:
        # Ensure no matching entry exists for this token
        with pytest.raises(HTTPException) as exc:
            _validate_sse_token("definitely-not-a-real-token-xyz")
        assert exc.value.status_code == 401

    @pytest.mark.unit
    def test_valid_token_returns_user(self) -> None:
        import secrets as _secrets
        raw = _secrets.token_urlsafe(32)
        h = _hash_token(raw)
        _sse_tokens[h] = {
            "user": {"sub": "da-1", "role": "admin"},
            "expires_at": time.time() + 300,
        }
        user = _validate_sse_token(raw)
        assert user["sub"] == "da-1"
        # Token is consumed — second call should fail
        with pytest.raises(HTTPException):
            _validate_sse_token(raw)


class TestGetSSEToken:

    @pytest.mark.unit
    def test_non_governance_role_without_domain_roles_raises_403(self) -> None:
        """A plain user with no domain_roles claim → 403."""
        plain_user = {"sub": "u1", "role": "user", "domain_roles": {}}
        with (
            patch(
                "lumina.services.system_log.events_routes.get_current_user",
                new=AsyncMock(return_value=plain_user),
            ),
            patch(
                "lumina.services.system_log.events_routes.require_auth",
                return_value=plain_user,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_sse_token(credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_governance_role_gets_token(self) -> None:
        """admin role → SSE token returned with expected keys."""
        admin_user = {"sub": "a1", "role": "admin"}
        with (
            patch(
                "lumina.services.system_log.events_routes.get_current_user",
                new=AsyncMock(return_value=admin_user),
            ),
            patch(
                "lumina.services.system_log.events_routes.require_auth",
                return_value=admin_user,
            ),
        ):
            result = _run(get_sse_token(credentials=_fake_creds()))
        assert "token" in result
        assert result["expires_in"] == _SSE_TOKEN_TTL
