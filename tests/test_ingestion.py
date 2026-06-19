"""Tests for the document ingestion pipeline.

Covers: extractors, interpreter (with mock SLM), IngestService lifecycle,
RBAC gating, multi-interpretation review, and System Log commitment.
"""

from __future__ import annotations

import json
import uuid

import pytest


# ── Extractor tests ──────────────────────────────────────────

class TestExtractors:
    """Tests for lumina.ingestion.extractors."""

    def test_extract_markdown(self):
        from lumina.ingestion.extractors import extract_text
        raw = b"# Title\n\nSome paragraph."
        assert extract_text(raw, "markdown") == "# Title\n\nSome paragraph."

    def test_extract_csv(self):
        from lumina.ingestion.extractors import extract_text
        raw = b"a,b,c\n1,2,3\n"
        result = extract_text(raw, "csv")
        assert "a | b | c" in result
        assert "1 | 2 | 3" in result

    def test_extract_json(self):
        from lumina.ingestion.extractors import extract_text
        raw = json.dumps({"key": "value"}).encode()
        result = extract_text(raw, "json")
        assert '"key"' in result
        assert '"value"' in result

    def test_extract_yaml(self):
        from lumina.ingestion.extractors import extract_text
        raw = b"key: value\nlist:\n  - one\n"
        result = extract_text(raw, "yaml")
        assert "key: value" in result

    def test_extract_unsupported_raises(self):
        from lumina.ingestion.extractors import extract_text
        with pytest.raises(ValueError, match="Unsupported content type"):
            extract_text(b"data", "binary")

    def test_extract_structured_json(self):
        from lumina.ingestion.extractors import extract_structured
        raw = json.dumps({"a": 1}).encode()
        assert extract_structured(raw, "json") == {"a": 1}

    def test_extract_structured_unsupported(self):
        from lumina.ingestion.extractors import extract_structured
        with pytest.raises(ValueError, match="only supports json/yaml"):
            extract_structured(b"hi", "csv")


# ── Interpreter tests ───────────────────────────────────────

