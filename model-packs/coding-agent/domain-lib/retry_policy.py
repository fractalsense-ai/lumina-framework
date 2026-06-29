from __future__ import annotations

from typing import Any


def classify_failure(error: Any) -> str:
    message = str(error or "").lower()

    if not message:
        return "unknown"
    if "timeout" in message or "temporar" in message or "connection" in message:
        return "transient"
    if "rate limit" in message or "429" in message:
        return "rate_limit"
    if "unauthorized" in message or "forbidden" in message or "permission" in message:
        return "auth"
    if "invalid" in message or "validation" in message or "schema" in message:
        return "validation"
    return "tool_error"


def should_retry(failure_class: str, attempt_count: int, max_retries: int) -> bool:
    if attempt_count >= max_retries:
        return False
    return failure_class in {"transient", "rate_limit", "unknown"}


def next_backoff_seconds(
    attempt_count: int,
    base_backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 30.0,
) -> float:
    attempt = max(0, int(attempt_count))
    backoff = float(base_backoff_seconds) * (2 ** attempt)
    return min(float(max_backoff_seconds), backoff)
