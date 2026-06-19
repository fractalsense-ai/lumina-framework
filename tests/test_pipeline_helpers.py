"""Unit tests for lumina.api.pipeline helper functions.

Covers pure-logic paths in:
  - response.build_result
  - response.attach_holodeck_data
  - slm_normalizer._normalize_slm_command
  - commands.build_clarification_response

No server, no real model, no network.  External dependencies (DOMAIN_REGISTRY,
route helpers) are patched to None / simple mocks so that every branch is
exercised deterministically.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# response.build_result
# ═══════════════════════════════════════════════════════════════════════════

from lumina.api.pipeline.response import attach_holodeck_data, build_result


class TestBuildResult:
    """Tests for build_result() dict assembly."""

    def _containers(self, frozen: bool = False) -> dict:
        container = SimpleNamespace(frozen=frozen)
        return {"sess-1": container}

    @pytest.mark.unit
    def test_basic_keys_present(self) -> None:
        """Non-escalated result has the mandatory top-level keys."""
        r = build_result(
            llm_response="Hello",
            resolved_action="task_presentation",
            prompt_contract={"prompt_type": "task_presentation"},
            escalated=False,
            tool_results=None,
            resolved_domain_id="education",
            structured_content=None,
            session_id="sess-1",
            session_containers={},
            seal=None,
            seal_meta=None,
            transcript=None,
        )
        assert r["response"] == "Hello"
        assert r["action"] == "task_presentation"
        assert r["prompt_type"] == "task_presentation"
        assert r["escalated"] is False
        assert r["domain_id"] == "education"
        assert "transcript_seal" not in r
        assert "structured_content" not in r

    @pytest.mark.unit
    def test_prompt_type_defaults_to_task_presentation(self) -> None:
        """prompt_type falls back to 'task_presentation' when key is absent."""
        r = build_result(
            llm_response="x",
            resolved_action="task_presentation",
            prompt_contract={},
            escalated=False,
            tool_results=None,
            resolved_domain_id="edu",
            structured_content=None,
            session_id="s",
            session_containers={},
            seal=None,
            seal_meta=None,
            transcript=None,
        )
        assert r["prompt_type"] == "task_presentation"

    @pytest.mark.unit
    def test_seal_fields_added_when_seal_present(self) -> None:
        """When a seal is provided the three transcript fields are included."""
        r = build_result(
            llm_response="hi",
            resolved_action="task_presentation",
            prompt_contract={"prompt_type": "task_presentation"},
            escalated=False,
            tool_results=None,
            resolved_domain_id="edu",
            structured_content=None,
            session_id="sess-1",
            session_containers={},
            seal="abc123",
            seal_meta={"alg": "sha256"},
            transcript=[{"role": "user", "content": "hi"}],
        )
        assert r["transcript_seal"] == "abc123"
        assert r["transcript_seal_metadata"] == {"alg": "sha256"}
        assert r["transcript_snapshot"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.unit
    def test_escalated_frozen_session_overrides_action(self) -> None:
        """When escalated and the session is frozen, action becomes 'session_frozen'."""
        r = build_result(
            llm_response="escalated",
            resolved_action="governance_command",
            prompt_contract={"prompt_type": "governance"},
            escalated=True,
            tool_results=None,
            resolved_domain_id="edu",
            structured_content=None,
            session_id="sess-1",
            session_containers=self._containers(frozen=True),
            seal=None,
            seal_meta=None,
            transcript=None,
        )
        assert r["action"] == "session_frozen"

    @pytest.mark.unit
    def test_escalated_but_not_frozen_keeps_action(self) -> None:
        """When escalated but the session is NOT frozen, action is unchanged."""
        r = build_result(
            llm_response="escalated",
            resolved_action="governance_command",
            prompt_contract={"prompt_type": "governance"},
            escalated=True,
            tool_results=None,
            resolved_domain_id="edu",
            structured_content=None,
            session_id="sess-1",
            session_containers=self._containers(frozen=False),
            seal=None,
            seal_meta=None,
            transcript=None,
        )
        assert r["action"] == "governance_command"

    @pytest.mark.unit
    def test_escalated_no_container_keeps_action(self) -> None:
        """When escalated but the session_id is absent from containers, action is unchanged."""
        r = build_result(
            llm_response="x",
            resolved_action="governance_command",
            prompt_contract={},
            escalated=True,
            tool_results=None,
            resolved_domain_id="edu",
            structured_content=None,
            session_id="sess-99",
            session_containers={},
            seal=None,
            seal_meta=None,
            transcript=None,
        )
        assert r["action"] == "governance_command"

    @pytest.mark.unit
    def test_structured_content_included_when_not_none(self) -> None:
        """structured_content dict is added to the result when provided."""
        sc = {"holodeck": {"state_snapshot": {}}}
        r = build_result(
            llm_response="x",
            resolved_action="task_presentation",
            prompt_contract={},
            escalated=False,
            tool_results={"tool": "ok"},
            resolved_domain_id="edu",
            structured_content=sc,
            session_id="sess-1",
            session_containers={},
            seal=None,
            seal_meta=None,
            transcript=None,
        )
        assert r["structured_content"] == sc
        assert r["tool_results"] == {"tool": "ok"}


# ═══════════════════════════════════════════════════════════════════════════
# response.attach_holodeck_data
# ═══════════════════════════════════════════════════════════════════════════


@dataclasses.dataclass
class _FakeState:
    score: float = 0.9
    level: str = "algebra"


class TestAttachHolodeckData:
    """Tests for attach_holodeck_data() structured_content assembly."""

    def _make_inspection(self, invariant_results: list | None = None) -> Any:
        ir = MagicMock()
        ir.to_dict.return_value = {"ok": True}
        ir.invariant_results = invariant_results or []
        return ir

    def _make_orchestrator(self, state: Any) -> Any:
        orch = MagicMock()
        orch.state = state
        return orch

    @pytest.mark.unit
    def test_dataclass_state_serialised(self) -> None:
        """Dataclass orchestrator.state is asdict'd into state_snapshot."""
        orch = self._make_orchestrator(_FakeState(score=0.8, level="geometry"))
        ir = self._make_inspection()
        result: dict[str, Any] = {}
        out = attach_holodeck_data(
            result, orch,
            turn_data={"q": 1},
            inspection_result=ir,
            world_sim_theme={},
            mud_world_state={},
        )
        assert out["structured_content"]["holodeck"]["state_snapshot"] == {
            "score": 0.8,
            "level": "geometry",
        }

    @pytest.mark.unit
    def test_dict_state_copied(self) -> None:
        """dict orchestrator.state is shallow-copied into state_snapshot."""
        orch = self._make_orchestrator({"health": 100})
        ir = self._make_inspection()
        result: dict[str, Any] = {}
        out = attach_holodeck_data(
            result, orch,
            turn_data={},
            inspection_result=ir,
            world_sim_theme={},
            mud_world_state={"zone": "forest"},
        )
        hd = out["structured_content"]["holodeck"]
        assert hd["state_snapshot"] == {"health": 100}
        assert hd["world_sim_active"] is True
        assert hd["mud_world_state"] == {"zone": "forest"}

    @pytest.mark.unit
    def test_unknown_state_type_gives_empty_snapshot(self) -> None:
        """Non-dataclass, non-dict state yields an empty state_snapshot."""
        orch = self._make_orchestrator("plain-string-state")
        ir = self._make_inspection(invariant_results=[{"check": "pass"}])
        result: dict[str, Any] = {}
        out = attach_holodeck_data(
            result, orch,
            turn_data={"k": "v"},
            inspection_result=ir,
            world_sim_theme={},
            mud_world_state={},
        )
        hd = out["structured_content"]["holodeck"]
        assert hd["state_snapshot"] == {}
        assert hd["invariant_checks"] == [{"check": "pass"}]

    @pytest.mark.unit
    def test_existing_structured_content_is_extended(self) -> None:
        """If structured_content already exists, holodeck is added without overwriting it."""
        orch = self._make_orchestrator({})
        ir = self._make_inspection()
        result: dict[str, Any] = {"structured_content": {"previous_key": "value"}}
        out = attach_holodeck_data(
            result, orch,
            turn_data={},
            inspection_result=ir,
            world_sim_theme={},
            mud_world_state={},
        )
        assert out["structured_content"]["previous_key"] == "value"
        assert "holodeck" in out["structured_content"]

    @pytest.mark.unit
    def test_empty_mud_world_state_gives_world_sim_inactive(self) -> None:
        """world_sim_active is False when mud_world_state has no 'zone' key."""
        orch = self._make_orchestrator({})
        ir = self._make_inspection()
        result: dict[str, Any] = {}
        out = attach_holodeck_data(
            result, orch,
            turn_data={},
            inspection_result=ir,
            world_sim_theme={},
            mud_world_state={},
        )
        assert out["structured_content"]["holodeck"]["world_sim_active"] is False
        assert out["structured_content"]["holodeck"]["mud_world_state"] is None


