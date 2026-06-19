"""Deterministic tests for lumina.daemon.tasks — proposal-generating task functions.

Covers: glossary_expansion, glossary_pruning, rejection_corpus_alignment,
cross_module_consistency, and domain_physics_constraint_refresh.

All tests use fake persistence stubs and no live services.
"""
from __future__ import annotations

from typing import Any

import pytest

from lumina.daemon.tasks import (
    cross_module_consistency,
    domain_physics_constraint_refresh,
    get_task,
    glossary_expansion,
    glossary_pruning,
    rejection_corpus_alignment,
)


# ── Minimal fake persistence ──────────────────────────────────────────────────


class _FakePersistence:
    """Persistence stub — implements only the query_log_records interface."""

    def __init__(self, records: list[dict] | None = None) -> None:
        self._records: list[dict] = records or []

    def query_log_records(
        self,
        domain_id: str | None = None,
        limit: int = 100,
        **_kw: Any,
    ) -> list[dict]:
        return self._records[:limit]


def _ingestion_record(yaml_content: str) -> dict:
    return {
        "record_type": "IngestionRecord",
        "interpretations": [{"yaml_content": yaml_content}],
    }


# ── Task registration ─────────────────────────────────────────────────────────


class TestTaskRegistry:

    @pytest.mark.unit
    def test_all_covered_tasks_are_registered(self) -> None:
        for name in (
            "glossary_expansion",
            "glossary_pruning",
            "rejection_corpus_alignment",
            "cross_module_consistency",
            "domain_physics_constraint_refresh",
        ):
            assert get_task(name) is not None, f"Task '{name}' not in registry"


# ── glossary_expansion ────────────────────────────────────────────────────────


class TestGlossaryExpansion:

    @pytest.mark.unit
    def test_none_persistence_returns_success_no_proposals(self) -> None:
        result = glossary_expansion("edu", {})
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_new_terms_from_ingestion_become_proposals(self) -> None:
        pers = _FakePersistence([
            _ingestion_record("polynomial: mapping of coefficients"),
        ])
        result = glossary_expansion("edu", {}, persistence=pers)
        assert result.success is True
        terms = {p.detail["term"] for p in result.proposals}
        assert "polynomial" in terms
        assert "mapping" in terms
        assert "coefficients" in terms

    @pytest.mark.unit
    def test_existing_glossary_terms_not_proposed(self) -> None:
        pers = _FakePersistence([_ingestion_record("polynomial equation")])
        domain_physics = {"glossary": [{"term": "polynomial"}]}
        result = glossary_expansion("edu", domain_physics, persistence=pers)
        terms = {p.detail["term"] for p in result.proposals}
        assert "polynomial" not in terms
        assert "equation" in terms  # new and long enough

    @pytest.mark.unit
    def test_words_three_chars_or_fewer_are_skipped(self) -> None:
        pers = _FakePersistence([_ingestion_record("add sub mul divides")])
        result = glossary_expansion("edu", {}, persistence=pers)
        terms = {p.detail["term"] for p in result.proposals}
        assert "add" not in terms
        assert "sub" not in terms
        assert "mul" not in terms
        assert "divides" in terms

    @pytest.mark.unit
    def test_punctuation_stripped_from_word_candidates(self) -> None:
        pers = _FakePersistence([_ingestion_record("invariant: coefficient,")])
        result = glossary_expansion("edu", {}, persistence=pers)
        terms = {p.detail["term"] for p in result.proposals}
        assert "invariant" in terms
        assert "invariant:" not in terms
        assert "coefficient" in terms
        assert "coefficient," not in terms

    @pytest.mark.unit
    def test_non_ingestion_records_are_ignored(self) -> None:
        pers = _FakePersistence([
            {"record_type": "TraceEvent", "interpretations": [{"yaml_content": "polynomial: term"}]},
        ])
        result = glossary_expansion("edu", {}, persistence=pers)
        assert result.proposals == []

    @pytest.mark.unit
    def test_persistence_exception_returns_success_empty_proposals(self) -> None:
        class _BrokenPersistence:
            def query_log_records(self, **_kw: Any) -> list:
                raise RuntimeError("DB unavailable")

        result = glossary_expansion("edu", {}, persistence=_BrokenPersistence())
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_proposal_fields_are_correct(self) -> None:
        pers = _FakePersistence([_ingestion_record("eigenvalue decomposition")])
        result = glossary_expansion("edu", {}, persistence=pers)
        assert len(result.proposals) > 0
        p = result.proposals[0]
        assert p.task == "glossary_expansion"
        assert p.domain_id == "edu"
        assert p.proposal_type == "glossary_add"
        assert "term" in p.detail
        assert p.detail["source"] == "ingestion"


