"""Deterministic context staging helpers for the coding-agent pack.

Lightweight, dependency-free helpers for splitting text into overlapping
chunks, estimating token counts, and selecting relevant chunks for a
budget-constrained prompt window.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Dict
import re


def rough_tokens(text: str) -> int:
    """Return a rough token estimate (word count)."""
    if not text:
        return 0
    return len(text.strip().split())


def clean_text(text: str) -> str:
    """Strip null bytes and collapse whitespace to single spaces."""
    if text is None:
        return ""
    s = text.replace("\x00", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def split_words(text: str, chunk_words: int = 220, overlap_words: int = 40) -> List[str]:
    """Split text into overlapping word chunks.

    Returns a list of chunk strings. Deterministic and pure.
    """
    cleaned = clean_text(text)
    words = cleaned.split()
    if not words:
        return []
    if chunk_words <= 0:
        raise ValueError("chunk_words must be > 0")
    step = max(1, chunk_words - overlap_words)
    chunks: List[str] = []
    for i in range(0, len(words), step):
        chunk = words[i : i + chunk_words]
        if not chunk:
            break
        chunks.append(" ".join(chunk))
        if i + chunk_words >= len(words):
            break
    return chunks


def _score_chunk(chunk_text: str, query_terms: Iterable[str]) -> float:
    s = chunk_text.lower()
    score = 0
    for t in query_terms:
        if not t:
            continue
        score += s.count(t.lower())
    return float(score)


def stage_context(
    chunks: Iterable[Dict[str, Any]],
    query: str,
    budget_tokens: int = 4500,
    top_k: int = 6,
    max_per_path: int = 2,
) -> Dict[str, Any]:
    """Selects relevant chunks up to a token budget.

    `chunks` is an iterable of dicts with keys: `text` and `path`.
    Selection is lexical: counts occurrences of query terms in chunk text.
    Returns a deterministically-ordered selection list.
    """
    qterms = [t for t in re.split(r"\W+", query.lower()) if t]
    scored = []
    for c in chunks:
        text = clean_text(c.get("text") or "")
        path = c.get("path") or ""
        score = _score_chunk(text, qterms) if qterms else 0.0
        tokens = rough_tokens(text)
        scored.append({"text": text, "path": path, "score": score, "tokens": tokens})

    # stable sort by (-score, path, index) to make deterministic
    scored.sort(key=lambda x: (-x["score"], x["path"], x["text"]))

    selected = []
    used_tokens = 0
    per_path_count = {}

    for item in scored:
        if len(selected) >= top_k:
            break
        if used_tokens + item["tokens"] > budget_tokens:
            continue
        cnt = per_path_count.get(item["path"], 0)
        if cnt >= max_per_path:
            continue
        selected.append({"text": item["text"], "path": item["path"], "score": item["score"]})
        used_tokens += item["tokens"]
        per_path_count[item["path"]] = cnt + 1

    provenance = {"budget_tokens": int(budget_tokens), "selected_count": len(selected), "query": query}
    summary = f"selected {len(selected)} chunk(s) for query"
    recall_hints = list(dict.fromkeys([t for t in qterms]))

    return {"selected": selected, "summary": summary, "provenance": provenance, "recall_hints": recall_hints}
