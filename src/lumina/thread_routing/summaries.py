"""Transcript-free rolling recap state for scoped routed threads."""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from lumina.retrieval.institutional import InstitutionalMemoryIndexer
from lumina.thread_routing.policy import ThreadRoutingPolicy

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")
_STOP_WORDS = frozenset({
    "about", "after", "again", "because", "before", "could", "from", "have",
    "here", "into", "just", "need", "please", "that", "the", "this", "what",
    "when", "with", "would", "your",
})


def _state_key(thread_id: str, organization_id: str, site_id: str) -> str:
    payload = "\x1f".join((organization_id, site_id, thread_id)).encode("utf-8")
    return f"thread-summary-{hashlib.sha256(payload).hexdigest()}"


def _topics(message: str) -> list[str]:
    """Derive bounded topic labels, never retaining the source turn verbatim."""
    labels: list[str] = []
    for token in _TOKEN_RE.findall(message.lower()):
        if token not in _STOP_WORDS and token not in labels:
            labels.append(token)
        if len(labels) == 6:
            break
    return labels or ["general"]


def record_thread_recap(
    *,
    persistence: Any,
    indexer: InstitutionalMemoryIndexer,
    policy: ThreadRoutingPolicy,
    thread_id: str,
    actor_id: str,
    turn_count: int,
    message: str,
    action: str,
    domain_id: str | None,
    device_id: str | None = None,
) -> dict[str, Any] | None:
    """Persist and index a recap at turn one and each configured recap interval."""
    if turn_count < 1:
        raise ValueError("thread recap requires a positive turn count")
    state = persistence.load_session_state(_state_key(thread_id, policy.organization_id, policy.site_id))
    previous = state.get("summary_state") if isinstance(state, dict) else None
    if previous is not None and not isinstance(previous, dict):
        raise ValueError("stored thread summary state is invalid")
    previous_end = int(previous.get("turn_end", 0)) if previous else 0
    if previous and turn_count < previous_end:
        raise ValueError("thread recap turn count cannot move backwards")
    if previous and turn_count - previous_end < policy.recap_interval_turns:
        return None

    labels = _topics(message)
    recap_version = int(previous.get("recap_version", 0)) + 1 if previous else 1
    summary_record_id = str(uuid.uuid4())
    updated_utc = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    summary_state: dict[str, Any] = {
        "schema_version": "1.0.0",
        "thread_id": thread_id,
        "organization_id": policy.organization_id,
        "site_id": policy.site_id,
        "actor_id": actor_id,
        "status": "open",
        "summary_record_id": summary_record_id,
        "recap_version": recap_version,
        "turn_start": previous_end + 1,
        "turn_end": turn_count,
        "topics": labels,
        "updated_utc": updated_utc,
    }
    if device_id:
        summary_state["device_id"] = device_id
    summary = "Topics: " + ", ".join(labels) + f". Latest action: {action}."
    record: dict[str, Any] = {
        "record_type": "ThreadSummaryRecord",
        "record_id": summary_record_id,
        "organization_id": policy.organization_id,
        "site_id": policy.site_id,
        "actor_id": actor_id,
        "thread_id": thread_id,
        "summary": summary,
        "domain_id": domain_id or "",
    }
    if device_id:
        record["device_id"] = device_id
    indexer.ingest([record])
    persistence.save_session_state(
        _state_key(thread_id, policy.organization_id, policy.site_id),
        {"summary_state": summary_state},
    )
    return summary_state