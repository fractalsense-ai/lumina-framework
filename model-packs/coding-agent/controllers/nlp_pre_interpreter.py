"""Deterministic Phase A pre-interpreter for coding-agent turns."""

from __future__ import annotations

from typing import Any


BOUNDARY_TERMS = (
    "bypass authority",
    "ignore system pack",
    "use credentials",
    "force push",
    "deploy without review",
)


def pre_interpret(input_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract cheap authority-boundary signals before SLM interpretation."""
    text = input_text.lower()
    requested_files = [token for token in input_text.split() if "/" in token or "\\" in token]
    return {
        "authority_boundary_hint": any(term in text for term in BOUNDARY_TERMS),
        "mentions_patch": any(term in text for term in ("patch", "diff", "edit", "modify")),
        "mentions_tests": any(term in text for term in ("test", "pytest", "validate", "ci")),
        "requested_files": requested_files,
    }