# ── glossary_pruning ──────────────────────────────────────────────────────────


class TestGlossaryPruning:

    @pytest.mark.unit
    def test_term_without_definition_becomes_prune_proposal(self) -> None:
        domain_physics = {
            "glossary": [
                {"term": "polynomial"},                          # no definition
                {"term": "coefficient", "definition": "A multiplier."},
            ]
        }
        result = glossary_pruning("edu", domain_physics)
        assert result.success is True
        assert len(result.proposals) == 1
        assert result.proposals[0].detail["term"] == "polynomial"
        assert result.proposals[0].proposal_type == "glossary_prune"

    @pytest.mark.unit
    def test_all_terms_with_definitions_no_proposals(self) -> None:
        domain_physics = {
            "glossary": [
                {"term": "polynomial", "definition": "A sum of terms."},
                {"term": "coefficient", "definition": "A multiplier."},
            ]
        }
        result = glossary_pruning("edu", domain_physics)
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_empty_glossary_no_proposals(self) -> None:
        result = glossary_pruning("edu", {})
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_proposal_summary_contains_term_name(self) -> None:
        domain_physics = {"glossary": [{"term": "eigenvalue"}]}
        result = glossary_pruning("edu", domain_physics)
        assert "eigenvalue" in result.proposals[0].summary

    @pytest.mark.unit
    def test_task_and_domain_id_on_proposal(self) -> None:
        domain_physics = {"glossary": [{"term": "matrix"}]}
        result = glossary_pruning("linear-alg", domain_physics)
        p = result.proposals[0]
        assert p.task == "glossary_pruning"
        assert p.domain_id == "linear-alg"


# ── rejection_corpus_alignment ────────────────────────────────────────────────


class TestRejectionCorpusAlignment:

    @pytest.mark.unit
    def test_stale_module_ref_becomes_proposal(self) -> None:
        domain_physics = {
            "rejection_corpus": [{"module_id": "algebra-advanced", "text": "Not ready"}],
            "modules": [{"module_id": "algebra-basic"}],
        }
        result = rejection_corpus_alignment("edu", domain_physics)
        assert result.success is True
        assert len(result.proposals) == 1
        assert result.proposals[0].proposal_type == "rejection_stale"
        assert "algebra-advanced" in result.proposals[0].summary

    @pytest.mark.unit
    def test_valid_module_ref_no_proposal(self) -> None:
        domain_physics = {
            "rejection_corpus": [{"module_id": "algebra-basic", "text": "Not ready"}],
            "modules": [{"module_id": "algebra-basic"}],
        }
        result = rejection_corpus_alignment("edu", domain_physics)
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_empty_rejection_corpus_no_proposals(self) -> None:
        result = rejection_corpus_alignment("edu", {"modules": [{"module_id": "m1"}]})
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_entry_without_module_id_skipped(self) -> None:
        domain_physics = {
            "rejection_corpus": [{"text": "No module ref here"}],
            "modules": [],
        }
        result = rejection_corpus_alignment("edu", domain_physics)
        assert result.proposals == []

    @pytest.mark.unit
    def test_multiple_stale_refs_each_get_proposal(self) -> None:
        domain_physics = {
            "rejection_corpus": [
                {"module_id": "removed-1"},
                {"module_id": "removed-2"},
            ],
            "modules": [],
        }
        result = rejection_corpus_alignment("edu", domain_physics)
        assert len(result.proposals) == 2


# ── cross_module_consistency ──────────────────────────────────────────────────


