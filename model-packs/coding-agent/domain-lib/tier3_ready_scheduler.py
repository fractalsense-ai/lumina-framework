from __future__ import annotations

from typing import List

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from . import dag_validator, tier_contracts
except Exception:
    import importlib.util
    import pathlib
    import sys

    base = pathlib.Path(__file__).parent

    dv_path = base / "dag_validator.py"
    spec = importlib.util.spec_from_file_location("coding_agent_dag_validator", str(dv_path))
    dag_validator = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_dag_validator"] = dag_validator
    spec.loader.exec_module(dag_validator)

    tc_path = base / "tier_contracts.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier_contracts", str(tc_path))
    tier_contracts = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier_contracts"] = tier_contracts
    spec.loader.exec_module(tier_contracts)


PlanDAG = tier_contracts.PlanDAG
TaskSlice = tier_contracts.TaskSlice
ExecutionContext = tier_contracts.ExecutionContext


def is_node_ready(node_id: str, dag: PlanDAG, execution_context: ExecutionContext) -> bool:
    completed = set(execution_context.completed_node_ids or [])
    ready = dag_validator.ready_node_ids(dag, completed)
    return node_id in ready


def validate_slice_ready(task_slice: TaskSlice, dag: PlanDAG, execution_context: ExecutionContext) -> List[str]:
    errors: List[str] = []
    node_ids = {n.node_id for n in dag.nodes}

    if task_slice.node_id not in node_ids:
        errors.append(f"unknown_slice_node: {task_slice.node_id}")
        return errors

    if task_slice.node_id in set(execution_context.completed_node_ids or []):
        errors.append(f"already_completed: {task_slice.node_id}")

    if task_slice.node_id in set(execution_context.failed_node_ids or []):
        errors.append(f"failed_node_blocked: {task_slice.node_id}")

    if not is_node_ready(task_slice.node_id, dag, execution_context):
        completed = set(execution_context.completed_node_ids or [])
        for dep in task_slice.depends_on or []:
            if dep not in completed:
                errors.append(f"dependency_not_ready: {task_slice.node_id} -> {dep}")

    return errors


def next_ready_slices(
    dag: PlanDAG,
    slices: List[TaskSlice],
    execution_context: ExecutionContext,
) -> List[TaskSlice]:
    completed = set(execution_context.completed_node_ids or [])
    failed = set(execution_context.failed_node_ids or [])
    ready_ids = set(dag_validator.ready_node_ids(dag, completed))

    ordered = []
    slice_by_node = {s.node_id: s for s in slices}
    for node in dag_validator.stable_topological_sort(dag):
        node_id = node.node_id
        if node_id in completed or node_id in failed:
            continue
        if node_id not in ready_ids:
            continue
        if node_id in slice_by_node:
            ordered.append(slice_by_node[node_id])

    return ordered
