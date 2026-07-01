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


def _load_execution_modules():
    try:
        from model_packs.coding_agent.domain_lib import execution_state_store as _store
        from model_packs.coding_agent.domain_lib import tier_contracts as _contracts
        return _store, _contracts
    except Exception:
        import importlib.util
        import pathlib
        import sys

        base = pathlib.Path(__file__).parent.parent

        store_path = base / "domain-lib" / "execution_state_store.py"
        spec = importlib.util.spec_from_file_location("coding_agent_execution_state_store", str(store_path))
        _store = importlib.util.module_from_spec(spec)
        sys.modules["coding_agent_execution_state_store"] = _store
        spec.loader.exec_module(_store)

        contracts_path = base / "domain-lib" / "tier_contracts.py"
        spec = importlib.util.spec_from_file_location("coding_agent_tier_contracts_runtime", str(contracts_path))
        _contracts = importlib.util.module_from_spec(spec)
        sys.modules["coding_agent_tier_contracts_runtime"] = _contracts
        spec.loader.exec_module(_contracts)

        return _store, _contracts


def _load_orchestration_modules():
    try:
        from model_packs.coding_agent.controllers import orchestration_loop as _loop
        from model_packs.coding_agent.domain_lib import turn_budget as _turn_budget
        return _loop, _turn_budget
    except Exception:
        import importlib.util
        import pathlib
        import sys

        base = pathlib.Path(__file__).parent.parent

        loop_path = base / "controllers" / "orchestration_loop.py"
        spec = importlib.util.spec_from_file_location("coding_agent_orchestration_loop", str(loop_path))
        _loop = importlib.util.module_from_spec(spec)
        sys.modules["coding_agent_orchestration_loop"] = _loop
        spec.loader.exec_module(_loop)

        budget_path = base / "domain-lib" / "turn_budget.py"
        spec = importlib.util.spec_from_file_location("coding_agent_turn_budget_runtime", str(budget_path))
        _turn_budget = importlib.util.module_from_spec(spec)
        sys.modules["coding_agent_turn_budget_runtime"] = _turn_budget
        spec.loader.exec_module(_turn_budget)

        return _loop, _turn_budget


def _resolve_plan_id(task_slice: dict[str, Any], task_spec: dict[str, Any]) -> str:
    if not isinstance(task_slice, dict):
        return str(task_spec.get("task_id") or "default")
    if task_slice.get("plan_id"):
        return str(task_slice.get("plan_id"))
    plan = task_slice.get("plan") if isinstance(task_slice.get("plan"), dict) else {}
    if plan.get("plan_id"):
        return str(plan.get("plan_id"))
    return str(task_spec.get("task_id") or "default")


def _should_use_orchestration_loop(evidence: dict[str, Any]) -> bool:
    if not isinstance(evidence, dict):
        return False
    if bool(evidence.get("use_orchestration_loop")):
        return True
    micro = evidence.get("micro_context") if isinstance(evidence.get("micro_context"), dict) else {}
    if bool(micro.get("use_orchestration_loop")):
        return True
    has_plan = isinstance(evidence.get("plan"), dict)
    has_task_slices = isinstance(evidence.get("task_slices"), list) and bool(evidence.get("task_slices"))
    return bool(has_plan and has_task_slices)