class TestCrossModuleConsistency:

    @pytest.mark.unit
    def test_direct_prerequisite_cycle_detected(self) -> None:
        domain_physics = {
            "modules": [
                {"module_id": "algebra", "prerequisites": ["geometry"]},
                {"module_id": "geometry", "prerequisites": ["algebra"]},
            ]
        }
        result = cross_module_consistency("edu", domain_physics)
        assert result.success is True
        assert len(result.proposals) >= 1
        assert any(p.proposal_type == "prerequisite_cycle" for p in result.proposals)

    @pytest.mark.unit
    def test_acyclic_prerequisites_no_proposals(self) -> None:
        domain_physics = {
            "modules": [
                {"module_id": "algebra", "prerequisites": []},
                {"module_id": "calculus", "prerequisites": ["algebra"]},
            ]
        }
        result = cross_module_consistency("edu", domain_physics)
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_empty_modules_no_proposals(self) -> None:
        result = cross_module_consistency("edu", {})
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_cycle_proposal_identifies_both_modules(self) -> None:
        domain_physics = {
            "modules": [
                {"module_id": "mod-a", "prerequisites": ["mod-b"]},
                {"module_id": "mod-b", "prerequisites": ["mod-a"]},
            ]
        }
        result = cross_module_consistency("edu", domain_physics)
        p = result.proposals[0]
        assert {p.detail["module_a"], p.detail["module_b"]} == {"mod-a", "mod-b"}

    @pytest.mark.unit
    def test_no_prerequisites_key_treated_as_empty(self) -> None:
        domain_physics = {
            "modules": [
                {"module_id": "standalone"},  # no prerequisites key
            ]
        }
        result = cross_module_consistency("edu", domain_physics)
        assert result.proposals == []


# ── domain_physics_constraint_refresh ────────────────────────────────────────


class TestDomainPhysicsConstraintRefresh:

    @pytest.mark.unit
    def test_invariant_with_missing_module_becomes_proposal(self) -> None:
        domain_physics = {
            "invariants": [{"id": "inv-1", "applies_to": ["deleted-module"]}],
            "modules": [{"module_id": "active-module"}],
        }
        result = domain_physics_constraint_refresh("edu", domain_physics)
        assert result.success is True
        assert len(result.proposals) == 1
        assert result.proposals[0].proposal_type == "invariant_orphan"
        assert "deleted-module" in result.proposals[0].summary

    @pytest.mark.unit
    def test_invariant_with_valid_module_no_proposal(self) -> None:
        domain_physics = {
            "invariants": [{"id": "inv-1", "applies_to": ["active-module"]}],
            "modules": [{"module_id": "active-module"}],
        }
        result = domain_physics_constraint_refresh("edu", domain_physics)
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_invariant_without_applies_to_no_proposal(self) -> None:
        domain_physics = {
            "invariants": [{"id": "inv-no-refs"}],
            "modules": [],
        }
        result = domain_physics_constraint_refresh("edu", domain_physics)
        assert result.proposals == []

    @pytest.mark.unit
    def test_empty_domain_physics_no_proposals(self) -> None:
        result = domain_physics_constraint_refresh("edu", {})
        assert result.success is True
        assert result.proposals == []

    @pytest.mark.unit
    def test_proposal_detail_contains_invariant_and_module(self) -> None:
        domain_physics = {
            "invariants": [{"id": "inv-orphan", "applies_to": ["ghost-mod"]}],
            "modules": [],
        }
        result = domain_physics_constraint_refresh("edu", domain_physics)
        p = result.proposals[0]
        assert p.detail["invariant_id"] == "inv-orphan"
        assert p.detail["missing_module"] == "ghost-mod"

    @pytest.mark.unit
    def test_multiple_missing_modules_produce_multiple_proposals(self) -> None:
        domain_physics = {
            "invariants": [{"id": "inv-wide", "applies_to": ["mod-gone-1", "mod-gone-2"]}],
            "modules": [],
        }
        result = domain_physics_constraint_refresh("edu", domain_physics)
        assert len(result.proposals) == 2
