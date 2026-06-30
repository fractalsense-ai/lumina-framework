from __future__ import annotations

from typing import Any, Dict, List

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from . import tier_dispatcher
    from ..domain_lib import orchestration_result, tier3_ready_scheduler, tier_contracts, turn_budget
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
    failed_node_id: str | None = None
    halt_reason = "budget_exhausted"

    while budget.can_execute_slice():
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
        evidence_timeline.append(
            {
                "slice_id": str(current.slice_id),
                "node_id": str(current.node_id),
                "reason": str(dispatch_result.get("reason", "")) if isinstance(dispatch_result, dict) else "",
                "dispatched": bool(dispatch_result.get("dispatched", False)) if isinstance(dispatch_result, dict) else False,
                "status": str((tier3_evidence or {}).get("status", "")) if isinstance(tier3_evidence, dict) else "",
            }
        )

        if checkpoint_store is not None:
            try:
                checkpoint_store.save_checkpoint(str(plan_id or "default"), context.to_dict(), source="orchestration_loop")
            except Exception:
                pass

        budget.record_slice(_extract_token_usage(dispatch_result if isinstance(dispatch_result, dict) else {}))

        status = str((tier3_evidence or {}).get("status", "")) if isinstance(tier3_evidence, dict) else ""
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
    else:
        all_nodes = {node.node_id for node in dag.nodes}
        completed = set(context.completed_node_ids or [])
        if all_nodes and all_nodes.issubset(completed):
            halt_reason = "all_completed"
        else:
            halt_reason = turn_budget.budget_exhaustion_reason(budget)

    if not budget.can_execute_slice() and halt_reason not in {"all_completed", "permanent_failure", "retry_scheduled", "no_ready_slices"}:
        all_nodes = {node.node_id for node in dag.nodes}
        completed = set(context.completed_node_ids or [])
        if all_nodes and all_nodes.issubset(completed):
            halt_reason = "all_completed"
        else:
            halt_reason = turn_budget.budget_exhaustion_reason(budget)

    return orchestration_result.OrchestrationResult(
        executed_slice_ids=executed_slice_ids,
        completed_node_ids=list(context.completed_node_ids or []),
        failed_node_id=failed_node_id,
        halt_reason=halt_reason,
        evidence_timeline=evidence_timeline,
        execution_context=context.to_dict(),
        budget=budget.to_dict(),
    )
