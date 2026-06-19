"""Unit tests for admin_middleware and domain_middleware.

Covers every branch of the three-track auth helper functions:
  - admin_middleware: get_admin_user, get_user_user,
                      require_admin_auth, require_user_auth
  - domain_middleware: get_domain_user,
                       require_domain_auth, require_domain_scope

No TestClient, persistence, network, model, or secrets.
verify_scoped_jwt is patched for every call.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from lumina.auth.auth import AuthError, TokenExpiredError, TokenInvalidError
from lumina.api.admin_middleware import (
    get_admin_user,
    get_user_user,
    require_admin_auth,
    require_user_auth,
)
from lumina.api.domain_middleware import (
    get_domain_user,
    require_domain_auth,
    require_domain_scope,
)


# ─── helpers ───────────────────────────────────────────────────────────────

def _creds(token: str = "tok") -> SimpleNamespace:
    """Minimal stand-in for HTTPAuthorizationCredentials."""
    return SimpleNamespace(credentials=token)


def _run(coro):
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════
# admin_middleware.get_admin_user
# ═══════════════════════════════════════════════════════════════════════════


class TestGetAdminUser:

    @pytest.mark.unit
    def test_returns_none_when_no_credentials(self) -> None:
        """No credentials → returns None (unauthenticated, not an error)."""
        result = _run(get_admin_user(credentials=None))
        assert result is None

    @pytest.mark.unit
    def test_returns_user_dict_on_valid_token(self) -> None:
        """Valid admin token → returns the decoded user dict."""
        fake_user = {"sub": "admin-1", "token_scope": "admin"}
        with patch("lumina.api.admin_middleware.verify_scoped_jwt", return_value=fake_user):
            result = _run(get_admin_user(credentials=_creds("good")))
        assert result == fake_user

    @pytest.mark.unit
    def test_raises_401_on_expired_token(self) -> None:
        """TokenExpiredError → 401 with 'Token expired' detail."""
        with patch(
            "lumina.api.admin_middleware.verify_scoped_jwt",
            side_effect=TokenExpiredError("expired"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_admin_user(credentials=_creds()))
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    @pytest.mark.unit
    def test_raises_401_on_invalid_token(self) -> None:
        """TokenInvalidError → 401 with 'Invalid' detail."""
        with patch(
            "lumina.api.admin_middleware.verify_scoped_jwt",
            side_effect=TokenInvalidError("bad"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_admin_user(credentials=_creds()))
        assert exc.value.status_code == 401
        assert "invalid" in exc.value.detail.lower()

    @pytest.mark.unit
    def test_raises_401_on_auth_error(self) -> None:
        """Generic AuthError → 401 with 'Invalid' detail."""
        with patch(
            "lumina.api.admin_middleware.verify_scoped_jwt",
            side_effect=AuthError("scope mismatch"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_admin_user(credentials=_creds()))
        assert exc.value.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# admin_middleware.get_user_user
# ═══════════════════════════════════════════════════════════════════════════


class TestGetUserUser:

    @pytest.mark.unit
    def test_returns_none_when_no_credentials(self) -> None:
        result = _run(get_user_user(credentials=None))
        assert result is None

    @pytest.mark.unit
    def test_returns_user_dict_on_valid_token(self) -> None:
        fake_user = {"sub": "user-1", "token_scope": "user"}
        with patch("lumina.api.admin_middleware.verify_scoped_jwt", return_value=fake_user):
            result = _run(get_user_user(credentials=_creds("good")))
        assert result == fake_user

    @pytest.mark.unit
    def test_raises_401_on_expired_token(self) -> None:
        with patch(
            "lumina.api.admin_middleware.verify_scoped_jwt",
            side_effect=TokenExpiredError("expired"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_user_user(credentials=_creds()))
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    @pytest.mark.unit
    def test_raises_401_on_invalid_token(self) -> None:
        with patch(
            "lumina.api.admin_middleware.verify_scoped_jwt",
            side_effect=TokenInvalidError("bad"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_user_user(credentials=_creds()))
        assert exc.value.status_code == 401

    @pytest.mark.unit
    def test_raises_401_on_auth_error(self) -> None:
        with patch(
            "lumina.api.admin_middleware.verify_scoped_jwt",
            side_effect=AuthError("scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_user_user(credentials=_creds()))
        assert exc.value.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# admin_middleware.require_admin_auth
# ═══════════════════════════════════════════════════════════════════════════


class TestRequireAdminAuth:

    @pytest.mark.unit
    def test_raises_401_when_user_is_none(self) -> None:
        """No user dict → 401 (not authenticated)."""
        with pytest.raises(HTTPException) as exc:
            require_admin_auth(None)
        assert exc.value.status_code == 401

    @pytest.mark.unit
    def test_raises_403_when_wrong_scope(self) -> None:
        """User present but token_scope is not 'admin' → 403."""
        with pytest.raises(HTTPException) as exc:
            require_admin_auth({"sub": "u1", "token_scope": "user"})
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_raises_403_on_domain_scope(self) -> None:
        """Domain-track token rejected by admin check → 403."""
        with pytest.raises(HTTPException) as exc:
            require_admin_auth({"sub": "da-1", "token_scope": "domain"})
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_returns_user_on_admin_scope(self) -> None:
        """Admin-scoped user dict passes through unchanged."""
        user = {"sub": "admin-1", "token_scope": "admin"}
        assert require_admin_auth(user) is user


# ═══════════════════════════════════════════════════════════════════════════
# admin_middleware.require_user_auth
# ═══════════════════════════════════════════════════════════════════════════


class TestRequireUserAuth:

    @pytest.mark.unit
    def test_raises_401_when_user_is_none(self) -> None:
        with pytest.raises(HTTPException) as exc:
            require_user_auth(None)
        assert exc.value.status_code == 401

    @pytest.mark.unit
    def test_raises_403_when_wrong_scope(self) -> None:
        """Admin token rejected by user-tier check → 403."""
        with pytest.raises(HTTPException) as exc:
            require_user_auth({"sub": "a1", "token_scope": "admin"})
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_returns_user_on_user_scope(self) -> None:
        user = {"sub": "u1", "token_scope": "user"}
        assert require_user_auth(user) is user


# ═══════════════════════════════════════════════════════════════════════════
# domain_middleware.get_domain_user
# ═══════════════════════════════════════════════════════════════════════════


class TestGetDomainUser:

    @pytest.mark.unit
    def test_returns_none_when_no_credentials(self) -> None:
        result = _run(get_domain_user(credentials=None))
        assert result is None

    @pytest.mark.unit
    def test_returns_user_dict_on_valid_token(self) -> None:
        fake_user = {"sub": "da-1", "token_scope": "domain", "governed_modules": ["edu/algebra"]}
        with patch("lumina.api.domain_middleware.verify_scoped_jwt", return_value=fake_user):
            result = _run(get_domain_user(credentials=_creds("domain-tok")))
        assert result == fake_user

    @pytest.mark.unit
    def test_raises_401_on_expired_token(self) -> None:
        with patch(
            "lumina.api.domain_middleware.verify_scoped_jwt",
            side_effect=TokenExpiredError("expired"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_domain_user(credentials=_creds()))
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    @pytest.mark.unit
    def test_raises_401_on_invalid_token(self) -> None:
        with patch(
            "lumina.api.domain_middleware.verify_scoped_jwt",
            side_effect=TokenInvalidError("bad"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_domain_user(credentials=_creds()))
        assert exc.value.status_code == 401

    @pytest.mark.unit
    def test_raises_401_on_auth_error(self) -> None:
        with patch(
            "lumina.api.domain_middleware.verify_scoped_jwt",
            side_effect=AuthError("scope"),
        ):
            with pytest.raises(HTTPException) as exc:
                _run(get_domain_user(credentials=_creds()))
        assert exc.value.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# domain_middleware.require_domain_auth
# ═══════════════════════════════════════════════════════════════════════════


class TestRequireDomainAuth:

    @pytest.mark.unit
    def test_raises_401_when_user_is_none(self) -> None:
        with pytest.raises(HTTPException) as exc:
            require_domain_auth(None)
        assert exc.value.status_code == 401

    @pytest.mark.unit
    def test_raises_403_when_wrong_scope(self) -> None:
        """Admin token rejected by domain check → 403."""
        with pytest.raises(HTTPException) as exc:
            require_domain_auth({"sub": "a1", "token_scope": "admin"})
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_raises_403_on_user_scope(self) -> None:
        with pytest.raises(HTTPException) as exc:
            require_domain_auth({"sub": "u1", "token_scope": "user"})
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_returns_user_on_domain_scope(self) -> None:
        user = {"sub": "da-1", "token_scope": "domain"}
        assert require_domain_auth(user) is user


# ═══════════════════════════════════════════════════════════════════════════
# domain_middleware.require_domain_scope
# ═══════════════════════════════════════════════════════════════════════════


class TestRequireDomainScope:

    @pytest.mark.unit
    def test_raises_403_when_no_governed_modules(self) -> None:
        """DA with no governed_modules claim → 403 (access denied to everything)."""
        user = {"sub": "da-1", "token_scope": "domain", "governed_modules": []}
        with pytest.raises(HTTPException) as exc:
            require_domain_scope(user, "edu/algebra")
        assert exc.value.status_code == 403
        assert "no governed modules" in exc.value.detail.lower()

    @pytest.mark.unit
    def test_raises_403_when_governed_modules_absent(self) -> None:
        """Missing governed_modules key entirely → 403."""
        user = {"sub": "da-1", "token_scope": "domain"}
        with pytest.raises(HTTPException) as exc:
            require_domain_scope(user, "edu/algebra")
        assert exc.value.status_code == 403

    @pytest.mark.unit
    def test_raises_403_when_module_outside_scope(self) -> None:
        """Module not in governed list → 403 with module id in detail."""
        user = {"sub": "da-1", "token_scope": "domain", "governed_modules": ["edu/algebra"]}
        with pytest.raises(HTTPException) as exc:
            require_domain_scope(user, "agri/crop-planning")
        assert exc.value.status_code == 403
        assert "agri/crop-planning" in exc.value.detail

    @pytest.mark.unit
    def test_passes_silently_when_module_in_scope(self) -> None:
        """Module in governed list → no exception, returns None."""
        user = {"sub": "da-1", "token_scope": "domain", "governed_modules": ["edu/algebra", "edu/geometry"]}
        result = require_domain_scope(user, "edu/algebra")
        assert result is None
