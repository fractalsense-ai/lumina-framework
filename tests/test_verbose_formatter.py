"""Tests for lumina.api.verbose_formatter.

Covers _colorize, ColoredTurnFormatter.format, is_verbose, and
install_verbose_handler.
"""
from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from lumina.api.verbose_formatter import (
    ColoredTurnFormatter,
    _STAGE_COLORS,
    _colorize,
    install_verbose_handler,
    is_verbose,
)


# ── _colorize ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_colorize_known_stage_contains_tag() -> None:
    result = _colorize("GATE", "hello world")
    assert "[GATE]" in result
    assert "hello world" in result


@pytest.mark.unit
def test_colorize_unknown_stage_uses_white() -> None:
    result = _colorize("UNKNOWN_STAGE", "msg")
    assert "[UNKNOWN_STAGE]" in result


@pytest.mark.unit
def test_colorize_all_known_stages() -> None:
    for tag in _STAGE_COLORS:
        result = _colorize(tag, "test message")
        assert f"[{tag}]" in result
        assert "test message" in result


# ── ColoredTurnFormatter ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_colored_formatter_default_fmt() -> None:
    fmt = ColoredTurnFormatter()
    assert "%(asctime)s" in fmt._style._fmt
    assert "%(message)s" in fmt._style._fmt


@pytest.mark.unit
def test_colored_formatter_custom_fmt() -> None:
    fmt = ColoredTurnFormatter(fmt="%(message)s", datefmt="%H:%M:%S")
    assert fmt._style._fmt == "%(message)s"
    assert fmt.datefmt == "%H:%M:%S"


@pytest.mark.unit
def test_colored_formatter_formats_stage_message() -> None:
    fmt = ColoredTurnFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0,
        msg="[GATE] checking policy", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "[GATE]" in output


@pytest.mark.unit
def test_colored_formatter_passes_through_non_stage_message() -> None:
    fmt = ColoredTurnFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0,
        msg="plain message without brackets", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "plain message" in output


@pytest.mark.unit
def test_colored_formatter_unknown_stage_passes_through() -> None:
    """[UNKNOWNTAG] does not match a stage color — no colorization."""
    fmt = ColoredTurnFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="", lineno=0,
        msg="[NOTASTAGE] some info", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "NOTASTAGE" in output


# ── is_verbose ────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_is_verbose_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_VERBOSE", raising=False)
    assert is_verbose() is False


@pytest.mark.unit
def test_is_verbose_false_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_VERBOSE", "0")
    assert is_verbose() is False


@pytest.mark.unit
def test_is_verbose_false_when_false_str(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_VERBOSE", "false")
    assert is_verbose() is False


@pytest.mark.unit
def test_is_verbose_true_when_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_VERBOSE", "1")
    assert is_verbose() is True


@pytest.mark.unit
def test_is_verbose_true_when_true_str(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_VERBOSE", "true")
    assert is_verbose() is True


# ── install_verbose_handler ───────────────────────────────────────────────────


@pytest.mark.unit
def test_install_verbose_handler_sets_formatter() -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    original_handlers = root.handlers[:]
    root.handlers = [handler]
    try:
        install_verbose_handler()
        assert isinstance(handler.formatter, ColoredTurnFormatter)
    finally:
        root.handlers = original_handlers


@pytest.mark.unit
def test_install_verbose_handler_no_handlers() -> None:
    """Should not raise even when root logger has no handlers."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    root.handlers = []
    try:
        install_verbose_handler()  # should not raise
    finally:
        root.handlers = original_handlers
