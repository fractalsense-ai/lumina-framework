"""Forge-neutral change-request helper utilities.

Provide safe path and branch validation and a canonical normalizer for
change request payloads. These helpers are pure and have no external
dependencies.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def validate_allowed_path(path: str, allowed_prefixes: List[str]) -> bool:
    if not path or path.startswith("/") or path.startswith("~"):
        return False
    normalized = path.replace("\\", "/")
    for pfx in allowed_prefixes:
        if normalized.startswith(pfx):
            return True
    return False


def validate_change_branch(branch: str) -> bool:
    if not branch or branch.strip() == "":
        return False
    if ".." in branch or "@{" in branch:
        return False
    if branch.startswith("/") or branch.endswith("/"):
        return False
    if re.search(r"\s", branch):
        return False
    return True


def normalize_change_request_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    title = payload.get("title")
    description = payload.get("description")
    branch = payload.get("branch")
    files = payload.get("files_changed") or payload.get("files") or []
    if not title or not description or not branch:
        raise ValueError("missing required fields")
    return {
        "title": str(title).strip(),
        "description": str(description).strip(),
        "branch": str(branch).strip(),
        "files_changed": list(files),
        "author": payload.get("author"),
        "metadata": payload.get("metadata") or {},
    }
