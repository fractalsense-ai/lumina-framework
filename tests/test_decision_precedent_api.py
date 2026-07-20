"""Integration tests for the authenticated Slice 29 decision precedent API."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from lumina.auth import auth
from lumina.persistence.adapter import NullPersistenceAdapter
from lumina.retrieval.embedder import EMBEDDING_DIM
from lumina.retrieval.institutional import InstitutionalMemoryIndexer
from lumina.retrieval.vector_store import VectorStore

_REPO_ROOT = Path(__file__).resolve().parents[1]


class _RecordingPersistence(NullPersistenceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []

    def append_log_record(self, session_id, record, ledger_path=None) -> None:
        self.records.append(dict(record))
        super().append_log_record(session_id, record, ledger_path)


class _FakeEmbedder:
    def embed_chunks(self, chunks):
        return np.asarray([self.embed_query(chunk.text) for chunk in chunks], dtype=np.float32)

    def embed_query(self, query):
        vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vector[0 if "brake" in query.lower() else 1] = 1.0
        return vector


def _load_api_module():
    module_path = _REPO_ROOT / "src" / "lumina" / "api" / "server.py"
    spec = importlib.util.spec_from_file_location("lumina.api.server", str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load lumina-api-server module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lumina.api.server"] = module
    spec.loader.exec_module(module)
    return module


def _summary(record_id: str, *, site_id: str = "site-1") -> dict:
    return {
        "record_type": "ThreadSummaryRecord", "record_id": record_id,
        "organization_id": "org-a", "site_id": site_id, "actor_id": "actor-a",
        "thread_id": f"thread-{record_id}", "summary": "Brake inspection work order.",
        "created_utc": "2026-07-20T12:00:00Z",
    }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("LUMINA_RUNTIME_CONFIG_PATH", "model-packs/education/cfg/runtime-config.yaml")
    monkeypatch.delenv("LUMINA_DOMAIN_REGISTRY_PATH", raising=False)
    module = _load_api_module()
    persistence = _RecordingPersistence()
    module.PERSISTENCE = persistence
    monkeypatch.setattr(auth, "JWT_SECRET", "test-secret")
    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "memory"), _FakeEmbedder())
    indexer.ingest([_summary("same-site"), _summary("other-site", site_id="site-2")])
    import lumina.api.routes.decision_precedent as route_module
    monkeypatch.setattr(route_module, "_get_institutional_indexer", lambda: indexer)
    route_module._pending_confirmations.clear()
    route_module._consumed_confirmation_ids.clear()
    return TestClient(module.app), persistence


def _token(
    *, actor_id: str = "actor-a", organization_id: str | None = "org-a", site_id: str | None = "site-1"
) -> str:
    return auth.create_scoped_jwt(
        user_id=actor_id, role="user", organization_id=organization_id, site_id=site_id
    )


@pytest.mark.integration
def test_preflight_uses_same_site_evidence_without_retaining_message(client) -> None:
    test_client, persistence = client
    response = test_client.post("/api/decision-precedent/preflight", headers={"Authorization": f"Bearer {_token()}"}, json={"message": "brake update", "risk_class": "routine", "session_id": "session-1"})

    assert response.status_code == 200
    assert response.json()["tier"] == "suggest_only"
    trace = persistence.records[0]
    evidence = trace["evidence_summary"]["decision_confidence_score"]
    assert evidence["precedent_matches"][0]["summary_record_id"] == "same-site"
    assert "message" not in evidence
    assert "brake update" not in str(evidence)


@pytest.mark.integration
def test_high_risk_preflight_creates_pending_standard_escalation(client) -> None:
    test_client, persistence = client
    response = test_client.post("/api/decision-precedent/preflight", headers={"Authorization": f"Bearer {_token()}"}, json={"message": "brake update", "risk_class": "financial"})

    assert response.status_code == 200
    assert response.json()["tier"] == "mandatory_escalation"
    assert response.json()["escalation_record_id"]
    escalation = persistence.records[1]
    assert escalation["record_type"] == "EscalationRecord"
    assert escalation["status"] == "pending"
    assert "message" not in escalation["evidence_summary"]


@pytest.mark.integration
def test_confirmation_is_scoped_and_replay_protected(client) -> None:
    test_client, persistence = client
    preflight = test_client.post("/api/decision-precedent/preflight", headers={"Authorization": f"Bearer {_token()}"}, json={"message": "brake update", "risk_class": "operational"})
    assert preflight.status_code == 200
    confidence_record_id = preflight.json()["confidence_record_id"]
    assert preflight.json()["confirmation_required"] is True

    confirmed = test_client.post(f"/api/decision-precedent/{confidence_record_id}/confirm", headers={"Authorization": f"Bearer {_token()}"})
    assert confirmed.status_code == 200
    assert confirmed.json()["tier"] == "require_confirmation"
    assert persistence.records[-1]["decision"] == "decision_precedent_confirmed"

    replay = test_client.post(f"/api/decision-precedent/{confidence_record_id}/confirm", headers={"Authorization": f"Bearer {_token()}"})
    assert replay.status_code == 409


@pytest.mark.integration
def test_preflight_requires_active_operating_context(client) -> None:
    test_client, persistence = client
    response = test_client.post("/api/decision-precedent/preflight", headers={"Authorization": f"Bearer {_token(organization_id=None, site_id=None)}"}, json={"message": "brake update", "risk_class": "routine"})

    assert response.status_code == 403
    assert persistence.records == []