class TestInterpreter:
    """Tests for lumina.ingestion.interpreter (with mock SLM)."""

    @staticmethod
    def _mock_slm_single(**_kw):
        return json.dumps({
            "interpretations": [{
                "label": "default",
                "yaml_content": "module_id: test-mod\nartifacts: []",
                "confidence": 0.95,
                "ambiguity_notes": "Unambiguous mapping.",
            }]
        })

    @staticmethod
    def _mock_slm_multi(**_kw):
        return json.dumps({
            "interpretations": [
                {"label": "strict", "yaml_content": "strict: true", "confidence": 0.8, "ambiguity_notes": ""},
                {"label": "loose", "yaml_content": "loose: true", "confidence": 0.6, "ambiguity_notes": ""},
                {"label": "hierarchical", "yaml_content": "hier: true", "confidence": 0.5, "ambiguity_notes": ""},
            ]
        })

    def test_single_interpretation(self):
        from lumina.ingestion.interpreter import generate_interpretations
        result = generate_interpretations(
            extracted_text="hello world",
            domain_physics={"id": "test", "description": "test domain"},
            call_slm_fn=self._mock_slm_single,
        )
        assert len(result) == 1
        assert result[0]["label"] == "default"
        assert result[0]["confidence"] == 0.95
        assert "id" in result[0]

    def test_multi_interpretation(self):
        from lumina.ingestion.interpreter import generate_interpretations
        result = generate_interpretations(
            extracted_text="ambiguous content",
            domain_physics={"id": "test"},
            max_interpretations=3,
            call_slm_fn=self._mock_slm_multi,
        )
        assert len(result) == 3
        labels = {r["label"] for r in result}
        assert labels == {"strict", "loose", "hierarchical"}

    def test_max_interpretations_limit(self):
        from lumina.ingestion.interpreter import generate_interpretations
        result = generate_interpretations(
            extracted_text="content",
            domain_physics={"id": "test"},
            max_interpretations=1,
            call_slm_fn=self._mock_slm_multi,
        )
        assert len(result) == 1

    def test_slm_payload_scopes_context_and_module_context(self):
        from lumina.ingestion.interpreter import generate_interpretations

        captured = {}

        def capture_slm(**kw):
            captured.update(kw)
            return self._mock_slm_single()

        long_text = "x" * 8100
        result = generate_interpretations(
            extracted_text=long_text,
            domain_physics={
                "id": "domain-a",
                "description": "A deterministic test domain.",
                "invariants": [{"id": "inv-1"}],
                "standing_orders": [{"id": "so-1"}],
            },
            glossary=[{"term": "Artifact"}],
            module_context={"id": "module-a", "version": "1.0.0"},
            max_interpretations=2,
            call_slm_fn=capture_slm,
        )

        user_payload = json.loads(captured["user"])
        assert result[0]["label"] == "default"
        assert user_payload["document_text"] == long_text[:8000]
        assert user_payload["domain_id"] == "domain-a"
        assert user_payload["domain_description"] == "A deterministic test domain."
        assert user_payload["existing_invariants"] == ["inv-1"]
        assert user_payload["existing_standing_orders"] == ["so-1"]
        assert user_payload["glossary_terms"] == ["Artifact"]
        assert user_payload["target_module"] == {"id": "module-a", "version": "1.0.0"}
        assert user_payload["max_interpretations"] == 2
        assert "structured document interpreter" in captured["system"]

    def test_markdown_fenced_json_response_is_parsed(self):
        from lumina.ingestion.interpreter import generate_interpretations

        def fenced_slm(**_kw):
            return "```json\n" + self._mock_slm_single() + "\n```"

        result = generate_interpretations(
            extracted_text="content",
            domain_physics={"id": "test"},
            call_slm_fn=fenced_slm,
        )

        assert len(result) == 1
        assert result[0]["label"] == "default"
        assert result[0]["yaml_content"] == "module_id: test-mod\nartifacts: []"

    @pytest.mark.parametrize(
        "raw_response",
        [
            "[]",
            json.dumps({"interpretations": []}),
            json.dumps({"interpretations": "default"}),
        ],
    )
    def test_invalid_slm_response_returns_fallback(self, raw_response):
        from lumina.ingestion.interpreter import generate_interpretations

        result = generate_interpretations(
            extracted_text="preserve me",
            domain_physics={"id": "test"},
            call_slm_fn=lambda **_kw: raw_response,
        )

        assert len(result) == 1
        assert result[0]["label"] == "default"
        assert result[0]["confidence"] == 0.0
        assert "preserve me" in result[0]["yaml_content"]

    def test_slm_failure_returns_fallback(self):
        from lumina.ingestion.interpreter import generate_interpretations

        def bad_slm(**_kw):
            raise RuntimeError("SLM offline")

        result = generate_interpretations(
            extracted_text="some text",
            domain_physics={"id": "test"},
            call_slm_fn=bad_slm,
        )
        assert len(result) == 1
        assert result[0]["confidence"] == 0.0
        assert "raw text preserved" in result[0]["ambiguity_notes"]


# ── IngestService lifecycle tests ────────────────────────────

