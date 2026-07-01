from __future__ import annotations

from typing import Any, Dict, List

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from . import tier_dispatcher
    from ..domain_lib import orchestration_result, tier3_ready_scheduler, tier_contracts, turn_budget
    from ..domain_lib import orchestration_telemetry, evidence_harvest, teardown_coordinator
except Exception:
    import importlib.util
    import pathlib
    import sys

    base = pathlib.Path(__file__).parent

    td_path = base / "tier_dispatcher.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier_dispatcher_orchestration", str(td_path))
    tier_dispatcher = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier_dispatcher_orchestration"] = tier_dispatcher
    spec.loader.exec_module(tier_dispatcher)

    domain = base.parent / "domain-lib"

    or_path = domain / "orchestration_result.py"
    spec = importlib.util.spec_from_file_location("coding_agent_orchestration_result", str(or_path))
    orchestration_result = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_orchestration_result"] = orchestration_result
    spec.loader.exec_module(orchestration_result)

    rs_path = domain / "tier3_ready_scheduler.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier3_ready_scheduler_orchestration", str(rs_path))
    tier3_ready_scheduler = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier3_ready_scheduler_orchestration"] = tier3_ready_scheduler
    spec.loader.exec_module(tier3_ready_scheduler)

    tc_path = domain / "tier_contracts.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier_contracts_orchestration", str(tc_path))
    tier_contracts = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier_contracts_orchestration"] = tier_contracts
    spec.loader.exec_module(tier_contracts)

    tb_path = domain / "turn_budget.py"
    spec = importlib.util.spec_from_file_location("coding_agent_turn_budget", str(tb_path))
    turn_budget = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_turn_budget"] = turn_budget
    spec.loader.exec_module(turn_budget)
    ot_path = domain / "orchestration_telemetry.py"
    spec = importlib.util.spec_from_file_location("coding_agent_orchestration_telemetry", str(ot_path))
    orchestration_telemetry = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_orchestration_telemetry"] = orchestration_telemetry
    spec.loader.exec_module(orchestration_telemetry)
    eh_path = domain / "evidence_harvest.py"
    spec = importlib.util.spec_from_file_location("coding_agent_evidence_harvest", str(eh_path))
    evidence_harvest = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_evidence_harvest"] = evidence_harvest
    spec.loader.exec_module(evidence_harvest)

    td_path = domain / "teardown_coordinator.py"
    spec = importlib.util.spec_from_file_location("coding_agent_teardown_coordinator", str(td_path))
    teardown_coordinator = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_teardown_coordinator"] = teardown_coordinator
    spec.loader.exec_module(teardown_coordinator)


def _to_plan_dag(plan_dag: Dict[str, Any] | Any) -> Any:
    if isinstance(plan_dag, tier_contracts.PlanDAG):
        return plan_dag
    return tier_contracts.PlanDAG.from_dict(plan_dag if isinstance(plan_dag, dict) else {})


def _to_execution_context(execution_context: Dict[str, Any] | Any) -> Any:
    if isinstance(execution_context, tier_contracts.ExecutionContext):
        return execution_context
    return tier_contracts.ExecutionContext.from_dict(execution_context if isinstance(execution_context, dict) else {})


def _to_task_slices(all_slices: List[Dict[str, Any]] | List[Any]) -> List[Any]:
    normalized: List[Any] = []
    for item in list(all_slices or []):
        if isinstance(item, tier_contracts.TaskSlice):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(tier_contracts.TaskSlice.from_dict(item))
    return normalized


def _extract_token_usage(dispatch_result: Dict[str, Any]) -> int:
    usage = dispatch_result.get("usage") if isinstance(dispatch_result, dict) else None
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if total is not None:
            try:
                return max(0, int(total))
            except Exception:
                return 0
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        try:
            return max(0, int(prompt_tokens or 0) + int(completion_tokens or 0))
        except Exception:
            return 0
    try:
        return max(0, int(dispatch_result.get("tokens_used", 0))) if isinstance(dispatch_result, dict) else 0
    except Exception:
        return 0


def _slice_token_estimate(task_slice: Any) -> int:
    try:
        value = getattr(task_slice, "context_budget_tokens", 0)
    except Exception:
        value = 0
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _compat_halt_reason(halt_reason: str) -> str:
    if halt_reason in {"slice_limit_reached", "token_budget_exhausted", "time_budget_exhausted"}:
        return "budget_exhausted"
    return str(halt_reason)
    return 0


