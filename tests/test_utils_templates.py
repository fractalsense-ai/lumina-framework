"""Tests for lumina.api.utils.templates.

Covers resolve_context_path and render_template_value.
"""
from __future__ import annotations

import pytest

from lumina.api.utils.templates import render_template_value, resolve_context_path


# ── resolve_context_path ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_resolve_simple_key() -> None:
    ctx = {"name": "Alice"}
    assert resolve_context_path(ctx, "name") == "Alice"


@pytest.mark.unit
def test_resolve_nested_key() -> None:
    ctx = {"user": {"role": "teacher"}}
    assert resolve_context_path(ctx, "user.role") == "teacher"


@pytest.mark.unit
def test_resolve_deeply_nested() -> None:
    ctx = {"a": {"b": {"c": 42}}}
    assert resolve_context_path(ctx, "a.b.c") == 42


@pytest.mark.unit
def test_resolve_missing_key_returns_none() -> None:
    ctx = {"name": "Alice"}
    assert resolve_context_path(ctx, "missing") is None


@pytest.mark.unit
def test_resolve_missing_intermediate_returns_none() -> None:
    ctx = {"user": {"role": "teacher"}}
    assert resolve_context_path(ctx, "user.sub.id") is None


@pytest.mark.unit
def test_resolve_non_dict_intermediate_returns_none() -> None:
    ctx = {"user": "not_a_dict"}
    assert resolve_context_path(ctx, "user.role") is None


# ── render_template_value ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_render_plain_string_passthrough() -> None:
    assert render_template_value("hello", {}) == "hello"


@pytest.mark.unit
def test_render_single_placeholder_substitutes() -> None:
    ctx = {"name": "Alice"}
    assert render_template_value("{name}", ctx) == "Alice"


@pytest.mark.unit
def test_render_single_placeholder_preserves_type() -> None:
    """Single placeholder with numeric value returns the original type."""
    ctx = {"count": 5}
    result = render_template_value("{count}", ctx)
    assert result == 5


@pytest.mark.unit
def test_render_multiple_placeholders() -> None:
    ctx = {"first": "Hello", "second": "World"}
    result = render_template_value("{first}, {second}!", ctx)
    assert result == "Hello, World!"


@pytest.mark.unit
def test_render_missing_placeholder_becomes_empty() -> None:
    ctx = {}
    result = render_template_value("Hello {name}!", ctx)
    assert result == "Hello !"


@pytest.mark.unit
def test_render_nested_placeholder() -> None:
    ctx = {"user": {"name": "Bob"}}
    result = render_template_value("{user.name}", ctx)
    assert result == "Bob"


@pytest.mark.unit
def test_render_dict_value() -> None:
    ctx = {"x": "A"}
    result = render_template_value({"key": "{x}"}, ctx)
    assert result == {"key": "A"}


@pytest.mark.unit
def test_render_list_value() -> None:
    ctx = {"v": "Z"}
    result = render_template_value(["{v}", "literal"], ctx)
    assert result == ["Z", "literal"]


@pytest.mark.unit
def test_render_non_string_passthrough() -> None:
    assert render_template_value(42, {}) == 42
    assert render_template_value(True, {}) is True
    assert render_template_value(None, {}) is None


@pytest.mark.unit
def test_render_boolean_single_placeholder() -> None:
    ctx = {"flag": True}
    result = render_template_value("{flag}", ctx)
    assert result is True