# ═══════════════════════════════════════════════════════════════════════════
# slm_normalizer._normalize_slm_command
# ═══════════════════════════════════════════════════════════════════════════

import lumina.api.pipeline.slm_normalizer as _slm_mod
from lumina.api.pipeline.slm_normalizer import _normalize_slm_command


@pytest.fixture(autouse=True)
def _null_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real DomainRegistry is present during normalizer tests."""
    monkeypatch.setattr(_slm_mod._cfg, "DOMAIN_REGISTRY", None)
    monkeypatch.setattr(_slm_mod, "_domain_normalizer_cache", None)
    monkeypatch.setattr(_slm_mod, "_domain_normalizer_cache_registry_id", None)


class TestNormalizeSLMCommand:
    """Tests for _normalize_slm_command() — no DOMAIN_REGISTRY needed."""

    @pytest.mark.unit
    def test_update_user_role_copies_user_id_from_target(self) -> None:
        """user_id is inferred from target when not present in params."""
        cmd = {"operation": "update_user_role", "target": "alice", "params": {}}
        out = _normalize_slm_command(cmd)
        assert out["params"]["user_id"] == "alice"

    @pytest.mark.unit
    def test_update_user_role_normalises_spaced_role(self) -> None:
        """'Domain Authority' is normalised to 'domain_authority'."""
        cmd = {
            "operation": "update_user_role",
            "target": "",
            "params": {"new_role": "Domain Authority"},
        }
        out = _normalize_slm_command(cmd)
        assert out["params"]["new_role"] == "domain_authority"

    @pytest.mark.unit
    def test_update_user_role_clean_role_unchanged(self) -> None:
        """An already-clean role ('admin') is not modified."""
        cmd = {
            "operation": "update_user_role",
            "target": "",
            "params": {"user_id": "bob", "new_role": "admin"},
        }
        out = _normalize_slm_command(cmd)
        assert out["params"]["new_role"] == "admin"

    @pytest.mark.unit
    def test_invite_user_copies_username_from_target(self) -> None:
        """username is inferred from target when not present in params."""
        cmd = {"operation": "invite_user", "target": "carol", "params": {}}
        out = _normalize_slm_command(cmd)
        assert out["params"]["username"] == "carol"

    @pytest.mark.unit
    def test_invite_user_governed_modules_stripped_for_non_admin(self) -> None:
        """governed_modules is removed when the role is not admin."""
        cmd = {
            "operation": "invite_user",
            "target": "",
            "params": {
                "username": "dana",
                "role": "user",
                "governed_modules": ["edu/algebra"],
            },
        }
        out = _normalize_slm_command(cmd)
        assert "governed_modules" not in out["params"]

    @pytest.mark.unit
    def test_invite_user_governed_modules_kept_for_admin(self) -> None:
        """governed_modules is retained when the role is admin."""
        cmd = {
            "operation": "invite_user",
            "target": "",
            "params": {
                "username": "dana",
                "role": "admin",
                "governed_modules": ["edu/algebra"],
            },
        }
        out = _normalize_slm_command(cmd)
        assert out["params"]["governed_modules"] == ["edu/algebra"]

    @pytest.mark.unit
    def test_invite_user_params_as_list_coerced_to_dict(self) -> None:
        """When params is a list it is coerced to {item: True, ...}."""
        cmd = {
            "operation": "invite_user",
            "target": "erin",
            "params": ["role:user"],
        }
        out = _normalize_slm_command(cmd)
        # params was a list; it gets coerced, then username filled from target
        assert isinstance(out["params"], dict)
        assert out["params"]["username"] == "erin"

    @pytest.mark.unit
    def test_invite_user_governed_modules_string_coerced_to_list(self) -> None:
        """A single string in governed_modules is promoted to a one-element list."""
        cmd = {
            "operation": "invite_user",
            "target": "",
            "params": {
                "username": "frank",
                "role": "admin",
                "governed_modules": "edu/algebra",
            },
        }
        out = _normalize_slm_command(cmd)
        assert out["params"]["governed_modules"] == ["edu/algebra"]

    @pytest.mark.unit
    def test_invite_user_top_level_governed_modules_moved_into_params(self) -> None:
        """governed_modules at the top level is moved into params."""
        cmd = {
            "operation": "invite_user",
            "target": "",
            "governed_modules": ["edu/algebra"],
            "params": {"username": "gina", "role": "admin"},
        }
        out = _normalize_slm_command(cmd)
        assert out["params"]["governed_modules"] == ["edu/algebra"]

    @pytest.mark.unit
    def test_assign_domain_role_copies_user_id_from_target(self) -> None:
        """user_id is inferred from target for assign_domain_role."""
        cmd = {"operation": "assign_domain_role", "target": "henry", "params": {}}
        out = _normalize_slm_command(cmd)
        assert out["params"]["user_id"] == "henry"

    @pytest.mark.unit
    def test_revoke_domain_role_copies_user_id_from_target(self) -> None:
        """user_id is inferred from target for revoke_domain_role."""
        cmd = {"operation": "revoke_domain_role", "target": "ivan", "params": {}}
        out = _normalize_slm_command(cmd)
        assert out["params"]["user_id"] == "ivan"

    @pytest.mark.unit
    def test_unknown_operation_passthrough(self) -> None:
        """An unrecognised operation is returned unchanged (no mutation)."""
        cmd = {"operation": "delete_everything", "target": "all", "params": {"x": 1}}
        out = _normalize_slm_command(cmd)
        assert out["operation"] == "delete_everything"
        assert out["params"] == {"x": 1}

    @pytest.mark.unit
    def test_list_users_no_domain_registry_passthrough(self) -> None:
        """list_users with no DOMAIN_REGISTRY leaves params unchanged."""
        cmd = {"operation": "list_users", "target": "education", "params": {}}
        out = _normalize_slm_command(cmd)
        assert out["params"] == {}

    @pytest.mark.unit
    def test_invite_user_all_governed_modules_left_as_is_without_registry(self) -> None:
        """['all'] governed_modules is left unchanged when DOMAIN_REGISTRY is None."""
        cmd = {
            "operation": "invite_user",
            "target": "edu",
            "params": {
                "username": "jane",
                "role": "admin",
                "governed_modules": ["all"],
            },
        }
        out = _normalize_slm_command(cmd)
        # Without a registry we can't expand 'all' — value is preserved
        assert "all" in out["params"]["governed_modules"]


# ═══════════════════════════════════════════════════════════════════════════
# commands.build_clarification_response
# ═══════════════════════════════════════════════════════════════════════════

from lumina.api.pipeline.commands import build_clarification_response


class TestBuildClarificationResponse:
    """Tests for build_clarification_response() — pure dict assembly."""

    @pytest.mark.unit
    def test_schema_error_with_domain_role_alias_hint(self) -> None:
        """A domain-role alias in params triggers a specific hint."""
        aliases = {"teacher": "domain_authority", "student": "learner"}
        cmd = {
            "operation": "invite_user",
            "target": "alice",
            "params": {"role": "teacher"},
        }
        with (
            patch("lumina.api.config.DOMAIN_REGISTRY", None),
            patch(
                "lumina.api.routes.admin._get_domain_role_aliases",
                return_value=aliases,
            ),
        ):
            result = build_clarification_response(
                "schema validation failed: role 'teacher' invalid",
                cmd,
                user=None,
            )
        assert result["type"] == "clarification"
        assert any("domain role" in h for h in result["hints"])
        assert result["operation"] == "invite_user"

    @pytest.mark.unit
    def test_governed_modules_error_appends_domain_hint(self) -> None:
        """'governed_modules' in error triggers domain-labels hint (no registry → skipped)."""
        cmd = {"operation": "invite_user", "target": "", "params": {}}
        with patch("lumina.api.config.DOMAIN_REGISTRY", None):
            result = build_clarification_response(
                "governed_modules field required",
                cmd,
                user=None,
            )
        # With no registry the domain-labels branch is skipped; fallback hints added
        assert len(result["hints"]) >= 1

    @pytest.mark.unit
    def test_no_matching_pattern_falls_back_to_generic_hints(self) -> None:
        """When no error pattern matches, two generic fallback hints are returned."""
        cmd = {"operation": "update_user_role", "target": "", "params": {}}
        with patch("lumina.api.config.DOMAIN_REGISTRY", None):
            result = build_clarification_response(
                "completely unknown error xyz",
                cmd,
                user=None,
            )
        assert any("could not be processed" in h for h in result["hints"])
        assert any("rephrase" in h for h in result["hints"])

    @pytest.mark.unit
    def test_original_params_excludes_password(self) -> None:
        """Sensitive 'password' key is stripped from original_params."""
        cmd = {
            "operation": "invite_user",
            "target": "",
            "params": {"username": "bob", "password": "secret"},
        }
        with patch("lumina.api.config.DOMAIN_REGISTRY", None):
            result = build_clarification_response("some error", cmd, user=None)
        assert "password" not in result["original_params"]
        assert result["original_params"]["username"] == "bob"

    @pytest.mark.unit
    def test_result_contains_error_field(self) -> None:
        """The original error message is preserved in the 'error' key."""
        cmd = {"operation": "list_users", "target": "", "params": {}}
        with patch("lumina.api.config.DOMAIN_REGISTRY", None):
            result = build_clarification_response("field X missing", cmd, user=None)
        assert result["error"] == "field X missing"
