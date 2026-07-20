"""Integration tests for the authenticated thread-routing preflight API."""
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
from lumina.thread_routing.bindings import create_thread_session_binding

_REPO_ROOT = Path(__file__).resolve().parents[1]


class _RecordingPersistence(NullPersistenceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []

    def append_log_record(self, session_id, record, ledger_path=None) -> None:
        self.records.append(dict(record))
        super().append_log_record(session_id, record, ledger_path)


class _FakeEmbedder:
    @staticmethod
    def _embed(text):
        vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        if "brake" in text.lower():
            vector[0] = 1.0
        else:
            vector[1] = 1.0
        return vector

    def embed_chunks(self, chunks):
        return np.asarray([self._embed(chunk.text) for chunk in chunks], dtype=np.float32)

    def embed_query(self, query):
        return self._embed(query)


def _load_api_module():
    module_path = _REPO_ROOT / "src" / "lumina" / "api" / "server.py"
    module_name = "lumina.api.server"
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load lumina-api-server module")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _summary(record_id: str, *, thread_id: str, site_id: str) -> dict:
    return {
        "record_type": "ThreadSummaryRecord",
        "record_id": record_id,
        "organization_id": "org-a",
        "site_id": site_id,
        "actor_id": "actor-a",
        "thread_id": thread_id,
        "summary": "Open brake inspection work order.",
    }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("LUMINA_RUNTIME_CONFIG_PATH", "model-packs/education/cfg/runtime-config.yaml")
    monkeypatch.delenv("LUMINA_DOMAIN_REGISTRY_PATH", raising=False)
    mod = _load_api_module()
    persistence = _RecordingPersistence()
    mod.PERSISTENCE = persistence
    monkeypatch.setattr(auth, "JWT_SECRET", "test-secret")

    indexer = InstitutionalMemoryIndexer(VectorStore(tmp_path / "institutional"), _FakeEmbedder())
    indexer.ingest([
        _summary("summary-site-1", thread_id="thread-site-1", site_id="site-1"),
        _summary("summary-site-2", thread_id="thread-site-2", site_id="site-2"),
    ])
    create_thread_session_binding(
        persistence,
        thread_id="thread-site-1",
        session_id="session-thread-site-1",
        organization_id="org-a",
        site_id="site-1",
        actor_id="actor-a",
    )
    import lumina.api.routes.thread_routing as route_module
    monkeypatch.setattr(route_module, "get_institutional_indexer", lambda: indexer)
    route_module._pending_decisions.clear()
    route_module._consumed_decision_ids.clear()
    return TestClient(mod.app), persistence


def _token(*, organization_id: str | None = "org-a", site_id: str | None = "site-1") -> str:
    return auth.create_scoped_jwt(
        user_id="actor-a",
        role="user",
        organization_id=organization_id,
        site_id=site_id,
    )


@pytest.mark.integration
def test_preflight_attaches_only_to_same_site_and_persists_evidence(client) -> None:
    test_client, persistence = client
    response = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update", "session_id": "session-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "attach_existing"
    assert body["thread_id"] == "thread-site-1"
    assert [candidate["thread_id"] for candidate in body["candidates"]] == ["thread-site-1"]
    assert len(persistence.records) == 1
    assert persistence.records[0]["decision_id"] == body["decision_id"]
    assert "message" not in persistence.records[0]
    assert "transcript" not in persistence.records[0]


@pytest.mark.integration
def test_preflight_rejects_unscoped_token(client) -> None:
    test_client, persistence = client
    response = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token(organization_id=None, site_id=None)}"},
        json={"message": "brake inspection update"},
    )

    assert response.status_code == 403
    assert persistence.records == []


@pytest.mark.integration
def test_preflight_forks_without_a_matching_scoped_summary(client) -> None:
    test_client, _ = client
    response = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "inventory count", "active_thread_id": "thread-active"},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "fork_from"
    assert response.json()["source_thread_id"] == "thread-active"


@pytest.mark.integration
def test_confirmation_persists_accepted_routing_intent_without_transcript(client) -> None:
    test_client, persistence = client
    preflight = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update", "session_id": "session-1"},
    )
    assert preflight.status_code == 200

    confirmation = test_client.post(
        f"/api/thread-routing/{preflight.json()['decision_id']}/confirm",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"action": "accept"},
    )
    assert confirmation.status_code == 200
    assert confirmation.json()["decision_id"] == preflight.json()["decision_id"]
    assert confirmation.json()["thread_id"] == "thread-site-1"
    assert confirmation.json()["decision"] == "attach_existing"
    assert confirmation.json()["operator_override"] is False
    assert confirmation.json()["session_id"] == "session-thread-site-1"
    assert len(persistence.records) == 2
    evidence = persistence.records[1]["evidence_summary"]
    assert evidence["preflight_decision_id"] == preflight.json()["decision_id"]
    assert "message" not in evidence["routing_decision"]
    assert "transcript" not in evidence["routing_decision"]


