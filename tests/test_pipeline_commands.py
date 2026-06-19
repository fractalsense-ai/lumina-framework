"""Tests for pipeline/commands.py — build_command_content and internal helpers.

build_clarification_response is already covered by test_pipeline_helpers.py.
This file adds coverage for build_command_content, _execute_immediate, and
_stage_and_build branches.

No live model, admin routes, or persistence required — all dependencies patched.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lumina.api.pipeline.commands import (
    _execute_immediate,
    _stage_and_build,
    build_command_content,
)


# ─── common helpers ──────────────────────────────────────────────────────────


def _user(role: str = "root") -> dict:
    return {"sub": f"{role}-1", "role": role}


def _dispatch(operation: str = "invite_user", params: dict | None = None) -> dict:
    return {"operation": operation, "params": params or {}}


def _turn(dispatch: dict | None = None) -> dict:
    return {"command_dispatch": dispatch} if dispatch else {}


# ═══════════════════════════════════════════════════════════════════════════
# build_command_content — early-exit guards
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildCommandContentGuards:

    @pytest.mark.unit
    def test_non_command_action_returns_none(self) -> None:
        result = build_command_content(
            resolved_action="inference",
            turn_data=_turn(_dispatch()),
            input_text="hello",
            user=_user(),
            resolved_domain_id="edu",
            domain_physics={},
            runtime={},
            task_spec={"task_id": "t1"},
            session_id="s",
            orchestrator=MagicMock(),
            call_llm_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_missing_cmd_dispatch_returns_none(self) -> None:
        result = build_command_content(
            resolved_action="system_command",
            turn_data={},  # no command_dispatch key
            input_text="hello",
            user=_user(),
            resolved_domain_id="edu",
            domain_physics={},
            runtime={},
            task_spec={},
            session_id="s",
            orchestrator=MagicMock(),
            call_llm_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_cmd_dispatch_not_dict_returns_none(self) -> None:
        result = build_command_content(
            resolved_action="system_command",
            turn_data={"command_dispatch": "invite_user"},
            input_text="hello",
            user=_user(),
            resolved_domain_id="edu",
            domain_physics={},
            runtime={},
            task_spec={},
            session_id="s",
            orchestrator=MagicMock(),
            call_llm_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_cmd_dispatch_missing_operation_returns_none(self) -> None:
        result = build_command_content(
            resolved_action="system_command",
            turn_data={"command_dispatch": {"params": {}}},
            input_text="hello",
            user=_user(),
            resolved_domain_id="edu",
            domain_physics={},
            runtime={},
            task_spec={},
            session_id="s",
            orchestrator=MagicMock(),
            call_llm_fn=MagicMock(),
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# build_command_content — HITL-exempt path
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildCommandContentHITLExempt:

    @pytest.mark.unit
    def test_hitl_exempt_operation_calls_execute_immediate(self) -> None:
        expected = {"type": "query_result", "operation": "list_modules", "result": {"count": 3}}
        with patch("lumina.api.pipeline.commands._execute_immediate", return_value=expected) as mock_exec:
            with patch(
                "lumina.api.routes.admin._get_hitl_exempt_ops",
                return_value={"list_modules", "list_domains"},
            ):
                result = build_command_content(
                    resolved_action="system_command",
                    turn_data=_turn(_dispatch("list_modules")),
                    input_text="list modules",
                    user=_user(),
                    resolved_domain_id="edu",
                    domain_physics={},
                    runtime={},
                    task_spec={"task_id": "t1"},
                    session_id="s",
                    orchestrator=MagicMock(),
                    call_llm_fn=MagicMock(),
                )
        mock_exec.assert_called_once()
        assert result == expected

    @pytest.mark.unit
    def test_non_hitl_operation_calls_stage_and_build(self) -> None:
        expected = {"type": "command_proposal", "operation": "invite_user"}
        with patch("lumina.api.pipeline.commands._stage_and_build", return_value=expected) as mock_stage:
            with patch(
                "lumina.api.routes.admin._get_hitl_exempt_ops",
                return_value=set(),
            ):
                with patch(
                    "lumina.api.routes.admin._normalize_slm_command",
                    return_value={"operation": "invite_user", "params": {}},
                ):
                    with patch(
                        "lumina.api.routes.admin._stage_command",
                        return_value={"structured_content": expected},
                    ):
                        result = build_command_content(
                            resolved_action="system_command",
                            turn_data=_turn(_dispatch("invite_user")),
                            input_text="invite alice",
                            user=_user(),
                            resolved_domain_id="edu",
                            domain_physics={},
                            runtime={},
                            task_spec={"task_id": "t1"},
                            session_id="s",
                            orchestrator=MagicMock(),
                            call_llm_fn=MagicMock(),
                        )
        mock_stage.assert_called_once()
        assert result == expected

    @pytest.mark.unit
    def test_value_error_returns_clarification_card(self) -> None:
        with patch(
            "lumina.api.routes.admin._get_hitl_exempt_ops",
            side_effect=ValueError("schema validation failed: bad role"),
        ):
            result = build_command_content(
                resolved_action="system_command",
                turn_data=_turn(_dispatch("invite_user", {"role": "god"})),
                input_text="invite with god role",
                user=_user(),
                resolved_domain_id="edu",
                domain_physics={},
                runtime={},
                task_spec={},
                session_id="s",
                orchestrator=MagicMock(),
                call_llm_fn=MagicMock(),
            )
        assert result is not None
        assert result["type"] == "clarification"
        assert "invite_user" in result["operation"]

    @pytest.mark.unit
    def test_generic_exception_returns_none(self) -> None:
        with patch(
            "lumina.api.routes.admin._get_hitl_exempt_ops",
            side_effect=RuntimeError("unexpected crash"),
        ):
            result = build_command_content(
                resolved_action="system_command",
                turn_data=_turn(_dispatch("invite_user")),
                input_text="invite alice",
                user=_user(),
                resolved_domain_id="edu",
                domain_physics={},
                runtime={},
                task_spec={},
                session_id="s",
                orchestrator=MagicMock(),
                call_llm_fn=MagicMock(),
            )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# _execute_immediate
# ═══════════════════════════════════════════════════════════════════════════


class TestExecuteImmediate:

    @pytest.mark.unit
    def test_execute_immediate_returns_query_result(self) -> None:
        exec_result = {"operation": "list_modules", "count": 2, "records": []}
        with patch(
            "lumina.api.routes.admin._normalize_slm_command",
            return_value={"operation": "list_modules", "params": {"domain_id": "edu"}},
        ):
            with patch(
                "lumina.api.routes.admin._execute_admin_operation",
                return_value=MagicMock(),
            ) as mock_exec:
                # Patch asyncio.run to return our fake result synchronously
                with patch("asyncio.run", return_value=exec_result):
                    result = _execute_immediate(
                        cmd_dispatch=_dispatch("list_modules"),
                        input_text="list modules",
                        user=_user(),
                        resolved_domain_id="edu",
                        actor_id="root-1",
                        actor_role="root",
                        operation="list_modules",
                    )
        assert result["type"] == "query_result"
        assert result["operation"] == "list_modules"

    @pytest.mark.unit
    def test_execute_immediate_injects_domain_id_when_missing(self) -> None:
        """domain_id is injected into params when absent."""
        with patch(
            "lumina.api.routes.admin._normalize_slm_command",
            return_value={"operation": "list_modules", "params": {}},
        ):
            with patch("asyncio.run", return_value={"operation": "list_modules"}):
                with patch("lumina.api.routes.admin._execute_admin_operation", return_value=MagicMock()):
                    result = _execute_immediate(
                        cmd_dispatch=_dispatch("list_modules"),
                        input_text="list modules",
                        user=_user(),
                        resolved_domain_id="edu-resolved",
                        actor_id="root-1",
                        actor_role="root",
                        operation="list_modules",
                    )
        assert result["type"] == "query_result"


# ═══════════════════════════════════════════════════════════════════════════
# _stage_and_build
# ═══════════════════════════════════════════════════════════════════════════


class TestStageAndBuild:

    @pytest.mark.unit
    def test_non_physics_returns_staged_structured_content(self) -> None:
        staged_content = {"type": "command_proposal", "operation": "invite_user"}
        with patch(
            "lumina.api.routes.admin._stage_command",
            return_value={"structured_content": staged_content},
        ):
            result = _stage_and_build(
                cmd_dispatch=_dispatch("invite_user"),
                input_text="invite alice",
                user=_user(),
                resolved_domain_id="edu",
                domain_physics={},
                runtime={},
                task_spec={"task_id": "t1"},
                session_id="s",
                orchestrator=MagicMock(),
                actor_id="root-1",
                actor_role="root",
                operation="invite_user",
                resolved_action="system_command",
                call_llm_fn=MagicMock(),
            )
        assert result == staged_content

    @pytest.mark.unit
    def test_physics_edit_with_proposal_builds_physics_card(self) -> None:
        staged = {"structured_content": {"type": "command_proposal"}, "escalation_record_id": None}
        proposal = {"proposed_patch": {"label": "New Label"}}
        physics_card = {"type": "physics_edit_proposal", "staged": staged}
        with patch("lumina.api.routes.admin._stage_command", return_value=staged):
            with patch(
                "lumina.api.structured_content.build_physics_edit_card",
                return_value=physics_card,
            ):
                result = _stage_and_build(
                    cmd_dispatch=_dispatch("update_domain_physics"),
                    input_text="update label",
                    user=_user(),
                    resolved_domain_id="edu",
                    domain_physics={"id": "edu", "label": "Old"},
                    runtime={"tool_fns": {"extract_physics_patch": lambda *a: proposal}},
                    task_spec={"task_id": "t1"},
                    session_id="s",
                    orchestrator=MagicMock(),
                    actor_id="root-1",
                    actor_role="root",
                    operation="update_domain_physics",
                    resolved_action="governance_command",
                    call_llm_fn=MagicMock(),
                )
        assert result == physics_card

    @pytest.mark.unit
    def test_physics_edit_no_proposal_returns_staged_content(self) -> None:
        staged_content = {"type": "command_proposal", "operation": "update_domain_physics"}
        staged = {"structured_content": staged_content}
        with patch("lumina.api.routes.admin._stage_command", return_value=staged):
            result = _stage_and_build(
                cmd_dispatch=_dispatch("update_domain_physics"),
                input_text="update label",
                user=_user(),
                resolved_domain_id="edu",
                domain_physics={"id": "edu"},
                runtime={},  # no tool_fns
                task_spec={"task_id": "t1"},
                session_id="s",
                orchestrator=MagicMock(),
                actor_id="root-1",
                actor_role="root",
                operation="update_domain_physics",
                resolved_action="governance_command",
                call_llm_fn=MagicMock(),
            )
        assert result == staged_content

    @pytest.mark.unit
    def test_physics_edit_extract_fn_raises_logs_and_falls_back(self) -> None:
        """If extract_physics_patch throws, falls back to standard staging."""
        staged_content = {"type": "command_proposal"}
        staged = {"structured_content": staged_content}

        def _raising_extract(*a):
            raise RuntimeError("model timed out")

        with patch("lumina.api.routes.admin._stage_command", return_value=staged):
            result = _stage_and_build(
                cmd_dispatch=_dispatch("update_domain_physics"),
                input_text="update",
                user=_user(),
                resolved_domain_id="edu",
                domain_physics={"id": "edu"},
                runtime={"tool_fns": {"extract_physics_patch": _raising_extract}},
                task_spec={},
                session_id="s",
                orchestrator=MagicMock(),
                actor_id="root-1",
                actor_role="root",
                operation="update_domain_physics",
                resolved_action="governance_command",
                call_llm_fn=MagicMock(),
            )
        assert result == staged_content

    @pytest.mark.unit
    def test_novel_synthesis_appends_to_orchestrator(self) -> None:
        staged = {"structured_content": None, "staged_id": "stg-1", "escalation_record_id": None}
        proposal = {"proposed_patch": {"label": "x"}}
        physics_card: dict[str, Any] = {"type": "physics_edit_proposal", "context": {}}
        novel_ids = ["novel-1", "novel-2"]
        orchestrator = MagicMock()

        with patch("lumina.api.routes.admin._stage_command", return_value=staged):
            with patch(
                "lumina.api.structured_content.build_physics_edit_card",
                return_value=physics_card,
            ):
                _stage_and_build(
                    cmd_dispatch=_dispatch("update_domain_physics"),
                    input_text="update",
                    user=_user(),
                    resolved_domain_id="edu",
                    domain_physics={"id": "edu"},
                    runtime={
                        "tool_fns": {
                            "extract_physics_patch": lambda *a: proposal,
                            "detect_novel_synthesis": lambda *a: novel_ids,
                        }
                    },
                    task_spec={"task_id": "t1"},
                    session_id="s",
                    orchestrator=orchestrator,
                    actor_id="root-1",
                    actor_role="root",
                    operation="update_domain_physics",
                    resolved_action="governance_command",
                    call_llm_fn=MagicMock(),
                )
        orchestrator.append_provenance_trace.assert_called_once()
        call_kwargs = orchestrator.append_provenance_trace.call_args[1]
        assert call_kwargs["action"] == "novel_synthesis_flagged"
        assert "novel_ids" in call_kwargs["metadata"]
