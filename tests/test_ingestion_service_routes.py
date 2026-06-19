"""Unit tests for ingestion service routes.

Covers error paths, authorization, and happy paths in:
  - lumina.services.ingestion.routes  (_detect_content_type, get_ingestion,
                                       ingest_extract, ingest_review,
                                       ingest_commit, list_ingestions)
  - lumina.services.ingestion.staging_routes  (list_pending, get_staged_file,
                                               approve_staged_file,
                                               reject_staged_file,
                                               create_staged_file)

No live SLM, persistence, or network.  Dependencies are patched or replaced
with deterministic fakes.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lumina.system_log.commit_guard import notify_log_commit


# ─── helpers ─────────────────────────────────────────────────────────────────


def _run(coro) -> Any:
    return asyncio.run(coro)


def _user(role: str = "root", governed: list | None = None) -> dict:
    u: dict[str, Any] = {"sub": f"{role}-1", "role": role}
    if governed is not None:
        u["governed_modules"] = governed
    return u


def _fake_creds() -> Any:
    return SimpleNamespace(credentials="fake-tok")


def _patch_ingest_auth(user: dict):
    """Patch get_current_user + require_auth in the ingestion routes module."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch(
                "lumina.services.ingestion.routes.get_current_user",
                new=AsyncMock(return_value=user),
            ),
            patch(
                "lumina.services.ingestion.routes.require_auth",
                return_value=user,
            ),
        ):
            yield

    return _ctx()


# ═══════════════════════════════════════════════════════════════════════════
# _detect_content_type  (pure function)
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.routes import _detect_content_type


class TestDetectContentType:

    @pytest.mark.unit
    def test_pdf(self) -> None:
        assert _detect_content_type("report.pdf") == "pdf"

    @pytest.mark.unit
    def test_docx(self) -> None:
        assert _detect_content_type("paper.docx") == "docx"

    @pytest.mark.unit
    def test_doc_maps_to_docx(self) -> None:
        assert _detect_content_type("legacy.doc") == "docx"

    @pytest.mark.unit
    def test_md(self) -> None:
        assert _detect_content_type("notes.md") == "markdown"

    @pytest.mark.unit
    def test_txt(self) -> None:
        assert _detect_content_type("readme.txt") == "markdown"

    @pytest.mark.unit
    def test_csv(self) -> None:
        assert _detect_content_type("data.csv") == "csv"

    @pytest.mark.unit
    def test_json(self) -> None:
        assert _detect_content_type("config.json") == "json"

    @pytest.mark.unit
    def test_yaml(self) -> None:
        assert _detect_content_type("config.yaml") == "yaml"

    @pytest.mark.unit
    def test_yml(self) -> None:
        assert _detect_content_type("config.yml") == "yaml"

    @pytest.mark.unit
    def test_unsupported_returns_none(self) -> None:
        assert _detect_content_type("image.png") is None

    @pytest.mark.unit
    def test_no_extension_returns_none(self) -> None:
        assert _detect_content_type("Makefile") is None


# ═══════════════════════════════════════════════════════════════════════════
# get_ingestion
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.routes import get_ingestion


class TestGetIngestion:

    def _fake_svc(self, record: dict | None) -> MagicMock:
        svc = MagicMock()
        svc.get_record.return_value = record
        return svc

    @pytest.mark.unit
    def test_returns_record_when_found(self) -> None:
        record = {"ingestion_id": "abc", "status": "pending_extraction"}
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=self._fake_svc(record)),
        ):
            result = _run(get_ingestion("abc", credentials=_fake_creds()))
        assert result["ingestion_id"] == "abc"

    @pytest.mark.unit
    def test_raises_404_when_not_found(self) -> None:
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=self._fake_svc(None)),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_ingestion("nonexistent", credentials=_fake_creds()))
        assert exc.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# ingest_extract
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.routes import ingest_extract


class TestIngestExtract:

    @pytest.mark.unit
    def test_raises_404_when_record_not_found(self) -> None:
        svc = MagicMock()
        svc.get_record.return_value = None
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_extract("missing-id", credentials=_fake_creds()))
        assert exc.value.status_code == 404

    @pytest.mark.unit
    def test_returns_interpretations_on_success(self) -> None:
        svc = MagicMock()
        svc.get_record.return_value = {"ingestion_id": "doc-1", "domain_id": "education"}
        svc.extract_interpretations.return_value = [{"id": "i1"}, {"id": "i2"}]

        fake_registry = MagicMock()
        fake_registry.resolve_domain_id.return_value = "education"
        fake_registry.get_runtime_context.return_value = {"domain_physics_path": "/fake/path"}

        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
            patch("lumina.services.ingestion.routes._cfg") as mock_cfg,
            patch(
                "lumina.services.ingestion.routes.run_in_threadpool",
                new=AsyncMock(side_effect=[{"ingestion_config": {}}, [{"id": "i1"}, {"id": "i2"}]]),
            ),
        ):
            mock_cfg.DOMAIN_REGISTRY = fake_registry
            result = _run(ingest_extract("doc-1", credentials=_fake_creds()))

        assert result["interpretation_count"] == 2
        assert result["status"] == "extraction_complete"