@pytest.mark.integration
def test_confirmation_can_create_new_thread_once(client) -> None:
    test_client, _ = client
    preflight = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update"},
    )
    decision_id = preflight.json()["decision_id"]

    confirmation = test_client.post(
        f"/api/thread-routing/{decision_id}/confirm",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"action": "create_new"},
    )
    assert confirmation.status_code == 200
    assert confirmation.json()["decision"] == "create_new"
    assert confirmation.json()["operator_override"] is True
    assert confirmation.json()["thread_id"].startswith("thread-")

    replay = test_client.post(
        f"/api/thread-routing/{decision_id}/confirm",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"action": "accept"},
    )
    assert replay.status_code == 409


@pytest.mark.integration
def test_preflight_prunes_expired_pending_and_consumed_decisions(client, monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, _ = client
    import lumina.api.routes.thread_routing as route_module

    expired_at = 10.0
    route_module._pending_decisions["expired-pending"] = route_module._PendingDecision(
        decision=route_module.ThreadRoutingDecision(
            decision_id="expired-pending",
            organization_id="org-a",
            site_id="site-1",
            actor_id="actor-a",
            decision="create_new",
            thread_id="thread-expired",
            source_thread_id=None,
            policy_version=1,
            confidence=0.0,
            rationale_code="no_match",
            operator_confirmation_required=False,
            operator_override=False,
            candidates=(),
        ),
        session_id="session-expired",
        active_thread_id=None,
        expires_at=expired_at,
    )
    route_module._consumed_decision_ids["expired-consumed"] = expired_at
    monkeypatch.setattr(route_module.time, "monotonic", lambda: expired_at + 1)

    response = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update"},
    )

    assert response.status_code == 200
    assert "expired-pending" not in route_module._pending_decisions
    assert "expired-consumed" not in route_module._consumed_decision_ids


@pytest.mark.integration
def test_confirmation_reports_expired_decision_as_gone(client, monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, _ = client
    preflight = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update"},
    )
    decision_id = preflight.json()["decision_id"]
    import lumina.api.routes.thread_routing as route_module

    expires_at = route_module._pending_decisions[decision_id].expires_at
    monkeypatch.setattr(route_module.time, "monotonic", lambda: expires_at + 1)
    response = test_client.post(
        f"/api/thread-routing/{decision_id}/confirm",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"action": "accept"},
    )

    assert response.status_code == 410


@pytest.mark.integration
def test_confirmation_rejects_different_actor_or_active_context(client) -> None:
    test_client, _ = client
    preflight = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update"},
    )
    decision_id = preflight.json()["decision_id"]

    other_actor = auth.create_scoped_jwt(
        user_id="actor-b", role="user", organization_id="org-a", site_id="site-1"
    )
    forbidden_actor = test_client.post(
        f"/api/thread-routing/{decision_id}/confirm",
        headers={"Authorization": f"Bearer {other_actor}"},
        json={"action": "accept"},
    )
    assert forbidden_actor.status_code == 403

    wrong_context = _token(site_id="site-2")
    forbidden_context = test_client.post(
        f"/api/thread-routing/{decision_id}/confirm",
        headers={"Authorization": f"Bearer {wrong_context}"},
        json={"action": "accept"},
    )
    assert forbidden_context.status_code == 403


@pytest.mark.integration
def test_confirmed_thread_selects_bound_chat_session(client, monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, _ = client
    preflight = test_client.post(
        "/api/thread-routing/preflight",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "brake inspection update"},
    )
    confirmation = test_client.post(
        f"/api/thread-routing/{preflight.json()['decision_id']}/confirm",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"action": "create_new"},
    )
    assert confirmation.status_code == 200
    confirmed = confirmation.json()

    def fake_process_message(session_id, *_args, **_kwargs):
        from types import SimpleNamespace

        chat_module._session_containers[session_id] = SimpleNamespace(
            active_context=SimpleNamespace(turn_count=1)
        )
        return {
            "session_id": session_id,
            "response": "ok",
            "action": "continue",
            "prompt_type": "standard",
            "escalated": False,
            "domain_id": "_default",
        }

    import lumina.api.routes.chat as chat_module
    monkeypatch.setattr(chat_module, "process_message", fake_process_message)
    recap_calls: list[dict] = []

    def fake_record_thread_recap(**kwargs):
        recap_calls.append(kwargs)
        return None

    monkeypatch.setattr(chat_module, "record_thread_recap", fake_record_thread_recap)

    response = test_client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "continue", "thread_id": confirmed["thread_id"]},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == confirmed["session_id"]
    assert recap_calls[0]["thread_id"] == confirmed["thread_id"]
    assert recap_calls[0]["turn_count"] == 1

    mismatch = test_client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {_token()}"},
        json={
            "message": "continue",
            "thread_id": confirmed["thread_id"],
            "session_id": "other-session",
        },
    )
    assert mismatch.status_code == 409