from __future__ import annotations

from typing import Dict, List, Set

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from . import tier_contracts
except Exception:
    import importlib.util
    import pathlib
    import sys

    base = pathlib.Path(__file__).parent
    tc_path = base / "tier_contracts.py"
    if not tc_path.exists():
        tc_path = base.parent / "domain-lib" / "tier_contracts.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier_contracts", str(tc_path))
    tier_contracts = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier_contracts"] = tier_contracts
    spec.loader.exec_module(tier_contracts)


def validate_dag(dag: tier_contracts.PlanDAG) -> List[str]:
    """Return list of validation error messages for the PlanDAG."""
    errors: List[str] = []
    ids = [n.node_id for n in dag.nodes]
    seen = set()
    for nid in ids:
        if nid in seen:
            errors.append(f"duplicate_node_id: {nid}")
        seen.add(nid)

    node_set = set(ids)
    for n in dag.nodes:
        for dep in n.depends_on or []:
            if dep not in node_set:
                errors.append(f"dangling_depends_on: {n.node_id} -> {dep}")

    try:
        stable_topological_sort(dag)
    except Exception as exc:
        errors.append(f"cycle_or_sort_error: {exc}")

    return errors


def stable_topological_sort(dag: tier_contracts.PlanDAG) -> List[tier_contracts.PlanNode]:
    """Return a deterministic topological order for a valid DAG.

    Ready nodes are ordered by node_id so equal-priority plans produce stable
    output across Python versions and environments.
    """
    nodes = {n.node_id: n for n in dag.nodes}
    indeg: Dict[str, int] = {nid: 0 for nid in nodes}
    adj: Dict[str, List[str]] = {nid: [] for nid in nodes}

    for n in dag.nodes:
        for dep in n.depends_on or []:
            if dep in nodes:
                indeg[n.node_id] += 1
                adj[dep].append(n.node_id)

    ready = sorted([nid for nid, degree in indeg.items() if degree == 0])
    ordered: List[tier_contracts.PlanNode] = []
    while ready:
        cur = ready.pop(0)
        ordered.append(nodes[cur])
        for child in sorted(adj.get(cur, [])):
            indeg[child] -= 1
            if indeg[child] == 0:
                ready.append(child)
        ready.sort()

    if len(ordered) != len(nodes):
        raise ValueError("cycle detected in PlanDAG")
    return ordered


def ready_node_ids(dag: tier_contracts.PlanDAG, completed_node_ids: Set[str] | List[str]) -> List[str]:
    """Return executable node ids whose dependencies are all completed."""
    completed = set(completed_node_ids or [])
    ordered = stable_topological_sort(dag)
    ready: List[str] = []
    for n in ordered:
        if n.node_id in completed:
            continue
        if all(dep in completed for dep in (n.depends_on or [])):
            ready.append(n.node_id)
    return ready


def validate_micro_dag_lineage(
    global_dag: tier_contracts.PlanDAG,
    micro_dag: tier_contracts.PlanDAG,
) -> List[str]:
    """Validate that every micro-DAG node traces to an existing global node."""
    errors: List[str] = []
    global_ids = {n.node_id for n in global_dag.nodes}
    for n in micro_dag.nodes:
        parent = getattr(n, "parent_node_id", "") or n.node_id
        if parent not in global_ids:
            errors.append(f"missing_global_parent: {n.node_id} -> {parent}")
    return errors


def validate_task_slice_lineage(
    dag: tier_contracts.PlanDAG,
    slices: List[tier_contracts.TaskSlice],
) -> List[str]:
    """Validate that TaskSlices preserve a valid node/global parent reference."""
    errors: List[str] = []
    node_ids = {n.node_id for n in dag.nodes}
    for ts in slices:
        parent = getattr(ts, "parent_node_id", "") or ts.node_id
        if parent not in node_ids:
            errors.append(f"slice_missing_parent: {ts.slice_id} -> {parent}")
        for dep in getattr(ts, "depends_on", []) or []:
            if dep not in node_ids:
                errors.append(f"slice_dangling_depends_on: {ts.slice_id} -> {dep}")
    return errors
