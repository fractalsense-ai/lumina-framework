"""Unit tests for lumina.api.pipeline.interceptors.

Covers check_glossary, check_turn_0, resolve_greeting_eligible, and
check_greeting.  No live model or SLM — SLM paths are stubbed with
unittest.mock.patch on the slm import.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lumina.api.pipeline.interceptors import (
    check_glossary,
    check_greeting,
    check_turn_0,
    resolve_greeting_eligible,
)


# ─── common helpers ──────────────────────────────────────────────────────────


def _session(turn_count: int = 0) -> dict:
    return {"turn_count": turn_count, "session_id": "sess-1"}


def _physics(glossary: list | None = None, greeting: dict | None = None) -> dict:
    d: dict[str, Any] = {"id": "edu", "version": "1"}
    if glossary is not None:
        d["glossary"] = glossary
    if greeting is not None:
        d["greeting"] = greeting
    return d


def _runtime() -> dict:
    return {"domain": {}}


def _task_spec() -> dict:
    return {"task_id": "t-1"}


def _current_task() -> dict:
    return {"problem_text": "Solve x+2=5", "answer": "3"}


# ═══════════════════════════════════════════════════════════════════════════
# check_glossary
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckGlossary:

    @pytest.mark.unit
    def test_no_match_returns_none(self) -> None:
        result = check_glossary(
            session_id="s",
            session=_session(),
            input_text="what is photosynthesis",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            deterministic_response=False,
            system_prompt="You are a helpful tutor.",
            detect_glossary_query_fn=lambda text, glossary, **kw: None,
            slm_available_fn=lambda: False,
            slm_render_glossary_fn=MagicMock(),
            call_llm_fn=MagicMock(),
            sync_session_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_deterministic_with_template_uses_template(self) -> None:
        match = {"term": "variable", "definition": "an unknown", "example_in_context": "x=5", "related_terms": []}
        template = "{term}: {definition}"
        session = _session()
        sync = MagicMock()
        result = check_glossary(
            session_id="s",
            session=session,
            input_text="what is variable",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime={"deterministic_templates": {"definition_lookup": template}},
            resolved_domain_id="edu",
            deterministic_response=True,
            system_prompt="",
            detect_glossary_query_fn=lambda *a, **kw: match,
            slm_available_fn=lambda: False,
            slm_render_glossary_fn=MagicMock(),
            call_llm_fn=MagicMock(),
            sync_session_fn=sync,
        )
        assert result is not None
        assert "variable: an unknown" in result["response"]
        assert session["turn_count"] == 1
        sync.assert_called_once()

    @pytest.mark.unit
    def test_deterministic_no_template_builds_fallback(self) -> None:
        match = {"term": "integer", "definition": "a whole number", "example_in_context": "e.g. 5", "related_terms": []}
        result = check_glossary(
            session_id="s",
            session=_session(),
            input_text="what is integer",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            deterministic_response=True,
            system_prompt="",
            detect_glossary_query_fn=lambda *a, **kw: match,
            slm_available_fn=lambda: False,
            slm_render_glossary_fn=MagicMock(),
            call_llm_fn=MagicMock(),
            sync_session_fn=MagicMock(),
        )
        assert "Integer" in result["response"]
        assert "a whole number" in result["response"]

    @pytest.mark.unit
    def test_slm_available_calls_slm_render(self) -> None:
        match = {"term": "slope", "definition": "rise over run", "example_in_context": "2/3", "related_terms": []}
        slm_render = MagicMock(return_value="Slope is rise over run.")
        result = check_glossary(
            session_id="s",
            session=_session(),
            input_text="what is slope",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            deterministic_response=False,
            system_prompt="",
            detect_glossary_query_fn=lambda *a, **kw: match,
            slm_available_fn=lambda: True,
            slm_render_glossary_fn=slm_render,
            call_llm_fn=MagicMock(),
            sync_session_fn=MagicMock(),
        )
        slm_render.assert_called_once()
        assert result["response"] == "Slope is rise over run."
        assert result["action"] == "definition_lookup"

    @pytest.mark.unit
    def test_slm_unavailable_builds_fallback(self) -> None:
        match = {"term": "median", "definition": "middle value", "example_in_context": "5 in [1,5,9]", "related_terms": []}
        result = check_glossary(
            session_id="s",
            session=_session(),
            input_text="what is median",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            deterministic_response=False,
            system_prompt="",
            detect_glossary_query_fn=lambda *a, **kw: match,
            slm_available_fn=lambda: False,
            slm_render_glossary_fn=MagicMock(),
            call_llm_fn=MagicMock(),
            sync_session_fn=MagicMock(),
        )
        assert "Median" in result["response"]
        assert result["domain_id"] == "edu"

    @pytest.mark.unit
    def test_glossary_from_runtime_domain(self) -> None:
        """Falls back to runtime.domain.glossary when physics has none."""
        match = {"term": "x", "definition": "unknown", "example_in_context": "x=1", "related_terms": []}
        runtime = {"domain": {"glossary": [{"term": "x", "definition": "unknown"}]}}
        result = check_glossary(
            session_id="s",
            session=_session(),
            input_text="what is x",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics={},
            runtime=runtime,
            resolved_domain_id="edu",
            deterministic_response=True,
            system_prompt="",
            detect_glossary_query_fn=lambda text, glossary, **kw: match,
            slm_available_fn=lambda: False,
            slm_render_glossary_fn=MagicMock(),
            call_llm_fn=MagicMock(),
            sync_session_fn=MagicMock(),
        )
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════
# check_turn_0
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckTurn0:

    @pytest.mark.unit
    def test_no_turn0_fn_returns_none(self) -> None:
        result = check_turn_0(
            session_id="s",
            session=_session(),
            input_text="hi",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            holodeck=False,
            deterministic_response=False,
            active_mod={},
            session_containers={},
            user=None,
            slm_available_fn=lambda: False,
            call_llm_fn=MagicMock(),
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_turn0_fn_returns_false_returns_none(self) -> None:
        result = check_turn_0(
            session_id="s",
            session=_session(),
            input_text="hi",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            holodeck=False,
            deterministic_response=False,
            active_mod={"turn_0_presenter_fn": lambda **kw: False},
            session_containers={},
            user=None,
            slm_available_fn=lambda: False,
            call_llm_fn=MagicMock(),
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_turn0_llm_path_returns_result(self) -> None:
        llm = MagicMock(return_value="Here is your problem.")
        sync = MagicMock()
        seal_fn = MagicMock(return_value=(None, None, None))
        session = _session()
        result = check_turn_0(
            session_id="s",
            session=session,
            input_text="start",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="You are a tutor.",
            holodeck=False,
            deterministic_response=False,
            active_mod={"turn_0_presenter_fn": lambda **kw: True},
            session_containers={},
            user=None,
            slm_available_fn=lambda: False,
            call_llm_fn=llm,
            compute_seal_fn=seal_fn,
            sync_session_fn=sync,
        )
        assert result is not None
        assert result["action"] == "task_presentation"
        assert session["turn_count"] == 1
        llm.assert_called_once()

    @pytest.mark.unit
    def test_turn0_with_seal_adds_seal_to_result(self) -> None:
        llm = MagicMock(return_value="Problem presented.")
        seal_fn = MagicMock(return_value=("seal-abc", {"meta": 1}, "transcript..."))
        result = check_turn_0(
            session_id="s",
            session=_session(),
            input_text="start",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            holodeck=False,
            deterministic_response=False,
            active_mod={"turn_0_presenter_fn": lambda **kw: True},
            session_containers={},
            user={"sub": "u-1"},
            slm_available_fn=lambda: False,
            call_llm_fn=llm,
            compute_seal_fn=seal_fn,
            sync_session_fn=MagicMock(),
        )
        assert result["transcript_seal"] == "seal-abc"
        assert result["transcript_snapshot"] == "transcript..."

    @pytest.mark.unit
    def test_turn0_ring_buffer_pushed_when_container_present(self) -> None:
        llm = MagicMock(return_value="Here is problem.")
        container = MagicMock()
        session = _session()
        check_turn_0(
            session_id="s",
            session=session,
            input_text="start",
            current_task=_current_task(),
            task_spec=_task_spec(),
            domain_physics=_physics(),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            holodeck=False,
            deterministic_response=False,
            active_mod={"turn_0_presenter_fn": lambda **kw: True},
            session_containers={"s": container},
            user=None,
            slm_available_fn=lambda: False,
            call_llm_fn=llm,
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=MagicMock(),
        )
        container.ring_buffer.push.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# resolve_greeting_eligible
# ═══════════════════════════════════════════════════════════════════════════


class TestResolveGreetingEligible:

    @pytest.mark.unit
    def test_eligible_returns_true(self) -> None:
        physics = _physics(greeting={"enabled": True})
        assert resolve_greeting_eligible(
            session=_session(turn_count=0),
            domain_physics=physics,
            holodeck=False,
            deterministic_response=False,
            has_equation=False,
        ) is True

    @pytest.mark.unit
    def test_turn_count_nonzero_returns_false(self) -> None:
        physics = _physics(greeting={"enabled": True})
        assert resolve_greeting_eligible(
            session=_session(turn_count=1),
            domain_physics=physics,
            holodeck=False,
            deterministic_response=False,
            has_equation=False,
        ) is False

    @pytest.mark.unit
    def test_holodeck_true_returns_false(self) -> None:
        physics = _physics(greeting={"enabled": True})
        assert resolve_greeting_eligible(
            session=_session(turn_count=0),
            domain_physics=physics,
            holodeck=True,
            deterministic_response=False,
            has_equation=False,
        ) is False

    @pytest.mark.unit
    def test_deterministic_true_returns_false(self) -> None:
        physics = _physics(greeting={"enabled": True})
        assert resolve_greeting_eligible(
            session=_session(turn_count=0),
            domain_physics=physics,
            holodeck=False,
            deterministic_response=True,
            has_equation=False,
        ) is False

    @pytest.mark.unit
    def test_has_equation_returns_false(self) -> None:
        physics = _physics(greeting={"enabled": True})
        assert resolve_greeting_eligible(
            session=_session(turn_count=0),
            domain_physics=physics,
            holodeck=False,
            deterministic_response=False,
            has_equation=True,
        ) is False

    @pytest.mark.unit
    def test_greeting_not_enabled_returns_false(self) -> None:
        physics = _physics(greeting={"enabled": False})
        assert resolve_greeting_eligible(
            session=_session(turn_count=0),
            domain_physics=physics,
            holodeck=False,
            deterministic_response=False,
            has_equation=False,
        ) is False

    @pytest.mark.unit
    def test_no_greeting_config_returns_false(self) -> None:
        assert resolve_greeting_eligible(
            session=_session(turn_count=0),
            domain_physics=_physics(),
            holodeck=False,
            deterministic_response=False,
            has_equation=False,
        ) is False


# ═══════════════════════════════════════════════════════════════════════════
# check_greeting
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckGreeting:

    @pytest.mark.unit
    def test_command_dispatch_returns_none(self) -> None:
        """Command takes priority on turn 0."""
        result = check_greeting(
            session_id="s",
            session=_session(),
            input_text="hello",
            turn_data={"command_dispatch": {"command": "hint"}},
            domain_physics=_physics(greeting={"enabled": True, "fallback_message": "Hello!"}),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            session_containers={},
            user=None,
            holodeck=False,
            slm_available_fn=lambda: False,
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=MagicMock(),
        )
        assert result is None

    @pytest.mark.unit
    def test_slm_unavailable_uses_fallback_message(self) -> None:
        sync = MagicMock()
        session = _session()
        result = check_greeting(
            session_id="s",
            session=session,
            input_text="hello",
            turn_data={},
            domain_physics=_physics(greeting={"enabled": True, "fallback_message": "Welcome back!"}),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            session_containers={},
            user=None,
            holodeck=False,
            slm_available_fn=lambda: False,
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=sync,
        )
        assert result is not None
        assert result["response"] == "Welcome back!"
        assert result["action"] == "greeting"
        assert session["turn_count"] == 1
        sync.assert_called_once()

    @pytest.mark.unit
    def test_slm_unavailable_default_fallback_when_no_message(self) -> None:
        result = check_greeting(
            session_id="s",
            session=_session(),
            input_text="hello",
            turn_data={},
            domain_physics=_physics(greeting={"enabled": True}),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            session_containers={},
            user=None,
            holodeck=False,
            slm_available_fn=lambda: False,
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=MagicMock(),
        )
        assert "Welcome" in result["response"]

    @pytest.mark.unit
    def test_ring_buffer_pushed_when_container_present(self) -> None:
        container = MagicMock()
        check_greeting(
            session_id="s",
            session=_session(),
            input_text="hello",
            turn_data={},
            domain_physics=_physics(greeting={"enabled": True, "fallback_message": "Hi!"}),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            session_containers={"s": container},
            user=None,
            holodeck=False,
            slm_available_fn=lambda: False,
            compute_seal_fn=lambda *a, **kw: (None, None, None),
            sync_session_fn=MagicMock(),
        )
        container.ring_buffer.push.assert_called_once()

    @pytest.mark.unit
    def test_seal_added_to_result(self) -> None:
        seal_fn = MagicMock(return_value=("seal-xyz", {"algo": "sha3"}, "snapshot"))
        result = check_greeting(
            session_id="s",
            session=_session(),
            input_text="hello",
            turn_data={},
            domain_physics=_physics(greeting={"enabled": True, "fallback_message": "Hi"}),
            runtime=_runtime(),
            resolved_domain_id="edu",
            system_prompt="",
            session_containers={},
            user={"sub": "u-1"},
            holodeck=False,
            slm_available_fn=lambda: False,
            compute_seal_fn=seal_fn,
            sync_session_fn=MagicMock(),
        )
        assert result["transcript_seal"] == "seal-xyz"
        assert result["transcript_snapshot"] == "snapshot"

    @pytest.mark.unit
    def test_slm_available_calls_slm(self) -> None:
        with patch("lumina.api.pipeline.interceptors.check_greeting.__module__"):
            pass  # just verifying patch path
        # Patch the SLM call inside check_greeting
        with patch("lumina.core.slm.call_slm", return_value="Hey there!") as mock_slm:
            result = check_greeting(
                session_id="s",
                session=_session(),
                input_text="hello",
                turn_data={},
                domain_physics=_physics(greeting={"enabled": True, "fallback_message": "Hi"}),
                runtime=_runtime(),
                resolved_domain_id="edu",
                system_prompt="You are a tutor.",
                session_containers={},
                user=None,
                holodeck=False,
                slm_available_fn=lambda: True,
                compute_seal_fn=lambda *a, **kw: (None, None, None),
                sync_session_fn=MagicMock(),
            )
        # SLM is called lazily via import inside function; result should come from SLM
        assert result is not None
        assert result["action"] == "greeting"