# ═══════════════════════════════════════════════════════════════════════════
# ingest_review
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.routes import ingest_review


class TestIngestReview:

    def _fake_svc(self, record: dict | None = None) -> MagicMock:
        svc = MagicMock()
        svc.get_record.return_value = record or {"ingestion_id": "doc-1", "domain_id": "education"}
        svc.review_interpretation.return_value = {"status": "approved"}
        return svc

    @pytest.mark.unit
    def test_non_admin_root_raises_403(self) -> None:
        with _patch_ingest_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_review("doc-1", req={"decision": "approve"}, credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_raises_404_when_record_not_found(self) -> None:
        svc = MagicMock()
        svc.get_record.return_value = None
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_review("missing", req={"decision": "approve"}, credentials=_fake_creds()))
        assert exc.value.status_code == 404

    @pytest.mark.unit
    def test_admin_not_governing_domain_raises_403(self) -> None:
        with (
            _patch_ingest_auth(_user("admin")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=self._fake_svc()),
            patch("lumina.services.ingestion.routes.can_govern_domain", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_review("doc-1", req={"decision": "approve"}, credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_invalid_decision_raises_400(self) -> None:
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=self._fake_svc()),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_review("doc-1", req={"decision": "destroy"}, credentials=_fake_creds()))
        assert exc.value.status_code == 400

    @pytest.mark.unit
    def test_root_approve_returns_updated_record(self) -> None:
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=self._fake_svc()),
        ):
            result = _run(ingest_review("doc-1", req={"decision": "approve"}, credentials=_fake_creds()))
        assert result["status"] == "approved"

    @pytest.mark.unit
    def test_service_value_error_raises_400(self) -> None:
        svc = self._fake_svc()
        svc.review_interpretation.side_effect = ValueError("state conflict")
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_review("doc-1", req={"decision": "approve"}, credentials=_fake_creds()))
        assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# ingest_commit
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.routes import ingest_commit


