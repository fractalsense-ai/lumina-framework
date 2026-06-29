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
    # Safe test runner: allow a short explicit command allowlist and run via subprocess
    import subprocess
    import shlex
    import os

    commands = payload.get("commands", [])
    working_dir = payload.get("working_dir") or os.getcwd()

    # Basic validation: commands must be a non-empty list
    if not isinstance(commands, list) or not commands:
        return {"tests_passed": False, "output": "invalid_commands"}

    # Allow only certain first tokens to avoid arbitrary shell execution
    allowed_first = {"pytest", "python", "python3"}
    first_tok = shlex.split(commands[0])[0] if isinstance(commands[0], str) and commands[0].strip() else ""
    if first_tok not in allowed_first:
        return {"tests_passed": False, "output": "unauthorized_command"}

    # Validate working_dir via a safe path check from change_request if available
    try:
        import importlib.util, pathlib

        policy_path = pathlib.Path(__file__).parent.parent / "domain-lib" / "change_request.py"
        spec = importlib.util.spec_from_file_location("change_request", str(policy_path))
        cr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cr)
        if not cr.validate_allowed_path(working_dir, ["."]):
            # Fallback to repository cwd instead of failing the call
            working_dir = os.getcwd()
    except Exception:
        # If validator not available, continue but restrict to cwd
        working_dir = os.getcwd()

    try:
        # Execute the provided command list sequentially; prefer running a single command
        proc = subprocess.run(commands, cwd=working_dir, capture_output=True, text=True, timeout=120)
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return {"tests_passed": proc.returncode == 0, "output": output[:4000], "return_code": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"tests_passed": False, "output": "timeout", "return_code": -1}
    except FileNotFoundError:
        return {"tests_passed": False, "output": "command_not_found", "return_code": -1}


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
