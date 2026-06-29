"""Job interpretation helpers for the coding-agent pack.

Provides deterministic classification and JSON extraction utilities for
interpreting operator or system job text without any external dependencies.
"""

from __future__ import annotations

import re
import json
from typing import Any, List, Dict


def classify_job_mode(text: str) -> str:
    s = (text or "").lower()
    short_exec = {"yes", "ok", "go", "sure", "proceed", "do it", "doit"}
    if any(s.strip() == token for token in short_exec):
        return "execution"
    if any(word in s for word in ("review", "check", "inspect", "read")):
        return "review"
    if any(word in s for word in ("what", "how", "why", "explain", "list")):
        return "query"
    return "unknown"


def extract_tool_json_value(text: str) -> Any | None:
    """Extract first JSON object from fenced or inline JSON in `text`.

    Returns the parsed object or None on failure.
    """
    if not text:
        return None
    # fenced block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    candidate = None
    if m:
        candidate = m.group(1)
    else:
        # inline JSON heuristic: first {...}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]

    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except Exception:
        return None


def normalize_tool_call(obj: Dict[str, Any], allowed_tools: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("tool call must be a dict")
    tool = obj.get("tool") or obj.get("name")
    if not tool or not isinstance(tool, str):
        raise ValueError("tool name missing or invalid")
    if allowed_tools is not None and tool not in allowed_tools:
        raise ValueError(f"unknown tool: {tool}")
    # Normalized shape
    return {"tool": tool, "args": obj.get("args") or obj.get("payload") or {}, "raw": obj}


def normalize_tool_calls(text: str, allowed_tools: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    obj = extract_tool_json_value(text)
    if obj is None:
        return []
    if isinstance(obj, list):
        calls = obj
    else:
        calls = [obj]
    normalized = []
    for c in calls:
        try:
            normalized.append(normalize_tool_call(c, allowed_tools))
        except ValueError:
            # do not silently grant unknown tools
            raise
    return normalized