class TestIngestCommit:

    def _fake_svc(self, record: dict | None = None, commit_result: dict | None = None) -> MagicMock:
        svc = MagicMock()
        svc.get_record.return_value = record or {"ingestion_id": "doc-1", "domain_id": "education"}

        def _commit(ingestion_id, actor_id):
            notify_log_commit()  # satisfy @requires_log_commit guard
            return commit_result or {"status": "committed", "ingestion_id": ingestion_id}

        svc.commit_ingestion.side_effect = _commit
        return svc

    @pytest.mark.unit
    def test_non_admin_root_raises_403(self) -> None:
        with _patch_ingest_auth(_user("user")):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_commit("doc-1", credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_raises_404_when_record_not_found(self) -> None:
        svc = MagicMock()
        svc.get_record.return_value = None
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_commit("missing", credentials=_fake_creds()))
        assert exc.value.status_code == 404

    @pytest.mark.unit
    def test_admin_not_governing_raises_403(self) -> None:
        svc = MagicMock()
        svc.get_record.return_value = {"ingestion_id": "doc-1", "domain_id": "education"}
        with (
            _patch_ingest_auth(_user("admin")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
            patch("lumina.services.ingestion.routes.can_govern_domain", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(ingest_commit("doc-1", credentials=_fake_creds()))
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_root_commit_returns_result(self) -> None:
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=self._fake_svc()),
        ):
            result = _run(ingest_commit("doc-1", credentials=_fake_creds()))
        assert result["status"] == "committed"


# ═══════════════════════════════════════════════════════════════════════════
# list_ingestions
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.routes import list_ingestions


class TestListIngestions:

    @pytest.mark.unit
    def test_root_returns_all_records(self) -> None:
        records = [
            {"ingestion_id": "a", "domain_id": "education"},
            {"ingestion_id": "b", "domain_id": "agriculture"},
        ]
        svc = MagicMock()
        svc.list_records.return_value = records
        with (
            _patch_ingest_auth(_user("root")),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
        ):
            result = _run(list_ingestions(credentials=_fake_creds()))
        assert len(result) == 2

    @pytest.mark.unit
    def test_admin_filtered_to_governed_domains(self) -> None:
        records = [
            {"ingestion_id": "a", "domain_id": "education"},
            {"ingestion_id": "b", "domain_id": "agriculture"},
        ]
        svc = MagicMock()
        svc.list_records.return_value = records
        with (
            _patch_ingest_auth(_user("admin", governed=["education"])),
            patch("lumina.services.ingestion.routes._get_ingest_service", return_value=svc),
        ):
            result = _run(list_ingestions(credentials=_fake_creds()))
        assert len(result) == 1
        assert result[0]["domain_id"] == "education"


# ═══════════════════════════════════════════════════════════════════════════
# staging_routes
# ═══════════════════════════════════════════════════════════════════════════

from lumina.services.ingestion.staging_routes import (
    ApproveRequest,
    RejectRequest,
    StageFileRequest,
    approve_staged_file,
    create_staged_file,
    get_staged_file,
    list_pending,
    reject_staged_file,
)


def _patch_staging_auth(user: dict):
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("lumina.services.ingestion.staging_routes.require_auth", return_value=user):
            yield

    return _ctx()


def _fake_envelope(staged_id: str = "stg-1") -> MagicMock:
    env = MagicMock()
    env.staged_id = staged_id
    env.template_id = "tmpl-1"
    env.staged_at = "2026-06-19T00:00:00"
    env.log_record_id = "lr-1"
    env.to_dict.return_value = {
        "staged_id": staged_id,
        "template_id": "tmpl-1",
        "approval_status": "pending",
    }
    return env


class TestListPending:

    @pytest.mark.unit
    def test_root_gets_all_staged_files(self) -> None:
        svc = MagicMock()
        svc.list_staged.return_value = [_fake_envelope("s1"), _fake_envelope("s2")]
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            result = _run(list_pending(user=_user("root")))
        # root: actor_filter=None
        svc.list_staged.assert_called_once_with(actor_id=None)
        assert result["count"] == 2

    @pytest.mark.unit
    def test_admin_gets_only_own_staged_files(self) -> None:
        svc = MagicMock()
        svc.list_staged.return_value = [_fake_envelope("s3")]
        admin = _user("admin")
        with (
            _patch_staging_auth(admin),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            result = _run(list_pending(user=admin))
        # non-root: actor_filter = sub
        svc.list_staged.assert_called_once_with(actor_id="admin-1")
        assert result["count"] == 1


class TestGetStagedFile:

    @pytest.mark.unit
    def test_returns_envelope_when_found(self) -> None:
        env = _fake_envelope("stg-1")
        svc = MagicMock()
        svc.get_staged.return_value = env
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            result = _run(get_staged_file("stg-1", user=_user("root")))
        assert result["staged_id"] == "stg-1"

    @pytest.mark.unit
    def test_raises_404_when_not_found(self) -> None:
        svc = MagicMock()
        svc.get_staged.return_value = None
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_staged_file("nonexistent", user=_user("root")))
        assert exc.value.status_code == 404


class TestApproveAndRejectStagedFile:

    @pytest.mark.unit
    def test_approve_value_error_raises_422(self) -> None:
        svc = MagicMock()
        svc.approve_staged.side_effect = ValueError("already approved")
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(
                    approve_staged_file(
                        "stg-1",
                        body=ApproveRequest(),
                        user=_user("root"),
                    )
                )
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_reject_value_error_raises_422(self) -> None:
        svc = MagicMock()
        svc.reject_staged.side_effect = ValueError("already rejected")
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(
                    reject_staged_file(
                        "stg-1",
                        body=RejectRequest(reason="invalid"),
                        user=_user("root"),
                    )
                )
        assert exc.value.status_code == 422


class TestCreateStagedFile:

    @pytest.mark.unit
    def test_value_error_raises_422(self) -> None:
        svc = MagicMock()
        svc.stage_file.side_effect = ValueError("unknown template")
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(
                    create_staged_file(
                        body=StageFileRequest(template_id="bad-tmpl", payload={}),
                        user=_user("root"),
                    )
                )
        assert exc.value.status_code == 422

    @pytest.mark.unit
    def test_success_returns_staged_id(self) -> None:
        env = _fake_envelope("stg-new")

        def _fake_stage_file(**kwargs):
            notify_log_commit()  # satisfy @requires_log_commit guard
            return env

        svc = MagicMock()
        svc.stage_file.side_effect = _fake_stage_file
        with (
            _patch_staging_auth(_user("root")),
            patch("lumina.services.ingestion.staging_routes._get_service", return_value=svc),
        ):
            result = _run(
                create_staged_file(
                    body=StageFileRequest(template_id="tmpl-1", payload={"key": "val"}),
                    user=_user("root"),
                )
            )
        assert result["staged_id"] == "stg-new"
