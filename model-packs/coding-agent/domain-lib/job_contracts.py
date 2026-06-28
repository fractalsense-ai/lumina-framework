"""Coding-agent job contract stubs.

These dataclasses document the bounded handoff from the System Pack to the
Coding Agent pack. They intentionally carry no forge credentials or provider
binding.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodingAgentJob:
    """System-approved coding task scope."""

    job_id: str
    summary: str
    allowed_paths: tuple[str, ...] = ()
    validation_commands: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = (
        "credential_access",
        "authority_expansion",
        "unapproved_deploy",
    )
    task_graph: tuple[object, ...] = ()


@dataclass(frozen=True)
class CodingAgentResult:
    """Reviewable result returned to the System Pack."""

    job_id: str
    changed_paths: tuple[str, ...] = ()
    validation_status: str = "not_run"
    summary: str = ""
    evidence: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskNode:
    """Represents a single task node in a deterministic DAG handed to the pack.

    Lightweight and intentionally generic — `mcp_tools` is a placeholder for
    future MCP integration.
    """

    task_id: str
    task_type: str
    tier: int
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    blocked_by: tuple[str, ...] = ()
    success_emit: str | None = None
    fail_emit: str | None = None
    context_mode: str = "rag"
    mcp_tools: tuple[str, ...] = ()