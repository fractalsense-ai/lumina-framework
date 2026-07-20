"""vector_store.py — Flat-file numpy vector store with cosine similarity search.

Stores embeddings as a ``.npz`` archive and chunk metadata as a JSON sidecar.
Optimised for <10K documents — uses brute-force cosine search (no ANN index).

Persistence layout::

    {store_dir}/
        vectors.npz          # numpy array (N, 384)
        metadata.json        # list of chunk metadata dicts
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from lumina.retrieval.embedder import EMBEDDING_DIM, DocChunk
from lumina.retrieval.contracts import RetrievalFilter

if TYPE_CHECKING:
    from numpy.typing import NDArray

log = logging.getLogger("lumina-retrieval")


# ── Search result ────────────────────────────────────────────

class SearchResult:
    __slots__ = ("chunk", "score")

    def __init__(self, chunk: DocChunk, score: float) -> None:
        self.chunk = chunk
        self.score = score

    def __repr__(self) -> str:
        return f"SearchResult(score={self.score:.4f}, heading={self.chunk.heading!r})"


# ── Vector store ─────────────────────────────────────────────

class VectorStore:
    """Numpy-backed vector store with cosine similarity search.

    Parameters
    ----------
    store_dir:
        Directory for persisted ``.npz`` + ``metadata.json`` files.
        Created on first :meth:`save`.
    """

    def __init__(self, store_dir: Path | str) -> None:
        self._dir = Path(store_dir)
        self._vectors: NDArray[np.float32] = np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        self._chunks: list[DocChunk] = []

    # ── Mutation ──────────────────────────────────────────────

    def add(self, chunks: list[DocChunk], vectors: NDArray[np.float32]) -> None:
        """Append *chunks* and their *vectors* to the store (in-memory)."""
        if len(chunks) != vectors.shape[0]:
            raise ValueError("chunks and vectors must have the same length")
        if vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIM:
            raise ValueError(f"vectors must be shape (N, {EMBEDDING_DIM})")
        self._vectors = np.vstack([self._vectors, vectors]) if self._vectors.size else vectors
        self._chunks.extend(chunks)

    def clear(self) -> None:
        """Remove all entries (in-memory only — call :meth:`save` to persist)."""
        self._vectors = np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        self._chunks = []

    # ── Search ────────────────────────────────────────────────

    def search(
        self,
        query_vec: NDArray[np.float32],
        k: int = 5,
        *,
        organization_id: str | None = None,
        site_id: str | None = None,
        actor_id: str | None = None,
        device_id: str | None = None,
        retrieval_filter: RetrievalFilter | None = None,
    ) -> list[SearchResult]:
        """Return top-*k* chunks, applying scope filters before ranking."""
        if retrieval_filter is not None:
            retrieval_filter.validate()
        if self._vectors.size == 0:
            return []

        filters = {
            "organization_id": organization_id,
            "site_id": site_id,
            "actor_id": actor_id,
            "device_id": device_id,
        }
        if retrieval_filter is not None:
            filters.update({
                key: value
                for key, value in retrieval_filter.as_metadata().items()
                if value is not None and filters.get(key) is None
            })
        eligible_indices = [
            index
            for index, chunk in enumerate(self._chunks)
            if (
                (not retrieval_filter or not retrieval_filter.institutional_only
                 or chunk.content_type == "institutional_memory")
                and all(
                    expected is None or getattr(chunk, field_name, None) == expected
                    for field_name, expected in filters.items()
                )
            )
        ]
        if not eligible_indices:
            return []

        # Cosine similarity: dot(a, b) / (||a|| * ||b||)
        candidate_vectors = self._vectors[eligible_indices]
        norms = np.linalg.norm(candidate_vectors, axis=1)
        q_norm = np.linalg.norm(query_vec)
        # Guard against zero-norm vectors
        safe_denom = norms * q_norm
        safe_denom = np.where(safe_denom == 0, 1.0, safe_denom)
        scores = candidate_vectors @ query_vec / safe_denom

        top_k = min(k, len(scores))
        if top_k <= 0:
            return []
        top_indices = np.argpartition(scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [
            SearchResult(self._chunks[eligible_indices[i]], float(scores[i]))
            for i in top_indices
        ]

    # ── Persistence ───────────────────────────────────────────

    def save(self) -> None:
        """Write vectors and metadata to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self._dir / "vectors.npz", vectors=self._vectors)
        meta = [asdict(c) for c in self._chunks]
        (self._dir / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("VectorStore saved %d vectors to %s", len(self._chunks), self._dir)

    def load(self) -> None:
        """Load vectors and metadata from disk. Overwrites in-memory state."""
        vec_path = self._dir / "vectors.npz"
        meta_path = self._dir / "metadata.json"
        if not vec_path.exists() or not meta_path.exists():
            log.info("VectorStore: no persisted data at %s", self._dir)
            return
        data = np.load(vec_path)
        self._vectors = data["vectors"].astype(np.float32)
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        self._chunks = [
            DocChunk(
                source_path=r["source_path"],
                heading=r["heading"],
                text=r["text"],
                content_hash=r["content_hash"],
                content_type=r.get("content_type", "doc"),
                domain_id=r.get("domain_id", ""),
                organization_id=r.get("organization_id"),
                site_id=r.get("site_id"),
                actor_id=r.get("actor_id"),
                device_id=r.get("device_id"),
                record_type=r.get("record_type"),
                record_id=r.get("record_id"),
                thread_id=r.get("thread_id"),
                provider=r.get("provider"),
                external_record_type=r.get("external_record_type"),
                external_record_id=r.get("external_record_id"),
                module_key=r.get("module_key"),
                created_utc=r.get("created_utc"),
            )
            for r in raw
        ]
        log.info("VectorStore loaded %d vectors from %s", len(self._chunks), self._dir)

    # ── Properties ────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._chunks)

    def has_hash(self, content_hash: str) -> bool:
        """Check if a chunk with this content hash is already stored."""
        return any(c.content_hash == content_hash for c in self._chunks)


# ── Per-domain store registry ────────────────────────────────

class VectorStoreRegistry:
    """Manage per-domain :class:`VectorStore` instances.

    Each domain gets its own ``{base_dir}/{domain_id}/`` subdirectory.
    A special ``_global`` store aggregates lightweight routing vectors.

    Parameters
    ----------
    base_dir:
        Root directory for all per-domain vector stores.
    """

    GLOBAL_DOMAIN = "_global"

    def __init__(self, base_dir: Path | str) -> None:
        self._base = Path(base_dir)
        self._stores: dict[str, VectorStore] = {}

    def get(self, domain_id: str) -> VectorStore:
        """Return (or create) the store for *domain_id*."""
        if domain_id not in self._stores:
            self._stores[domain_id] = VectorStore(self._base / domain_id)
        return self._stores[domain_id]

    @property
    def global_store(self) -> VectorStore:
        """Shortcut for the lightweight routing store."""
        return self.get(self.GLOBAL_DOMAIN)

    def domain_ids(self) -> list[str]:
        """List domain-ids that have a persisted store on disk."""
        if not self._base.is_dir():
            return []
        return sorted(
            d.name for d in self._base.iterdir()
            if d.is_dir() and (d / "vectors.npz").exists()
        )

    def load_all(self) -> None:
        """Load every persisted domain store into memory."""
        for did in self.domain_ids():
            self.get(did).load()