def execute_dag_until(
    plan_dag: Dict[str, Any] | Any,
    execution_context: Dict[str, Any] | Any,
    all_slices: List[Dict[str, Any]] | List[Any],
    turn_budget_value: Dict[str, Any] | Any,
    checkpoint_store: Any | None = None,
    plan_id: str = "default",
) -> Any:
    dag = _to_plan_dag(plan_dag)
    context = _to_execution_context(execution_context)
    slices = _to_task_slices(all_slices)

    if isinstance(turn_budget_value, turn_budget.TurnBudget):
        budget = turn_budget_value
    elif isinstance(turn_budget_value, dict):
        budget = turn_budget.TurnBudget.from_dict(turn_budget_value)
    elif hasattr(turn_budget_value, "to_dict"):
        try:
            budget = turn_budget.TurnBudget.from_dict(turn_budget_value.to_dict())
        except Exception:
            budget = turn_budget.TurnBudget.from_params({})
    elif turn_budget_value is not None and hasattr(turn_budget_value, "max_slices_per_turn"):
        budget = turn_budget.TurnBudget.from_dict(
            {
                "max_tokens": getattr(turn_budget_value, "max_tokens", 0),
                "max_time_seconds": getattr(turn_budget_value, "max_time_seconds", 0.0),
                "max_slices_per_turn": getattr(turn_budget_value, "max_slices_per_turn", 1),
                "started_at_epoch": getattr(turn_budget_value, "started_at_epoch", 0.0),
                "consumed_tokens": getattr(turn_budget_value, "consumed_tokens", 0),
                "executed_slices": getattr(turn_budget_value, "executed_slices", 0),
            }
        )
    else:
        budget = turn_budget.TurnBudget.from_params({})

    executed_slice_ids: List[str] = []
    evidence_timeline: List[Dict[str, Any]] = []
    evidence_commit_obj = None
    teardown_result_obj = None
    failed_node_id: str | None = None
    halt_reason: str | None = None
    telemetry_events: List[Dict[str, Any]] = []

    # Emit start telemetry
    try:
        start_event = orchestration_telemetry.TelemetryEvent(
            event_type="orchestration_start",
            payload={
                "plan_id": str(plan_id or "default"),
                "ready_count": len(tier3_ready_scheduler.next_ready_slices(dag, slices, context)),
                "budget": budget.to_dict(),
            },
        )
        telemetry_events.append(start_event.to_dict())
    except Exception:
        pass

    while True:
        if not budget.can_execute_slice():
            halt_reason = turn_budget.budget_exhaustion_reason(budget)
            break

        ready = tier3_ready_scheduler.next_ready_slices(dag, slices, context)
        if not ready:
            all_nodes = {node.node_id for node in dag.nodes}
            completed = set(context.completed_node_ids or [])
            if all_nodes and all_nodes.issubset(completed):
                halt_reason = "all_completed"
            elif context.failed_node_ids:
                halt_reason = "permanent_failure"
                failed_node_id = str(context.failed_node_ids[-1])
            else:
                halt_reason = "no_ready_slices"
            break

        current = ready[0]
        estimated_slice_tokens = _slice_token_estimate(current)
        if not budget.can_execute_slice(next_slice_tokens=estimated_slice_tokens):
            halt_reason = turn_budget.budget_exhaustion_reason(budget, next_slice_tokens=estimated_slice_tokens)
            break

        payload = current.to_dict()
        payload["plan"] = dag.to_dict()
        payload["execution_context"] = context.to_dict()

        dispatch_result = tier_dispatcher.dispatch_to_tier_with_state(
            3,
            payload,
            execution_context=context.to_dict(),
        )
        context = _to_execution_context(dispatch_result.get("execution_context") or context.to_dict())

        executed_slice_ids.append(str(current.slice_id))
        tier3_evidence = dispatch_result.get("tier3_evidence") if isinstance(dispatch_result, dict) else None
        if not isinstance(tier3_evidence, dict):
            tier3_evidence = {}
        evidence_timeline.append(
            {
                "slice_id": str(current.slice_id),
                "node_id": str(current.node_id),
                "reason": str(dispatch_result.get("reason", "")) if isinstance(dispatch_result, dict) else "",
                "dispatched": bool(dispatch_result.get("dispatched", False)) if isinstance(dispatch_result, dict) else False,
                "status": str(tier3_evidence.get("status", "")),
                "tier3_evidence": dict(tier3_evidence),
            }
        )
        # Trigger minimal evidence harvest and teardown when a slice reports a registered/tests_passed status
        try:
            status = str(tier3_evidence.get("status", ""))
            if status in ("registered", "tests_passed", "committed"):
                slice_ctx = {
                    "slice_id": str(current.slice_id),
                    "node_id": str(current.node_id),
                    "artifacts": dispatch_result.get("artifacts") if isinstance(dispatch_result, dict) else {},
                    "tests": dispatch_result.get("tests") if isinstance(dispatch_result, dict) else {},
                    "checksums": dispatch_result.get("checksums") if isinstance(dispatch_result, dict) else {},
                    "temp_paths": dispatch_result.get("temp_paths") if isinstance(dispatch_result, dict) else [],
                }
                try:
                    evidence_commit_obj = evidence_harvest.build_evidence_from_orchestration(plan_id, slice_ctx)
                except Exception:
                    evidence_commit_obj = None
                try:
                    teardown_result_obj = teardown_coordinator.execute_teardown(plan_id, slice_ctx)
                except Exception:
                    teardown_result_obj = None
        except Exception:
            pass
        # per-slice telemetry
        try:
            slice_event = orchestration_telemetry.TelemetryEvent(
                event_type="slice_executed",
                payload={
                    "slice_id": str(current.slice_id),
                    "node_id": str(current.node_id),
                    "status": str(tier3_evidence.get("status", "")),
                    "attempt_count": int(tier3_evidence.get("attempt_count", 0) or 0),
                    "tokens": int(_extract_token_usage(dispatch_result) or 0),
                    "reason": str(dispatch_result.get("reason", "")) if isinstance(dispatch_result, dict) else "",
                },
            )
            telemetry_events.append(slice_event.to_dict())
        except Exception:
            pass

        if checkpoint_store is not None:
            try:
                checkpoint_store.save_checkpoint(str(plan_id or "default"), context.to_dict(), source="orchestration_loop")
            except Exception as exc:
                halt_reason = "checkpoint_persist_failed"
                evidence_timeline.append(
                    {
                        "slice_id": str(current.slice_id),
                        "node_id": str(current.node_id),
                        "reason": "checkpoint_persist_failed",
                        "dispatched": False,
                        "status": "failed",
                        "tier3_evidence": {
                            "error_class": "checkpoint_persist_failed",
                            "error_message": str(exc),
                        },
                    }
                )
                break

        token_usage = _extract_token_usage(dispatch_result if isinstance(dispatch_result, dict) else {})
        budget.record_slice(token_usage if token_usage > 0 else estimated_slice_tokens)

        status = str(tier3_evidence.get("status", ""))
        if status == "failed" or (
            isinstance(dispatch_result, dict)
            and dispatch_result.get("reason") == "tier3_execution_failed"
            and not bool(dispatch_result.get("retryable", False))
        ):
            failed_node_id = str(current.node_id)
            halt_reason = "permanent_failure"
            break

        if status == "retry_scheduled" or (
            isinstance(dispatch_result, dict) and dispatch_result.get("reason") == "retry_scheduled"
        ):
            halt_reason = "retry_scheduled"
            break

    all_nodes = {node.node_id for node in dag.nodes}
    completed = set(context.completed_node_ids or [])
    if all_nodes and all_nodes.issubset(completed):
        if halt_reason in {None, "no_ready_slices", "slice_limit_reached", "token_budget_exhausted", "time_budget_exhausted", "budget_available"}:
            halt_reason = "all_completed"

    if halt_reason is None:
        halt_reason = turn_budget.budget_exhaustion_reason(budget)

    # emit halt telemetry and summary
    try:
        halt_event = orchestration_telemetry.TelemetryEvent(
            event_type="orchestration_halt",
            payload={
                "plan_id": str(plan_id or "default"),
                "halt_reason": str(halt_reason),
                "halt_reason_compat": _compat_halt_reason(str(halt_reason)),
                "executed": executed_slice_ids,
                "completed_nodes": list(context.completed_node_ids or []),
                "failed_node_id": failed_node_id,
            },
        )
        telemetry_events.append(halt_event.to_dict())
    except Exception:
        pass

    try:
        summary = orchestration_telemetry.OrchestrationTurnSummary(
            plan_id=str(plan_id or "default"),
            executed_slices=executed_slice_ids,
            halt_reason=str(halt_reason),
            halt_reason_compat=_compat_halt_reason(str(halt_reason)),
            budget_snapshot=budget.to_dict(),
            evidence_summary=evidence_timeline,
        )
        telemetry_summary = summary.to_dict()
    except Exception:
        telemetry_summary = {}

    return orchestration_result.OrchestrationResult(
        executed_slice_ids=executed_slice_ids,
        completed_node_ids=list(context.completed_node_ids or []),
        failed_node_id=failed_node_id,
        halt_reason=str(halt_reason),
        halt_reason_compat=_compat_halt_reason(str(halt_reason)),
        evidence_timeline=evidence_timeline,
        execution_context=context.to_dict(),
        budget=budget.to_dict(),
        telemetry={"events": telemetry_events, "summary": telemetry_summary},
        evidence_commit=(evidence_commit_obj.to_dict() if hasattr(evidence_commit_obj, "to_dict") else None) if evidence_commit_obj is not None else None,
        teardown_result=(teardown_result_obj.to_dict() if hasattr(teardown_result_obj, "to_dict") else None) if teardown_result_obj is not None else None,
    )
