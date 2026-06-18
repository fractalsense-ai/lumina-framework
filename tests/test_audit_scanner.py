"""Tests for lumina.system_log.audit_scanner.

Covers _has_guard_marker, scan_modules, scan_source_ast, and print_report.
"""
from __future__ import annotations

import importlib
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina.system_log.audit_scanner import (
    STATE_MUTATING_ENDPOINTS,
    _has_guard_marker,
    print_report,
    scan_modules,
    scan_source_ast,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ── _has_guard_marker ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_has_guard_marker_true() -> None:
    fn = MagicMock()
    fn._requires_log_commit = True
    assert _has_guard_marker(fn) is True


@pytest.mark.unit
def test_has_guard_marker_false_missing() -> None:
    fn = MagicMock(spec=[])  # no _requires_log_commit attribute
    assert _has_guard_marker(fn) is False


@pytest.mark.unit
def test_has_guard_marker_false_wrong_value() -> None:
    fn = MagicMock()
    fn._requires_log_commit = False
    assert _has_guard_marker(fn) is False


@pytest.mark.unit
def test_has_guard_marker_false_non_bool() -> None:
    fn = MagicMock()
    fn._requires_log_commit = 1  # truthy but not exactly True
    assert _has_guard_marker(fn) is False


# ── scan_modules ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_scan_modules_returns_dict() -> None:
    result = scan_modules()
    assert isinstance(result, dict)


@pytest.mark.unit
def test_scan_modules_import_error_recorded() -> None:
    """When a module cannot be imported, its functions are listed as unguarded."""
    with patch("lumina.system_log.audit_scanner.importlib.import_module",
               side_effect=ImportError("missing module")):
        result = scan_modules()
    # All modules should be listed as unguarded since every import fails
    for mod_name in STATE_MUTATING_ENDPOINTS:
        assert mod_name in result


@pytest.mark.unit
def test_scan_modules_missing_function() -> None:
    """Function not found on the module is recorded as missing."""
    mock_mod = MagicMock(spec=[])  # no attributes
    with patch("lumina.system_log.audit_scanner.importlib.import_module",
               return_value=mock_mod):
        result = scan_modules()
    # All functions missing → all modules unguarded
    for mod_name in STATE_MUTATING_ENDPOINTS:
        assert mod_name in result


@pytest.mark.unit
def test_scan_modules_guarded_function_not_listed() -> None:
    """Properly guarded functions do not appear in the unguarded report."""
    guarded_fn = MagicMock()
    guarded_fn._requires_log_commit = True

    mock_mod = MagicMock()
    # Make every expected function guarded
    for fn_name in STATE_MUTATING_ENDPOINTS.get("chat", {"chat"}):
        setattr(mock_mod, fn_name, guarded_fn)

    with patch("lumina.system_log.audit_scanner.importlib.import_module",
               return_value=mock_mod):
        result = scan_modules()
    # "chat" module should be absent from the result
    assert "chat" not in result


# ── scan_source_ast ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_scan_source_ast_returns_dict() -> None:
    result = scan_source_ast()
    assert isinstance(result, dict)


@pytest.mark.unit
def test_scan_source_ast_missing_routes_dir(tmp_path: Path) -> None:
    """Non-existent routes dir → all modules listed as unguarded."""
    result = scan_source_ast(routes_dir=tmp_path / "nonexistent")
    for mod_name in STATE_MUTATING_ENDPOINTS:
        assert mod_name in result


@pytest.mark.unit
def test_scan_source_ast_syntax_error(tmp_path: Path) -> None:
    """Syntax error in a source file → module listed as unguarded."""
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    bad_file = routes_dir / "chat.py"
    bad_file.write_text("def broken(:\n", encoding="utf-8")

    result = scan_source_ast(routes_dir=routes_dir)
    assert "chat" in result


@pytest.mark.unit
def test_scan_source_ast_with_decorated_function(tmp_path: Path) -> None:
    """Function decorated with @requires_log_commit is not reported as missing."""
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    chat_file = routes_dir / "chat.py"
    chat_file.write_text(
        "@requires_log_commit\nasync def chat(): pass\n",
        encoding="utf-8",
    )

    result = scan_source_ast(routes_dir=routes_dir)
    assert "chat" not in result


@pytest.mark.unit
def test_scan_source_ast_undecorated_function_flagged(tmp_path: Path) -> None:
    """Function without @requires_log_commit is flagged."""
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    chat_file = routes_dir / "chat.py"
    chat_file.write_text("async def chat(): pass\n", encoding="utf-8")

    result = scan_source_ast(routes_dir=routes_dir)
    assert "chat" in result
    assert "chat" in result["chat"]


# ── print_report ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_print_report_all_clear(capsys: pytest.CaptureFixture) -> None:
    print_report({})
    captured = capsys.readouterr()
    assert "All state-mutating endpoints are guarded" in captured.out


@pytest.mark.unit
def test_print_report_shows_unguarded(capsys: pytest.CaptureFixture) -> None:
    print_report({"auth": ["register", "delete_user"]})
    captured = capsys.readouterr()
    assert "lumina.api.routes.auth.register" in captured.out
    assert "lumina.api.routes.auth.delete_user" in captured.out


@pytest.mark.unit
def test_print_report_shows_total_count(capsys: pytest.CaptureFixture) -> None:
    print_report({"auth": ["register"], "staging": ["create_staged_file"]})
    captured = capsys.readouterr()
    assert "2 unguarded" in captured.out