def domain_step(
    state: dict[str, Any],
    task_spec: dict[str, Any],
    evidence: dict[str, Any],
    params: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one bounded coding-agent domain tick."""
    new_state = dict(state)
    new_state["turn_count"] = int(new_state.get("turn_count", 0)) + 1

    # Policy gate: if a tool_call is present in evidence, check deny-by-default policy
    tool_call = evidence.get("tool_call") if isinstance(evidence.get("tool_call"), dict) else None
    if tool_call:
        try:
            import importlib.util, pathlib

            tp_path = pathlib.Path(__file__).parent.parent / "domain-lib" / "tool_policies.py"
            spec = importlib.util.spec_from_file_location("coding_agent_tool_policies", str(tp_path))
            tp = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tp)

            registered = [
                "adapter/ca/read-file/v1",
                "adapter/ca/write-file/v1",
                "adapter/ca/run-tests/v1",
                "adapter/ca/stage-patch/v1",
            ]
            policy = tp.build_default_policy(registered)
            req = tp.ToolCallRequest(tool_id=tool_call.get("tool_id"), payload=tool_call.get("payload", {}), caller_context=tool_call.get("caller_context", {}))
            allowed, reason = tp.check_tool_call(req, policy)
            if not allowed:
                return new_state, {
                    "tier": "critical",
                    "action": "reject_unauthorized_tool",
                    "frustration": False,
                    "escalation_eligible": False,
                    "reason": reason,
                }
        except Exception:
            # If policy module fails to load, fallback to safe behavior: deny
            return new_state, {
                "tier": "critical",
                "action": "reject_unauthorized_tool",
                "frustration": False,
                "escalation_eligible": False,
                "reason": "policy_load_failure",
            }

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
        # If the caller requested immediate activation, require System Pack approval.
        try:
            import importlib.util
            import pathlib
            import sys

            ag_path = pathlib.Path(__file__).parent.parent / "domain-lib" / "activation_gate.py"
            spec = importlib.util.spec_from_file_location("coding_agent_activation_gate", str(ag_path))
            _ag = importlib.util.module_from_spec(spec)
            sys.modules["coding_agent_activation_gate"] = _ag
            spec.loader.exec_module(_ag)
        except Exception:
            _ag = None

        if isinstance(evidence, dict) and evidence.get("activation_request"):
            approved = False
            if _ag is not None:
                try:
                    approved = _ag.validate_activation(evidence)
                except Exception:
                    approved = False

            if not approved:
                return new_state, {
                    "tier": "ok",
                    "action": "awaiting_system_approval",
                    "frustration": False,
                    "escalation_eligible": True,
                    "reason": "activation_requires_system_approval",
                }

        return new_state, {
            "tier": "ok",
            "action": "stage_patch_for_review",
            "frustration": False,
            "escalation_eligible": False,
            "reason": "validated_patch",
            "approved": True if isinstance(evidence, dict) and evidence.get("activation_request") and _ag is not None and _ag.validate_activation(evidence) else False,
        }

    # Prioritise orchestration loop when requested with plan + task_slices.
    if _should_use_orchestration_loop(evidence):
        try:
            _store, _contracts = _load_execution_modules()
            _loop, _turn_budget = _load_orchestration_modules()
        except Exception as exc:
            return new_state, {
                "action": "orchestration_failed",
                "reason": "orchestration_modules_missing",
                "detail": str(exc),
            }

        try:
            state_store = _store.ExecutionStateStore.from_dict(new_state.get("execution_state_store") or {})
        except Exception as exc:
            return new_state, {
                "action": "orchestration_failed",
                "reason": "execution_state_store_unavailable",
                "detail": str(exc),
            }

        plan_payload = evidence.get("plan") if isinstance(evidence.get("plan"), dict) else None
        slices_payload = evidence.get("task_slices") if isinstance(evidence.get("task_slices"), list) else []

        task_slice_payload = dict(evidence.get("task_slice") or {})
        if plan_payload is None and isinstance(task_slice_payload.get("plan"), dict):
            plan_payload = dict(task_slice_payload.get("plan") or {})
        if not slices_payload and task_slice_payload:
            slices_payload = [task_slice_payload]

        if not isinstance(plan_payload, dict) or not slices_payload:
            return new_state, {"action": "orchestration_failed", "reason": "plan_or_slices_missing"}

        plan_id = str(plan_payload.get("plan_id") or task_spec.get("task_id") or "default")
        latest = state_store.load_latest_checkpoint(plan_id)
        explicit_context_payload = evidence.get("execution_context") if isinstance(evidence.get("execution_context"), dict) else None
        if explicit_context_payload is None and isinstance(task_slice_payload.get("execution_context"), dict):
            explicit_context_payload = dict(task_slice_payload.get("execution_context") or {})
        if latest is not None:
            restored_context = _contracts.ExecutionContext.from_dict(latest.execution_context)
        else:
            restored_context = _contracts.ExecutionContext.from_dict(explicit_context_payload or {})

        budget = _turn_budget.TurnBudget.from_params(params)
        orchestration = _loop.execute_dag_until(
            plan_payload,
            restored_context.to_dict(),
            slices_payload,
            budget,
            checkpoint_store=state_store,
            plan_id=plan_id,
        )

        orchestration_result = orchestration.to_dict() if hasattr(orchestration, "to_dict") else dict(orchestration or {})
        if orchestration_result.get("halt_reason") == "checkpoint_persist_failed":
            return new_state, {
                "action": "orchestration_failed",
                "reason": "checkpoint_persist_failed",
                "dispatch_result": orchestration_result,
            }

        new_state["execution_state_store"] = state_store.to_dict()

        return new_state, {"action": "orchestrated", "dispatch_result": orchestration_result}

    # Prioritise execution-phase dispatch when a `task_slice` is present
    if evidence and evidence.get("task_slice"):
        try:
            from model_packs.coding_agent.controllers import tier_dispatcher as _td
        except Exception:
            # robust fallback: load by path
            try:
                import importlib.util, pathlib, sys

                td_path = pathlib.Path(__file__).parent / "controllers" / "tier_dispatcher.py"
                if not td_path.exists():
                    td_path = pathlib.Path(__file__).parent.parent / "controllers" / "tier_dispatcher.py"
                spec = importlib.util.spec_from_file_location("coding_agent_tier_dispatcher", str(td_path))
                _td = importlib.util.module_from_spec(spec)
                sys.modules["coding_agent_tier_dispatcher"] = _td
                spec.loader.exec_module(_td)
            except Exception:
                return new_state, {"action": "dispatch_failed", "reason": "dispatcher_missing"}

        try:
            _store, _contracts = _load_execution_modules()
            state_store = _store.ExecutionStateStore.from_dict(new_state.get("execution_state_store") or {})
        except Exception:
            state_store = None
            _contracts = None

        # execution_tier expected from micro_context if present
        execution_tier = None
        micro = evidence.get("micro_context") or {}
        execution_tier = micro.get("execution_tier") if isinstance(micro, dict) else None
        if execution_tier is None:
            execution_tier = 3

        task_slice_payload = dict(evidence.get("task_slice") or {})

        if int(execution_tier) == 3 and state_store is not None and _contracts is not None:
            plan_id = _resolve_plan_id(task_slice_payload, task_spec)
            latest = state_store.load_latest_checkpoint(plan_id)
            if latest is not None:
                restored_context = _contracts.ExecutionContext.from_dict(latest.execution_context)
            else:
                restored_context = _contracts.ExecutionContext.from_dict(task_slice_payload.get("execution_context") or {})

            # Pre-flight provider / API-key check to avoid making live calls without creds
            try:
                from model_packs.coding_agent.domain_lib import provider_routing as _pr
            except Exception:
                try:
                    import importlib.util, pathlib, sys

                    pr_path = pathlib.Path(__file__).parent.parent / "domain-lib" / "provider_routing.py"
                    spec = importlib.util.spec_from_file_location("coding_agent_provider_routing_runtime", str(pr_path))
                    _pr = importlib.util.module_from_spec(spec)
                    sys.modules["coding_agent_provider_routing_runtime"] = _pr
                    spec.loader.exec_module(_pr)
                except Exception:
                    _pr = None

            if _pr is not None:
                try:
                    prov = _pr.resolve_provider_for_slice(task_slice_payload)
                    if prov.get("requires_api_key"):
                        env_name = prov.get("api_key_env")
                        if env_name and not (env_name in __import__("os").environ):
                            return new_state, {
                                "action": "dispatch_failed",
                                "reason": "missing_api_key",
                                "provider": prov,
                            }
                except Exception:
                    # Fail safe: continue and let downstream dispatcher handle policy
                    prov = None

            dispatch_result = _td.dispatch_to_tier_with_state(
                3,
                task_slice_payload,
                execution_context=restored_context.to_dict(),
            )

            persisted_context = dispatch_result.get("execution_context") if isinstance(dispatch_result, dict) else None
            if isinstance(persisted_context, dict):
                source = "tier3_dispatch"
                tier3_evidence = dispatch_result.get("tier3_evidence")
                if isinstance(tier3_evidence, dict) and tier3_evidence.get("status"):
                    source = f"tier3_{tier3_evidence.get('status')}"
                state_store.save_checkpoint(plan_id, persisted_context, source=source)
                new_state["execution_state_store"] = state_store.to_dict()
        else:
            dispatch_result = _td.dispatch_to_tier(int(execution_tier), task_slice_payload)

        return new_state, {"action": "dispatched", "dispatch_result": dispatch_result}

    # Tier-2 planning: if micro-context prefers tier 2 and a job payload exists, decompose
    micro = evidence.get("micro_context") or {}
    execution_tier = micro.get("execution_tier") if isinstance(micro, dict) else None
    if execution_tier == 2 and evidence.get("job"):
        try:
            from model_packs.coding_agent.controllers import tier_dispatcher as _td
        except Exception:
            try:
                import importlib.util, pathlib, sys

                td_path = pathlib.Path(__file__).parent / "controllers" / "tier_dispatcher.py"
                if not td_path.exists():
                    td_path = pathlib.Path(__file__).parent.parent / "controllers" / "tier_dispatcher.py"
                spec = importlib.util.spec_from_file_location("coding_agent_tier_dispatcher", str(td_path))
                _td = importlib.util.module_from_spec(spec)
                sys.modules["coding_agent_tier_dispatcher"] = _td
                spec.loader.exec_module(_td)
            except Exception:
                return new_state, {"tier": "critical", "action": "decompose_failed", "reason": "dispatcher_missing"}

        job = evidence.get("job")
        dispatch_result = _td.dispatch_to_tier(2, job)
        return new_state, {"tier": "decomposed", "action": "decompose_job", "dispatch_result": dispatch_result}

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