"""Tests for lumina.ingestion.extractors.

Covers extract_text, extract_structured, and format-specific extractors.
Tests avoid real PDF/DOCX binary fixtures; optional dependency paths are
verified via ImportError simulation.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import patch

import pytest

from lumina.ingestion.extractors import (
    extract_structured,
    extract_text,
    _extract_csv,
    _extract_json,
    _extract_markdown,
    _extract_yaml,
)


# ── extract_text dispatch ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_extract_text_unsupported_type() -> None:
    with pytest.raises(ValueError, match="Unsupported content type"):
        extract_text(b"data", "xlsx")


@pytest.mark.unit
def test_extract_text_markdown() -> None:
    result = extract_text(b"# Heading\nSome text.", "markdown")
    assert "Heading" in result


@pytest.mark.unit
def test_extract_text_csv() -> None:
    result = extract_text(b"name,age\nAlice,30\nBob,25", "csv")
    assert "Alice" in result
    assert "30" in result


@pytest.mark.unit
def test_extract_text_json() -> None:
    data = json.dumps({"key": "value"}).encode("utf-8")
    result = extract_text(data, "json")
    assert '"key"' in result
    assert '"value"' in result


@pytest.mark.unit
def test_extract_text_yaml() -> None:
    result = extract_text(b"key: value\n", "yaml")
    assert "key" in result


# ── extract_structured ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_extract_structured_json() -> None:
    data = json.dumps({"x": 1}).encode("utf-8")
    result = extract_structured(data, "json")
    assert result == {"x": 1}


@pytest.mark.unit
def test_extract_structured_yaml() -> None:
    result = extract_structured(b"x: 1\ny: hello\n", "yaml")
    assert result["x"] == 1
    assert result["y"] == "hello"


@pytest.mark.unit
def test_extract_structured_unsupported_type() -> None:
    with pytest.raises(ValueError, match="extract_structured only supports json/yaml"):
        extract_structured(b"data", "csv")


# ── PDF extractor — ImportError path ─────────────────────────────────────────


@pytest.mark.unit
def test_extract_pdf_import_error() -> None:
    """When pdfplumber is not installed, a RuntimeError is raised."""
    with patch.dict(sys.modules, {"pdfplumber": None}):
        with pytest.raises((RuntimeError, ImportError)):
            extract_text(b"%PDF-fake", "pdf")


# ── DOCX extractor — ImportError path ────────────────────────────────────────


@pytest.mark.unit
def test_extract_docx_import_error() -> None:
    """When python-docx is not installed, a RuntimeError is raised."""
    with patch.dict(sys.modules, {"docx": None}):
        with pytest.raises((RuntimeError, ImportError)):
            extract_text(b"PK\x03\x04fake-docx", "docx")


# ── Format-specific extractors ────────────────────────────────────────────────


@pytest.mark.unit
def test_extract_markdown_utf8() -> None:
    text = "# Title\n\nParagraph with **bold**."
    result = _extract_markdown(text.encode("utf-8"))
    assert result == text


@pytest.mark.unit
def test_extract_markdown_latin1_bytes() -> None:
    """Non-UTF-8 bytes are replaced rather than raising."""
    result = _extract_markdown(b"caf\xe9")
    assert "caf" in result


@pytest.mark.unit
def test_extract_csv_produces_pipe_separated_rows() -> None:
    result = _extract_csv(b"a,b,c\n1,2,3\n")
    assert "a | b | c" in result
    assert "1 | 2 | 3" in result


@pytest.mark.unit
def test_extract_json_pretty_prints() -> None:
    data = {"z": 2, "a": 1}
    raw = json.dumps(data).encode("utf-8")
    result = _extract_json(raw)
    parsed = json.loads(result)
    assert parsed == data


@pytest.mark.unit
def test_extract_yaml_passthrough() -> None:
    raw = b"key: value\nlist:\n  - item1\n"
    result = _extract_yaml(raw)
    assert "key: value" in result
