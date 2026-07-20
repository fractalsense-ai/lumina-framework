"""Shared authenticated dependencies for scope-bound API routes."""
from __future__ import annotations

import functools
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from lumina.api import config as _cfg
from lumina.api.middleware import _bearer_scheme, get_current_user, require_auth
from lumina.auth.operating_context import operating_context_from_claims
from lumina.retrieval.embedder import DocEmbedder
from lumina.retrieval.institutional import InstitutionalMemoryIndexer
from lumina.retrieval.vector_store import VectorStore

_INSTITUTIONAL_INDEX_DIR = _cfg._REPO_ROOT / "data" / "retrieval-index" / "institutional-memory"


async def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """Return a verified authenticated user from the bearer-token flow."""
    return require_auth(await get_current_user(credentials))


def get_active_operating_context(
    user: dict[str, Any] = Depends(get_authenticated_user),
) -> dict[str, str | None]:
    """Require an active organization and site for scope-bound operations."""
    try:
        context = operating_context_from_claims(user)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid active operating context") from exc
    if context is None:
        raise HTTPException(status_code=403, detail="An active organization and site context is required")
    return context


@functools.lru_cache(maxsize=1)
def get_institutional_indexer() -> InstitutionalMemoryIndexer:
    """Build and share the local institutional-memory indexer lazily."""
    return InstitutionalMemoryIndexer(VectorStore(_INSTITUTIONAL_INDEX_DIR), DocEmbedder())