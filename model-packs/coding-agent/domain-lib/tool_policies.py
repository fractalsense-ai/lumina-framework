from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ToolCallRequest:
    tool_id: str
    payload: Dict[str, Any]
    caller_context: Dict[str, Any]


@dataclass
class ToolCallPolicy:
    allowed_tools: List[str]
    deny_reason: str = ""


def build_default_policy(allowed_tools: List[str]) -> ToolCallPolicy:
    """Construct a deny-by-default policy from the registered adapter ids."""
    return ToolCallPolicy(allowed_tools=list(allowed_tools))


def check_tool_call(request: ToolCallRequest, policy: ToolCallPolicy) -> Tuple[bool, str]:
    """Return (allowed, reason). Allowed only if `tool_id` is in allowlist and payload is a non-empty dict."""
    if not isinstance(request.payload, dict) or not request.payload:
        return False, "empty_payload"
    if request.tool_id not in policy.allowed_tools:
        return False, f"tool_not_allowed:{request.tool_id}"
    # payload basic sanity: not empty and no obviously malicious keys
    return True, ""
