from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lumina.auth import auth
from lumina.persistence.adapter import NullPersistenceAdapter

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


@pytest.fixture
def api_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LUMINA_RUNTIME_CONFIG_PATH", "model-packs/education/cfg/runtime-config.yaml")
    monkeypatch.delenv("LUMINA_DOMAIN_REGISTRY_PATH", raising=False)

    mod = _load_api_module()
    mod.PERSISTENCE = NullPersistenceAdapter()
    mod.BOOTSTRAP_MODE = True
    monkeypatch.setattr(auth, "JWT_SECRET", "test-secret")
    return mod


@pytest.fixture
def client(api_module):
    return TestClient(api_module.app)


@pytest.mark.integration
def test_register_first_user_bootstrap_promotes_root(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "test-pass-123", "role": "user"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "root"
    assert body["access_token"]


@pytest.mark.integration
def test_login_and_me_flow(client: TestClient) -> None:
    reg = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "test-pass-123", "role": "user"},
    )
    assert reg.status_code == 200

    # First registered user is auto-promoted to root (system track).
    login = client.post(
        "/api/admin/auth/login",
        json={"username": "bob", "password": "test-pass-123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["user_id"]
    assert me_body["role"] == "root"


@pytest.mark.integration
def test_users_endpoint_role_gating(client: TestClient) -> None:
    root_reg = client.post(
        "/api/auth/register",
        json={"username": "rootuser", "password": "test-pass-123", "role": "user"},
    )
    assert root_reg.status_code == 200
    root_token = root_reg.json()["access_token"]

    user_reg = client.post(
        "/api/auth/register",
        json={"username": "regular", "password": "test-pass-123", "role": "user"},
    )
    assert user_reg.status_code == 200

    users_as_root = client.get("/api/auth/users", headers={"Authorization": f"Bearer {root_token}"})
    assert users_as_root.status_code == 200
    assert len(users_as_root.json()) >= 2

    user_login = client.post(
        "/api/auth/login",
        json={"username": "regular", "password": "test-pass-123"},
    )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    users_as_regular = client.get("/api/auth/users", headers={"Authorization": f"Bearer {user_token}"})
    assert users_as_regular.status_code == 403


@pytest.mark.integration
def test_user_can_switch_only_to_an_assigned_operating_context(client: TestClient) -> None:
    root = client.post(
        "/api/auth/register",
        json={"username": "context-root", "password": "test-pass-123", "role": "user"},
    ).json()
    employee = client.post(
        "/api/auth/register",
        json={"username": "context-employee", "password": "test-pass-123", "role": "user"},
    ).json()

    assignment = client.patch(
        f"/api/auth/users/{employee['user_id']}",
        headers={"Authorization": f"Bearer {root['access_token']}"},
        json={
            "operating_memberships": [
                {
                    "organization_id": "org-1",
                    "site_ids": ["site-1", "site-2"],
                    "site_roles": {"site-1": "cashier", "site-2": "manager"},
                }
            ]
        },
    )
    assert assignment.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={"username": "context-employee", "password": "test-pass-123"},
    )
    assert login.status_code == 200
    assert login.json()["organization_id"] == "org-1"
    assert login.json()["site_id"] == "site-1"

    switched = client.post(
        "/api/auth/operating-context",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"organization_id": "org-1", "site_id": "site-2", "device_id": "device-9"},
    )
    assert switched.status_code == 200
    assert switched.json()["site_id"] == "site-2"
    assert switched.json()["device_id"] == "device-9"

    forbidden = client.post(
        "/api/auth/operating-context",
        headers={"Authorization": f"Bearer {switched.json()['access_token']}"},
        json={"organization_id": "org-1", "site_id": "site-3"},
    )
    assert forbidden.status_code == 403
