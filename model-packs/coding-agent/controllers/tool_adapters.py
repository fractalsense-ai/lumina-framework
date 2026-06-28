"""Tool adapter backing functions for the coding-agent pack.

These are intentionally lightweight stubs for Slice 7. They return structured
results and emit AUDIT-level events for operations that must be recorded in
the domain ledger. Real side-effecting implementation (git, network, deploy)
is out of scope for this slice.
"""

from __future__ import annotations

from typing import Any, Dict

from lumina.system_log.event_payload import create_event, LogLevel
from lumina.system_log.log_bus import emit


def read_file_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = payload.get("path")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        return {"read_ok": True, "content": content}
    except Exception as exc:  # pragma: no cover - best-effort sandbox
        return {"read_ok": False, "content": "", "error": str(exc)}


def write_file_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = payload.get("path")
    contents = payload.get("contents", "")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(contents)
        return {"write_ok": True, "path": path}
    except Exception as exc:  # pragma: no cover
        return {"write_ok": False, "error": str(exc)}


def run_tests_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Slice 7: do not execute arbitrary commands. Simulate test run.
    commands = payload.get("commands", [])
    # Simple heuristic: if 'pytest' in commands, respond with True
    tests_passed = any("pytest" in c for c in commands)
    return {"tests_passed": bool(tests_passed), "output": "simulated"}


def stage_patch_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    files = tuple(payload.get("files", []))
    # Emit an AUDIT trace event to record the staging action for this domain.
    event = create_event(
        source="coding_agent.tool_adapters",
        level=LogLevel.AUDIT,
        category="tool_call",
        message="stage_patch invoked",
        data={"files": list(files)},
        domain_id="coding-agent",
    )
    emit(event)
    return {"staged": True, "files": list(files)}
