"""SQLite persistence adapter — coverage top-up.

Tests for uncovered branches in SQLitePersistenceAdapter:
- User CRUD: create, get, get_by_username, list, activate, deactivate, update_role
- Governed modules: update_user_governed_modules add/remove
- Domain roles: update_user_domain_roles
- Invite token: set, get (found + expired), clear
- Consent: set, get, not-found
- Module state: save, load, list, delete
- Ledger path helpers: get_log_ledger_path, get_system_ledger_path,
  get_domain_ledger_path, get_module_ledger_path
- load_domain_physics
- close() / aclose()
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

from lumina.persistence.sqlite import SQLitePersistenceAdapter


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "topup.db"
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    adapter = SQLitePersistenceAdapter(repo_root=tmp_path, database_url=db_url)
    yield adapter
    adapter.close()


def _new_user(db: SQLitePersistenceAdapter, uid: str = "u-1", username: str = "alice") -> dict:
    return db.create_user(uid, username, "hash", "user", ["edu/algebra"])


# ═══════════════════════════════════════════════════════════════════════════
# Ledger path helpers (pure string construction — no DB needed)
# ═══════════════════════════════════════════════════════════════════════════


class TestLedgerPaths:

    @pytest.mark.unit
    def test_get_system_ledger_path(self, db: SQLitePersistenceAdapter) -> None:
        path = db.get_system_ledger_path("admin")
        assert "admin" in path

    @pytest.mark.unit
    def test_get_domain_ledger_path(self, db: SQLitePersistenceAdapter) -> None:
        path = db.get_domain_ledger_path("edu")
        assert "edu" in path

    @pytest.mark.unit
    def test_get_module_ledger_path(self, db: SQLitePersistenceAdapter) -> None:
        path = db.get_module_ledger_path("edu", "algebra")
        assert "edu" in path
        assert "algebra" in path

    @pytest.mark.unit
    def test_get_log_ledger_path_no_domain(self, db: SQLitePersistenceAdapter) -> None:
        path = db.get_log_ledger_path("sess-1")
        assert "sess-1" in path

    @pytest.mark.unit
    def test_get_log_ledger_path_with_domain(self, db: SQLitePersistenceAdapter) -> None:
        path = db.get_log_ledger_path("sess-1", domain_id="edu")
        assert path  # just verify it returns something


# ═══════════════════════════════════════════════════════════════════════════
# load_domain_physics
# ═══════════════════════════════════════════════════════════════════════════


class TestLoadDomainPhysics:

    @pytest.mark.unit
    def test_load_domain_physics_returns_dict(self, db: SQLitePersistenceAdapter, tmp_path: Path) -> None:
        phys_path = tmp_path / "physics.json"
        phys_path.write_text(json.dumps({"id": "edu", "version": "1"}), encoding="utf-8")
        result = db.load_domain_physics(str(phys_path))
        assert result["id"] == "edu"


# ═══════════════════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════════════════


class TestUserCRUD:

    @pytest.mark.unit
    def test_create_user_returns_user_dict(self, db: SQLitePersistenceAdapter) -> None:
        result = _new_user(db)
        assert result["user_id"] == "u-1"
        assert result["username"] == "alice"
        assert result["role"] == "user"

    @pytest.mark.unit
    def test_get_user_returns_user(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        user = db.get_user("u-1")
        assert user is not None
        assert user["username"] == "alice"

    @pytest.mark.unit
    def test_get_user_not_found_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        assert db.get_user("nonexistent") is None

    @pytest.mark.unit
    def test_get_user_by_username_returns_user(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        user = db.get_user_by_username("alice")
        assert user is not None
        assert user["user_id"] == "u-1"

    @pytest.mark.unit
    def test_get_user_by_username_not_found(self, db: SQLitePersistenceAdapter) -> None:
        assert db.get_user_by_username("nobody") is None

    @pytest.mark.unit
    def test_list_users_returns_all(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db, "u-1", "alice")
        _new_user(db, "u-2", "bob")
        users = db.list_users()
        usernames = [u["username"] for u in users]
        assert "alice" in usernames
        assert "bob" in usernames

    @pytest.mark.unit
    def test_activate_user_success(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        result = db.activate_user("u-1")
        assert result is True

    @pytest.mark.unit
    def test_deactivate_user_success(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        result = db.deactivate_user("u-1")
        assert result is True

    @pytest.mark.unit
    def test_update_user_role_success(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        updated = db.update_user_role("u-1", "admin", ["edu/algebra"])
        assert updated is not None
        assert updated["role"] == "admin"

    @pytest.mark.unit
    def test_update_user_domain_roles(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        result = db.update_user_domain_roles("u-1", {"edu": "student"})
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════
# Governed modules
# ═══════════════════════════════════════════════════════════════════════════


class TestGoverneModules:

    @pytest.mark.unit
    def test_update_governed_modules_add(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        result = db.update_user_governed_modules("u-1", add=["agri/crop"])
        assert result is not None
        assert "agri/crop" in result.get("governed_modules", [])

    @pytest.mark.unit
    def test_update_governed_modules_remove(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)  # has edu/algebra
        result = db.update_user_governed_modules("u-1", remove=["edu/algebra"])
        assert result is not None
        assert "edu/algebra" not in result.get("governed_modules", [])

    @pytest.mark.unit
    def test_update_governed_modules_not_found_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        result = db.update_user_governed_modules("missing-user", add=["edu/algebra"])
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Invite token
# ═══════════════════════════════════════════════════════════════════════════


class TestInviteToken:

    @pytest.mark.unit
    def test_set_and_get_invite_token(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        expires = time.time() + 3600
        ok = db.set_user_invite_token("u-1", "tok-abc", expires)
        assert ok is True
        user = db.get_user_by_invite_token("tok-abc")
        assert user is not None
        assert user["user_id"] == "u-1"

    @pytest.mark.unit
    def test_expired_token_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        past = time.time() - 1.0  # already expired
        db.set_user_invite_token("u-1", "tok-expired", past)
        user = db.get_user_by_invite_token("tok-expired")
        assert user is None

    @pytest.mark.unit
    def test_clear_invite_token(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        db.set_user_invite_token("u-1", "tok-clear", time.time() + 3600)
        ok = db.clear_user_invite_token("u-1")
        assert ok is True
        user = db.get_user_by_invite_token("tok-clear")
        assert user is None

    @pytest.mark.unit
    def test_get_nonexistent_token_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        assert db.get_user_by_invite_token("no-such-token") is None


# ═══════════════════════════════════════════════════════════════════════════
# User consent
# ═══════════════════════════════════════════════════════════════════════════


class TestUserConsent:

    @pytest.mark.unit
    def test_set_consent_success(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        now = time.time()
        ok = db.set_user_consent("u-1", True, now)
        assert ok is True

    @pytest.mark.unit
    def test_get_consent_after_set(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        now = time.time()
        db.set_user_consent("u-1", True, now)
        consent = db.get_user_consent("u-1")
        assert consent is not None
        assert consent["accepted"] is True

    @pytest.mark.unit
    def test_set_consent_unknown_user_returns_false(self, db: SQLitePersistenceAdapter) -> None:
        ok = db.set_user_consent("ghost", True, time.time())
        assert ok is False

    @pytest.mark.unit
    def test_get_consent_no_user_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        assert db.get_user_consent("ghost") is None

    @pytest.mark.unit
    def test_get_consent_without_setting_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        _new_user(db)
        assert db.get_user_consent("u-1") is None


# ═══════════════════════════════════════════════════════════════════════════
# Module state
# ═══════════════════════════════════════════════════════════════════════════


class TestModuleState:

    @pytest.mark.unit
    def test_save_and_load_module_state(self, db: SQLitePersistenceAdapter) -> None:
        state = {"current_task": "t1", "score": 5}
        db.save_module_state("u-1", "edu/algebra", state)
        loaded = db.load_module_state("u-1", "edu/algebra")
        assert loaded == state

    @pytest.mark.unit
    def test_load_missing_module_state_returns_none(self, db: SQLitePersistenceAdapter) -> None:
        assert db.load_module_state("u-1", "edu/algebra") is None

    @pytest.mark.unit
    def test_list_module_states_returns_keys(self, db: SQLitePersistenceAdapter) -> None:
        db.save_module_state("u-1", "edu/algebra", {"x": 1})
        db.save_module_state("u-1", "agri/crop", {"y": 2})
        keys = db.list_module_states("u-1")
        assert "edu/algebra" in keys
        assert "agri/crop" in keys

    @pytest.mark.unit
    def test_delete_module_state_success(self, db: SQLitePersistenceAdapter) -> None:
        db.save_module_state("u-1", "edu/algebra", {"x": 1})
        ok = db.delete_module_state("u-1", "edu/algebra")
        assert ok is True
        assert db.load_module_state("u-1", "edu/algebra") is None

    @pytest.mark.unit
    def test_delete_module_state_not_found_returns_false(self, db: SQLitePersistenceAdapter) -> None:
        ok = db.delete_module_state("u-1", "no/such/module")
        assert ok is False

    @pytest.mark.unit
    def test_save_module_state_upsert(self, db: SQLitePersistenceAdapter) -> None:
        db.save_module_state("u-1", "edu/algebra", {"score": 1})
        db.save_module_state("u-1", "edu/algebra", {"score": 99})
        loaded = db.load_module_state("u-1", "edu/algebra")
        assert loaded["score"] == 99


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle: close / aclose
# ═══════════════════════════════════════════════════════════════════════════


class TestLifecycle:

    @pytest.mark.unit
    def test_close_does_not_raise(self, tmp_path: Path) -> None:
        db_path = tmp_path / "close_test.db"
        db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        adapter = SQLitePersistenceAdapter(repo_root=tmp_path, database_url=db_url)
        adapter.close()  # should not raise

    @pytest.mark.unit
    def test_aclose_does_not_raise(self, tmp_path: Path) -> None:
        db_path = tmp_path / "aclose_test.db"
        db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        adapter = SQLitePersistenceAdapter(repo_root=tmp_path, database_url=db_url)
        asyncio.run(adapter.aclose())  # should not raise