class TestIngestService:
    """Full lifecycle: accept → extract → review → commit."""

    @staticmethod
    def _make_service(**kw):
        from lumina.ingestion.service import IngestService
        defaults = {
            "max_file_size_mb": 1,
            "call_slm_fn": lambda **_kw: json.dumps({
                "interpretations": [{
                    "label": "default",
                    "yaml_content": "module_id: m1\nartifacts: []",
                    "confidence": 0.9,
                    "ambiguity_notes": "",
                }]
            }),
        }
        defaults.update(kw)
        return IngestService(**defaults)

    # ── accept_document ──

    def test_accept_returns_doc_id(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"hello",
            filename="test.md",
            content_type="markdown",
            actor_id="user1",
            domain_id="dom1",
        )
        assert isinstance(doc_id, str)
        record = svc.get_record(doc_id)
        assert record is not None
        assert record["status"] == "pending_extraction"
        assert record["domain_id"] == "dom1"

    def test_accept_rejects_oversized(self):
        svc = self._make_service(max_file_size_mb=0)
        # 1 byte > 0 MB limit
        with pytest.raises(ValueError, match="exceeds limit"):
            svc.accept_document(
                file_bytes=b"x" * 1024,
                filename="big.md",
                content_type="markdown",
                actor_id="u",
                domain_id="d",
            )

    def test_accept_rejects_invalid_type(self):
        svc = self._make_service()
        with pytest.raises(ValueError, match="Unsupported content type"):
            svc.accept_document(
                file_bytes=b"x",
                filename="f.bin",
                content_type="binary",
                actor_id="u",
                domain_id="d",
            )

    # ── extract_interpretations ──

    def test_extract_produces_interpretations(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"data",
            filename="test.md",
            content_type="markdown",
            actor_id="user1",
            domain_id="dom1",
        )
        interps = svc.extract_interpretations(doc_id, domain_physics={"id": "dom1"})
        assert len(interps) >= 1
        assert interps[0]["label"] == "default"

        record = svc.get_record(doc_id)
        assert record["status"] == "extraction_complete"

    def test_extract_missing_doc_raises(self):
        svc = self._make_service()
        with pytest.raises(ValueError, match="not found"):
            svc.extract_interpretations("nonexistent", domain_physics={})

    # ── review_interpretation ──

    def test_review_approve(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"data",
            filename="test.md",
            content_type="markdown",
            actor_id="u1",
            domain_id="d1",
        )
        interps = svc.extract_interpretations(doc_id, domain_physics={"id": "d1"})
        interp_id = interps[0]["id"]

        result = svc.review_interpretation(
            doc_id,
            decision="approve",
            reviewer_id="da1",
            selected_interpretation_id=interp_id,
        )
        assert result["status"] == "approved"
        assert result["selected_interpretation_id"] == interp_id

    def test_review_reject(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"data",
            filename="test.md",
            content_type="markdown",
            actor_id="u",
            domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})

        result = svc.review_interpretation(
            doc_id, decision="reject", reviewer_id="da"
        )
        assert result["status"] == "rejected"

    def test_review_approve_requires_interpretation_id(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})

        with pytest.raises(ValueError, match="selected_interpretation_id required"):
            svc.review_interpretation(doc_id, decision="approve", reviewer_id="da")

    def test_review_edit_creates_new_interpretation(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})

        result = svc.review_interpretation(
            doc_id,
            decision="edit",
            reviewer_id="da",
            edits={"yaml_content": "custom: true"},
        )
        assert result["status"] == "approved"
        # The new edited interpretation should exist
        edited = [i for i in result["interpretations"] if i["label"] == "edited"]
        assert len(edited) == 1
        assert edited[0]["yaml_content"] == "custom: true"

    # ── commit_ingestion ──

    def test_commit_success(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"data", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        interps = svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        svc.review_interpretation(
            doc_id, decision="approve", reviewer_id="da",
            selected_interpretation_id=interps[0]["id"],
        )
        result = svc.commit_ingestion(doc_id, actor_id="da")
        assert result["status"] == "committed"
        assert "committed_hash" in result
        assert len(result["committed_hash"]) == 64  # SHA-256 hex

    def test_commit_rejects_non_approved(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        with pytest.raises(ValueError, match="must be 'approved'"):
            svc.commit_ingestion(doc_id, actor_id="u")

    # ── list_records ──

    def test_list_records_filtering(self):
        svc = self._make_service()
        svc.accept_document(
            file_bytes=b"a", filename="a.md", content_type="markdown",
            actor_id="u", domain_id="dom1",
        )
        svc.accept_document(
            file_bytes=b"b", filename="b.md", content_type="markdown",
            actor_id="u", domain_id="dom2",
        )

        all_records = svc.list_records()
        assert len(all_records) == 2

        dom1_only = svc.list_records(domain_id="dom1")
        assert len(dom1_only) == 1
        assert dom1_only[0]["domain_id"] == "dom1"

    def test_list_records_pagination(self):
        svc = self._make_service()
        for i in range(5):
            svc.accept_document(
                file_bytes=f"doc{i}".encode(),
                filename=f"doc{i}.md",
                content_type="markdown",
                actor_id="u",
                domain_id="d",
            )
        page = svc.list_records(limit=2, offset=0)
        assert len(page) == 2

        page2 = svc.list_records(limit=2, offset=2)
        assert len(page2) == 2

    # ── accept_document field storage ──

    def test_accept_stores_module_id(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"x",
            filename="f.md",
            content_type="markdown",
            actor_id="u",
            domain_id="d",
            module_id="mod-42",
        )
        assert svc.get_record(doc_id)["module_id"] == "mod-42"

    def test_accept_stores_actor_filename_content_type(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"hello",
            filename="notes.csv",
            content_type="csv",
            actor_id="user-99",
            domain_id="d",
        )
        rec = svc.get_record(doc_id)
        assert rec["ingesting_actor_id"] == "user-99"
        assert rec["original_filename"] == "notes.csv"
        assert rec["content_type"] == "csv"

    def test_accept_content_hash_is_sha256(self):
        import hashlib
        payload = b"deterministic content"
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=payload,
            filename="f.md",
            content_type="markdown",
            actor_id="u",
            domain_id="d",
        )
        expected = hashlib.sha256(payload).hexdigest()
        assert svc.get_record(doc_id)["content_hash"] == expected

    # ── review_interpretation edge cases ──

    def test_review_invalid_decision_raises(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        with pytest.raises(ValueError, match="Invalid decision"):
            svc.review_interpretation(doc_id, decision="skip", reviewer_id="da")

    def test_review_approve_with_bad_interp_id_raises(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        with pytest.raises(ValueError, match="not found"):
            svc.review_interpretation(
                doc_id,
                decision="approve",
                reviewer_id="da",
                selected_interpretation_id="no-such-id",
            )

    def test_review_notes_stored_on_record(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        svc.review_interpretation(
            doc_id, decision="reject", reviewer_id="da", review_notes="Not suitable."
        )
        rec = svc.get_record(doc_id)
        assert rec["review_notes"] == "Not suitable."
        assert rec["reviewer_id"] == "da"
        assert rec["review_decision"] == "reject"

    def test_review_notes_truncated_at_512_chars(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"d", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        long_note = "A" * 600
        svc.review_interpretation(
            doc_id, decision="reject", reviewer_id="da", review_notes=long_note
        )
        assert len(svc.get_record(doc_id)["review_notes"]) == 512

    # ── commit_ingestion extended ──

    def test_commit_returns_record_id_and_document_id(self):
        svc = self._make_service()
        doc_id = svc.accept_document(
            file_bytes=b"data", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        interps = svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        svc.review_interpretation(
            doc_id, decision="approve", reviewer_id="da",
            selected_interpretation_id=interps[0]["id"],
        )
        result = svc.commit_ingestion(doc_id, actor_id="da")
        assert result["record_id"] == svc.get_record(doc_id)["record_id"]
        assert result["document_id"] == doc_id

    def test_commit_hash_is_deterministic(self):
        """Same yaml_content always produces same committed_hash."""
        import json as _json

        fixed_slm = lambda **_kw: _json.dumps({
            "interpretations": [{
                "label": "fixed",
                "yaml_content": "key: value",
                "confidence": 1.0,
                "ambiguity_notes": "",
            }]
        })

        def _run():
            svc = self._make_service(call_slm_fn=fixed_slm)
            doc_id = svc.accept_document(
                file_bytes=b"same", filename="t.md", content_type="markdown",
                actor_id="u", domain_id="d",
            )
            interps = svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
            svc.review_interpretation(
                doc_id, decision="approve", reviewer_id="da",
                selected_interpretation_id=interps[0]["id"],
            )
            return svc.commit_ingestion(doc_id, actor_id="da")["committed_hash"]

        assert _run() == _run()

    def test_commit_calls_persistence_append_when_wired(self):
        calls = []
        svc = self._make_service(persistence_append=lambda *a, **kw: calls.append(a))
        doc_id = svc.accept_document(
            file_bytes=b"data", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        interps = svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        svc.review_interpretation(
            doc_id, decision="approve", reviewer_id="da",
            selected_interpretation_id=interps[0]["id"],
        )
        svc.commit_ingestion(doc_id, actor_id="da")
        assert len(calls) == 1

    def test_commit_swallows_persistence_append_exception(self):
        def bad_append(*_a, **_kw):
            raise RuntimeError("DB down")

        svc = self._make_service(persistence_append=bad_append)
        doc_id = svc.accept_document(
            file_bytes=b"data", filename="t.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        interps = svc.extract_interpretations(doc_id, domain_physics={"id": "d"})
        svc.review_interpretation(
            doc_id, decision="approve", reviewer_id="da",
            selected_interpretation_id=interps[0]["id"],
        )
        # Should not raise
        result = svc.commit_ingestion(doc_id, actor_id="da")
        assert result["status"] == "committed"

    # ── list_records status filter ──

    def test_list_records_status_filter(self):
        svc = self._make_service()
        # One doc stays pending, one gets extracted
        svc.accept_document(
            file_bytes=b"a", filename="a.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        doc_b = svc.accept_document(
            file_bytes=b"b", filename="b.md", content_type="markdown",
            actor_id="u", domain_id="d",
        )
        svc.extract_interpretations(doc_b, domain_physics={"id": "d"})

        pending = svc.list_records(status="pending_extraction")
        assert len(pending) == 1
        assert pending[0]["document_id"] != doc_b

        extracted = svc.list_records(status="extraction_complete")
        assert len(extracted) == 1
        assert extracted[0]["document_id"] == doc_b

    def test_list_records_combined_domain_and_status_filter(self):
        svc = self._make_service()
        doc_a = svc.accept_document(
            file_bytes=b"a", filename="a.md", content_type="markdown",
            actor_id="u", domain_id="dom-x",
        )
        svc.extract_interpretations(doc_a, domain_physics={"id": "dom-x"})
        svc.accept_document(
            file_bytes=b"b", filename="b.md", content_type="markdown",
            actor_id="u", domain_id="dom-y",
        )

        results = svc.list_records(domain_id="dom-x", status="extraction_complete")
        assert len(results) == 1
        assert results[0]["domain_id"] == "dom-x"

        empty = svc.list_records(domain_id="dom-x", status="pending_extraction")
        assert empty == []

    # ── get_record ──

    def test_get_record_returns_none_for_unknown_id(self):
        svc = self._make_service()
        assert svc.get_record("no-such-id") is None

    # ── document isolation ──

    def test_two_documents_do_not_share_state(self):
        svc = self._make_service()
        id_a = svc.accept_document(
            file_bytes=b"doc-a", filename="a.md", content_type="markdown",
            actor_id="u", domain_id="dom-a",
        )
        id_b = svc.accept_document(
            file_bytes=b"doc-b", filename="b.md", content_type="markdown",
            actor_id="u", domain_id="dom-b",
        )
        interps_a = svc.extract_interpretations(id_a, domain_physics={"id": "dom-a"})
        svc.review_interpretation(
            id_a, decision="approve", reviewer_id="da",
            selected_interpretation_id=interps_a[0]["id"],
        )

        # doc-b should still be pending
        rec_b = svc.get_record(id_b)
        assert rec_b["status"] == "pending_extraction"
        assert rec_b["interpretations"] == []
        assert rec_b["review_decision"] is None

        # doc-a should be approved
        rec_a = svc.get_record(id_a)
        assert rec_a["status"] == "approved"


# ── Content type detection tests ─────────────────────────────

class TestContentTypeDetection:
    """Tests for _detect_content_type helper used by API endpoints."""

    def test_known_extensions(self):
        from lumina.api.server import _detect_content_type
        assert _detect_content_type("doc.pdf") == "pdf"
        assert _detect_content_type("doc.docx") == "docx"
        assert _detect_content_type("doc.doc") == "docx"
        assert _detect_content_type("doc.md") == "markdown"
        assert _detect_content_type("doc.markdown") == "markdown"
        assert _detect_content_type("doc.txt") == "markdown"
        assert _detect_content_type("doc.csv") == "csv"
        assert _detect_content_type("doc.json") == "json"
        assert _detect_content_type("doc.yaml") == "yaml"
        assert _detect_content_type("doc.yml") == "yaml"

    def test_unknown_extension(self):
        from lumina.api.server import _detect_content_type
        assert _detect_content_type("doc.exe") is None
        assert _detect_content_type("noext") is None
