"""Focused deterministic tests for lumina.ingestion.interpreter.

These tests keep the SLM-adjacent ingestion path covered without live model
calls, secrets, local model servers, or external APIs.
"""
from __future__ import annotations

import json

from lumina.ingestion.interpreter import generate_interpretations


def _domain_physics() -> dict:
    return {
        "id": "education",
        "description": "Test education domain",
        "invariants": [
            {"id": "inv-safe"},
            {"id": "inv-progress"},
        ],
        "standing_orders": [
            {"id": "so-escalate"},
        ],
    }


def test_generate_interpretations_uses_imported_call_slm_when_not_injected(monkeypatch):
    captured = {}

    def fake_call_slm(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return json.dumps({
            "interpretations": [
                {
                    "label": "default",
                    "yaml_content": "modules: []",
                    "confidence": 0.95,
                    "ambiguity_notes": "clear mapping",
                }
            ]
        })

    monkeypatch.setattr("lumina.core.slm.call_slm", fake_call_slm)

    result = generate_interpretations(
        extracted_text="Raw lesson text",
        domain_physics=_domain_physics(),
        glossary=[{"term": "variable"}, {"term": "equation"}],
        module_context={"module_id": "algebra", "version": "1.0.0"},
        max_interpretations=2,
    )

    payload = json.loads(captured["user"])
    assert "structured document interpreter" in captured["system"]
    assert payload["document_text"] == "Raw lesson text"
    assert payload["domain_id"] == "education"
    assert payload["domain_description"] == "Test education domain"
    assert payload["existing_invariants"] == ["inv-safe", "inv-progress"]
    assert payload["existing_standing_orders"] == ["so-escalate"]
    assert payload["glossary_terms"] == ["variable", "equation"]
    assert payload["target_module"] == {"module_id": "algebra", "version": "1.0.0"}
    assert payload["max_interpretations"] == 2
    assert result[0]["id"]
    assert result[0]["label"] == "default"
    assert result[0]["yaml_content"] == "modules: []"
    assert result[0]["confidence"] == 0.95
    assert result[0]["ambiguity_notes"] == "clear mapping"


def test_generate_interpretations_defaults_missing_response_fields():
    def fake_slm(system: str, user: str) -> str:
        return json.dumps({"interpretations": [{}]})

    result = generate_interpretations(
        extracted_text="Sparse response",
        domain_physics=_domain_physics(),
        call_slm_fn=fake_slm,
    )

    assert len(result) == 1
    assert result[0]["id"]
    assert result[0]["label"] == "default"
    assert result[0]["yaml_content"] == ""
    assert result[0]["confidence"] == 0.5
    assert result[0]["ambiguity_notes"] == ""


def test_generate_interpretations_coerces_yaml_confidence_and_notes_fields():
    def fake_slm(system: str, user: str) -> str:
        return json.dumps({
            "interpretations": [
                {
                    "label": "loose",
                    "yaml_content": {"module": "algebra"},
                    "confidence": "0.75",
                    "ambiguity_notes": None,
                }
            ]
        })

    result = generate_interpretations(
        extracted_text="Coerce response",
        domain_physics=_domain_physics(),
        call_slm_fn=fake_slm,
    )

    assert result[0]["label"] == "loose"
    assert result[0]["yaml_content"] == "{'module': 'algebra'}"
    assert result[0]["confidence"] == 0.75
    assert result[0]["ambiguity_notes"] == "None"


def test_generate_interpretations_falls_back_on_invalid_json():
    def fake_slm(system: str, user: str) -> str:
        return "not json"

    result = generate_interpretations(
        extracted_text="Line one\nLine two",
        domain_physics=_domain_physics(),
        call_slm_fn=fake_slm,
    )

    assert len(result) == 1
    assert result[0]["id"]
    assert result[0]["label"] == "default"
    assert result[0]["confidence"] == 0.0
    assert "SLM extraction unavailable" in result[0]["yaml_content"]
    assert "Line one" in result[0]["yaml_content"]
    assert "Line two" in result[0]["yaml_content"]
    assert "manual review" in result[0]["ambiguity_notes"].lower()


def test_generate_interpretations_fallback_truncates_preserved_raw_text():
    long_text = "x" * 4000 + "TAIL"

    result = generate_interpretations(
        extracted_text=long_text,
        domain_physics=_domain_physics(),
        call_slm_fn=lambda **_kw: "not json",
    )

    preserved = result[0]["yaml_content"]
    assert "x" * 4000 in preserved
    assert "TAIL" not in preserved
