"""Coding Agent domain — runtime adapter skeleton.

The coding-agent pack is a bounded artifact factory. These adapters are
deterministic stubs that expose the required pack callables without making
live model, forge, credential, or network calls.
"""

from __future__ import annotations

import json
from typing import Any, Callable


DEFAULT_EVIDENCE: dict[str, Any] = {
    "job_scope_valid": False,
    "authority_boundary_violation": False,
    "requested_files": [],
    "patch_generated": False,
    "tests_passed": None,
    "confidence": 0.5,
}


def build_initial_state(profile: dict[str, Any]) -> dict[str, Any]:
    """Build initial coding-agent session state from profile data."""
    entity_state = profile.get("entity_state") or {}
    return {
        "turn_count": int(entity_state.get("turn_count", 0)),
        "scoped_jobs_completed": int(entity_state.get("completed_jobs", 0)),
        "boundary_violations": int(entity_state.get("rejected_boundary_requests", 0)),
        "pending_validation": False,
    }


def domain_step(
    state: dict[str, Any],
    task_spec: dict[str, Any],
    evidence: dict[str, Any],
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one bounded coding-agent domain tick."""
    new_state = dict(state)
    new_state["turn_count"] = int(new_state.get("turn_count", 0)) + 1

    # Prefer micro-context if provided by the pre-interpreter
    micro = evidence.get("micro_context") if isinstance(evidence.get("micro_context"), dict) else None
    boundary_violation = bool(evidence.get("authority_boundary_violation", False)) or bool(
        micro and micro.get("authority_boundary")
    )
    scope_valid = bool(evidence.get("job_scope_valid", False)) or bool(micro and micro.get("scope_valid"))
    patch_generated = bool(evidence.get("patch_generated", False))
    tests_passed = evidence.get("tests_passed")

    if boundary_violation or not scope_valid:
        new_state["boundary_violations"] = int(new_state.get("boundary_violations", 0)) + 1
        return new_state, {
            "tier": "critical",
            "action": "reject_out_of_scope" if not scope_valid else "request_system_scope",
            "frustration": False,
            "escalation_eligible": True,
            "reason": "authority_boundary",
        }

    if patch_generated and tests_passed is False:
        new_state["pending_validation"] = True
        return new_state, {
            "tier": "minor",
            "action": "run_local_validation",
            "frustration": False,
            "escalation_eligible": False,
            "reason": "validation_required",
        }

    if patch_generated and tests_passed is True:
        new_state["pending_validation"] = False
        new_state["scoped_jobs_completed"] = int(new_state.get("scoped_jobs_completed", 0)) + 1
        return new_state, {
            "tier": "ok",
            "action": "stage_patch_for_review",
            "frustration": False,
            "escalation_eligible": False,
            "reason": "validated_patch",
        }

    return new_state, {
        "tier": "ok",
        "action": None,
        "frustration": False,
        "escalation_eligible": False,
        "reason": task_spec.get("task_id", "coding_agent_step"),
    }


def _strip_markdown_fences(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")]
    return cleaned.strip()


def _merge_defaults(evidence: dict[str, Any], default_fields: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_EVIDENCE)
    merged.update(default_fields or {})
    for key, value in evidence.items():
        if key in merged:
            merged[key] = value
    if merged["requested_files"] is None:
        merged["requested_files"] = []
    return merged


def interpret_turn_input(
    call_llm: Callable[[str, str, str | None], str],
    input_text: str,
    task_context: dict[str, Any],
    prompt_text: str,
    default_fields: dict[str, Any] | None = None,
    tool_fns: dict[str, Callable[..., Any]] | None = None,
) -> dict[str, Any]:
    """Interpret a turn into bounded coding-agent evidence."""
    raw_response = call_llm(
        system=prompt_text,
        user=f"Coding-agent turn: {input_text}",
        model=None,
    )

    try:
        parsed = json.loads(_strip_markdown_fences(raw_response))
        evidence = parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, IndexError, TypeError):
        evidence = {}

    merged = _merge_defaults(evidence, default_fields)

    scope_checker = (tool_fns or {}).get("scope_checker")
    if scope_checker is not None:
        checked = scope_checker({"input_text": input_text, "task_context": task_context, "evidence": merged})
        if isinstance(checked, dict):
            merged.update({key: value for key, value in checked.items() if key in merged})

    return merged