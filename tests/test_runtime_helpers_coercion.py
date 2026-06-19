"""Unit tests for lumina.api.utils.coercion and lumina.api.runtime_helpers.

All tests are pure / deterministic — no live model or SLM calls.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lumina.api.utils.coercion import (
    coerce_bool,
    coerce_float,
    coerce_int,
    coerce_str,
    normalize_turn_data,
)
from lumina.api.runtime_helpers import (
    apply_tool_call_policy,
    invoke_runtime_tool,
    render_contract_response,
)


# ═══════════════════════════════════════════════════════════════════════════
# coerce_bool
# ═══════════════════════════════════════════════════════════════════════════


class TestCoerceBool:

    @pytest.mark.unit
    def test_true_bool_returned_unchanged(self) -> None:
        assert coerce_bool(True) is True

    @pytest.mark.unit
    def test_false_bool_returned_unchanged(self) -> None:
        assert coerce_bool(False) is False

    @pytest.mark.unit
    def test_int_1_is_true(self) -> None:
        assert coerce_bool(1) is True

    @pytest.mark.unit
    def test_int_0_is_false(self) -> None:
        assert coerce_bool(0) is False

    @pytest.mark.unit
    @pytest.mark.parametrize("s", ["true", "True", "TRUE", "1", "yes", "Yes", "y", "Y"])
    def test_truthy_strings(self, s: str) -> None:
        assert coerce_bool(s) is True

    @pytest.mark.unit
    @pytest.mark.parametrize("s", ["false", "False", "FALSE", "0", "no", "No", "n", "N"])
    def test_falsy_strings(self, s: str) -> None:
        assert coerce_bool(s) is False

    @pytest.mark.unit
    def test_unknown_returns_default(self) -> None:
        assert coerce_bool("maybe", default=True) is True

    @pytest.mark.unit
    def test_none_returns_default(self) -> None:
        assert coerce_bool(None, default=False) is False


# ═══════════════════════════════════════════════════════════════════════════
# coerce_int
# ═══════════════════════════════════════════════════════════════════════════


class TestCoerceInt:

    @pytest.mark.unit
    def test_int_passthrough(self) -> None:
        assert coerce_int(5) == 5

    @pytest.mark.unit
    def test_string_int(self) -> None:
        assert coerce_int("42") == 42

    @pytest.mark.unit
    def test_invalid_returns_default(self) -> None:
        assert coerce_int("not-a-number", default=3) == 3

    @pytest.mark.unit
    def test_none_returns_default(self) -> None:
        assert coerce_int(None, default=7) == 7

    @pytest.mark.unit
    def test_minimum_clamps_upward(self) -> None:
        assert coerce_int(-5, minimum=0) == 0

    @pytest.mark.unit
    def test_above_minimum_unchanged(self) -> None:
        assert coerce_int(10, minimum=1) == 10


# ═══════════════════════════════════════════════════════════════════════════
# coerce_float
# ═══════════════════════════════════════════════════════════════════════════


class TestCoerceFloat:

    @pytest.mark.unit
    def test_float_passthrough(self) -> None:
        assert coerce_float(1.5) == 1.5

    @pytest.mark.unit
    def test_string_float(self) -> None:
        assert coerce_float("3.14") == pytest.approx(3.14)

    @pytest.mark.unit
    def test_invalid_returns_default(self) -> None:
        assert coerce_float("bad", default=2.5) == 2.5

    @pytest.mark.unit
    def test_minimum_clamp(self) -> None:
        assert coerce_float(-1.0, minimum=0.0) == 0.0

    @pytest.mark.unit
    def test_maximum_clamp(self) -> None:
        assert coerce_float(5.0, maximum=3.0) == 3.0

    @pytest.mark.unit
    def test_within_bounds_unchanged(self) -> None:
        assert coerce_float(2.0, minimum=0.0, maximum=5.0) == 2.0


# ═══════════════════════════════════════════════════════════════════════════
# coerce_str
# ═══════════════════════════════════════════════════════════════════════════


class TestCoerceStr:

    @pytest.mark.unit
    def test_string_passthrough(self) -> None:
        assert coerce_str("hello") == "hello"

    @pytest.mark.unit
    def test_none_returns_default(self) -> None:
        assert coerce_str(None, default="fallback") == "fallback"

    @pytest.mark.unit
    def test_int_becomes_str(self) -> None:
        assert coerce_str(42) == "42"

    @pytest.mark.unit
    def test_empty_string_returned(self) -> None:
        assert coerce_str("") == ""


# ═══════════════════════════════════════════════════════════════════════════
# normalize_turn_data
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeTurnData:

    @pytest.mark.unit
    def test_empty_schema_returns_unchanged(self) -> None:
        turn = {"action": "submit", "score": 90}
        result = normalize_turn_data(turn, {})
        assert result == turn

    @pytest.mark.unit
    def test_none_schema_returns_unchanged(self) -> None:
        turn = {"action": "submit"}
        result = normalize_turn_data(turn, None)
        assert result == turn

    @pytest.mark.unit
    def test_bool_field_coerced(self) -> None:
        turn = {"holodeck": "true"}
        schema = {"holodeck": {"type": "bool", "default": False}}
        result = normalize_turn_data(turn, schema)
        assert result["holodeck"] is True

    @pytest.mark.unit
    def test_bool_default_injected_when_absent(self) -> None:
        turn: dict[str, Any] = {}
        schema = {"holodeck": {"type": "bool", "default": False}}
        result = normalize_turn_data(turn, schema)
        assert result["holodeck"] is False

    @pytest.mark.unit
    def test_int_field_coerced(self) -> None:
        turn = {"attempts": "3"}
        schema = {"attempts": {"type": "int", "default": 1, "minimum": 1}}
        result = normalize_turn_data(turn, schema)
        assert result["attempts"] == 3

    @pytest.mark.unit
    def test_int_minimum_enforced(self) -> None:
        turn = {"attempts": -10}
        schema = {"attempts": {"type": "int", "default": 1, "minimum": 0}}
        result = normalize_turn_data(turn, schema)
        assert result["attempts"] == 0

    @pytest.mark.unit
    def test_float_field_coerced(self) -> None:
        turn = {"difficulty": "0.75"}
        schema = {"difficulty": {"type": "float", "default": 0.5, "minimum": 0.0, "maximum": 1.0}}
        result = normalize_turn_data(turn, schema)
        assert result["difficulty"] == pytest.approx(0.75)

    @pytest.mark.unit
    def test_string_field_coerced(self) -> None:
        turn = {"label": 42}
        schema = {"label": {"type": "string", "default": ""}}
        result = normalize_turn_data(turn, schema)
        assert result["label"] == "42"

    @pytest.mark.unit
    def test_enum_valid_value_kept(self) -> None:
        turn = {"mode": "easy"}
        schema = {"mode": {"type": "enum", "values": ["easy", "hard"], "default": "easy"}}
        result = normalize_turn_data(turn, schema)
        assert result["mode"] == "easy"

    @pytest.mark.unit
    def test_enum_invalid_value_replaced_with_default(self) -> None:
        turn = {"mode": "impossible"}
        schema = {"mode": {"type": "enum", "values": ["easy", "hard"], "default": "easy"}}
        result = normalize_turn_data(turn, schema)
        assert result["mode"] == "easy"

    @pytest.mark.unit
    def test_list_field_passthrough(self) -> None:
        turn = {"tags": ["a", "b"]}
        schema = {"tags": {"type": "list", "default": []}}
        result = normalize_turn_data(turn, schema)
        assert result["tags"] == ["a", "b"]

    @pytest.mark.unit
    def test_list_non_list_replaced_with_default(self) -> None:
        turn = {"tags": "not-a-list"}
        schema = {"tags": {"type": "list", "default": ["x"]}}
        result = normalize_turn_data(turn, schema)
        assert result["tags"] == ["x"]

    @pytest.mark.unit
    def test_non_dict_raw_cfg_skipped(self) -> None:
        turn = {"field": "val"}
        schema = {"field": "not-a-dict"}
        result = normalize_turn_data(turn, schema)
        assert result["field"] == "val"


# ═══════════════════════════════════════════════════════════════════════════
# runtime_helpers — render_contract_response
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderContractResponse:

    @pytest.mark.unit
    def test_uses_prompt_type_template(self) -> None:
        runtime = {"deterministic_templates": {"inference": "Solve {task_id}."}}
        result = render_contract_response({"prompt_type": "inference", "task_id": "t1"}, runtime)
        assert "t1" in result

    @pytest.mark.unit
    def test_falls_back_to_default_template(self) -> None:
        runtime = {"deterministic_templates": {"default": "Continue with {task_id}."}}
        result = render_contract_response({"prompt_type": "unknown"}, runtime)
        assert "Continue" in result

    @pytest.mark.unit
    def test_hard_coded_fallback_when_no_template(self) -> None:
        runtime = {"deterministic_templates": {}}
        result = render_contract_response({"prompt_type": "unknown"}, runtime)
        assert "Continue" in result  # built-in fallback: "Continue with {task_id}."

    @pytest.mark.unit
    def test_template_with_missing_key_returned_literally(self) -> None:
        """When a template key is missing, return the raw template string."""
        runtime = {"deterministic_templates": {"inference": "Hello {undefined_key}."}}
        result = render_contract_response({"prompt_type": "inference", "task_id": "t1"}, runtime)
        assert result == "Hello {undefined_key}."

    @pytest.mark.unit
    def test_mud_template_used_when_zone_present(self) -> None:
        runtime = {
            "deterministic_templates": {"default": "fallback"},
            "deterministic_templates_mud": {"inference": "MUD: {task_id} in {zone}"},
        }
        mud = {"zone": "dungeon"}
        result = render_contract_response(
            {"prompt_type": "inference", "task_id": "t1"},
            runtime,
            mud_world_state=mud,
        )
        assert "MUD:" in result
        assert "dungeon" in result

    @pytest.mark.unit
    def test_mud_template_fallback_to_plain_when_no_zone(self) -> None:
        runtime = {
            "deterministic_templates": {"inference": "Plain: {task_id}"},
            "deterministic_templates_mud": {"inference": "MUD: {zone}"},
        }
        result = render_contract_response(
            {"prompt_type": "inference", "task_id": "t1"},
            runtime,
            mud_world_state={"zone": ""},  # empty zone → skip MUD template
        )
        assert "Plain:" in result


# ═══════════════════════════════════════════════════════════════════════════
# runtime_helpers — invoke_runtime_tool
# ═══════════════════════════════════════════════════════════════════════════


class TestInvokeRuntimeTool:

    @pytest.mark.unit
    def test_unknown_tool_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="Unknown tool adapter"):
            invoke_runtime_tool("mystery_tool", {}, {"tool_fns": {}})

    @pytest.mark.unit
    def test_tool_returning_non_dict_raises_runtime_error(self) -> None:
        runtime = {"tool_fns": {"bad_tool": lambda p: ["list not dict"]}}
        with pytest.raises(RuntimeError, match="must return a dict"):
            invoke_runtime_tool("bad_tool", {}, runtime)

    @pytest.mark.unit
    def test_tool_returns_result(self) -> None:
        tool_fn = MagicMock(return_value={"score": 42})
        runtime = {"tool_fns": {"scorer": tool_fn}}
        result = invoke_runtime_tool("scorer", {"question": "q1"}, runtime)
        assert result["score"] == 42
        tool_fn.assert_called_once_with({"question": "q1"})


# ═══════════════════════════════════════════════════════════════════════════
# runtime_helpers — apply_tool_call_policy
# ═══════════════════════════════════════════════════════════════════════════


class TestApplyToolCallPolicy:

    @pytest.mark.unit
    def test_no_policies_returns_empty(self) -> None:
        result = apply_tool_call_policy(
            "inference", {}, {}, {}, runtime={"tool_call_policies": {}},
        )
        assert result == []

    @pytest.mark.unit
    def test_no_policies_key_returns_empty(self) -> None:
        result = apply_tool_call_policy("inference", {}, {}, {}, runtime={})
        assert result == []

    @pytest.mark.unit
    def test_non_list_entries_returns_empty(self) -> None:
        runtime = {"tool_call_policies": {"inference": "not-a-list"}}
        result = apply_tool_call_policy("inference", {}, {}, {}, runtime=runtime)
        assert result == []

    @pytest.mark.unit
    def test_entry_without_tool_id_skipped(self) -> None:
        runtime = {"tool_call_policies": {"inference": [{"payload": {}}]}}
        result = apply_tool_call_policy("inference", {}, {}, {}, runtime=runtime)
        assert result == []

    @pytest.mark.unit
    def test_successful_tool_call_included_in_results(self) -> None:
        tool_fn = MagicMock(return_value={"matched": True})
        runtime = {
            "tool_call_policies": {
                "inference": [{"tool_id": "checker", "payload": {}}]
            },
            "tool_fns": {"checker": tool_fn},
        }
        result = apply_tool_call_policy("inference", {}, {}, {}, runtime=runtime)
        assert len(result) == 1
        assert result[0]["tool_id"] == "checker"
        assert result[0]["result"]["matched"] is True

    @pytest.mark.unit
    def test_non_dict_entry_skipped(self) -> None:
        runtime = {"tool_call_policies": {"inference": ["not-a-dict"]}}
        result = apply_tool_call_policy("inference", {}, {}, {}, runtime=runtime)
        assert result == []

    @pytest.mark.unit
    def test_multiple_tools_all_called(self) -> None:
        fn_a = MagicMock(return_value={"a": 1})
        fn_b = MagicMock(return_value={"b": 2})
        runtime = {
            "tool_call_policies": {
                "inference": [
                    {"tool_id": "tool_a", "payload": {}},
                    {"tool_id": "tool_b", "payload": {}},
                ]
            },
            "tool_fns": {"tool_a": fn_a, "tool_b": fn_b},
        }
        result = apply_tool_call_policy("inference", {}, {}, {}, runtime=runtime)
        assert len(result) == 2
        tool_ids = [r["tool_id"] for r in result]
        assert "tool_a" in tool_ids
        assert "tool_b" in tool_ids
