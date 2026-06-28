"""Job intake validation utilities for the coding-agent pack.

This module implements lightweight, deterministic validation suitable for
pre-interpreter checks and micro-context construction. Keep logic pure and
free of external side-effects so the runtime adapter can call it safely.
"""

from __future__ import annotations

from typing import Any


class ValidationResult:
    def __init__(self, valid: bool, errors: list[str], normalized: dict[str, Any]):
        self.valid = valid
        self.errors = errors
        self.normalized = normalized


def validate_job(payload: dict[str, Any]) -> ValidationResult:
    """Validate a job payload (best-effort).

    Rules (minimal, conservative):
    - `title`: required, non-empty string
    - `description`: required, >= 10 chars
    - `priority`: optional, one of ('low','normal','high')
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ValidationResult(False, ["payload-not-dict"], {})

    title = payload.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        errors.append("missing-or-invalid-title")

    description = payload.get("description")
    if not description or not isinstance(description, str) or len(description.strip()) < 10:
        errors.append("missing-or-short-description")

    priority = payload.get("priority")
    if priority is not None and priority not in ("low", "normal", "high"):
        errors.append("invalid-priority")

    normalized = {
        "title": (title or "").strip() if isinstance(title, str) else "",
        "description": (description or "").strip() if isinstance(description, str) else "",
        "priority": priority or "normal",
        "files": list(payload.get("files") or []),
    }

    return ValidationResult(valid=(len(errors) == 0), errors=errors, normalized=normalized)
