from __future__ import annotations

from typing import Dict, Any, List, Tuple
from datetime import datetime

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


def decompose_job(job: Dict[str, Any]) -> Tuple[tier_contracts.PlanDAG, Dict[str, List[str]]]:
    """Produce a PlanDAG and a mapping of node_id -> allowed_tools.

    Accepts either a dict-shaped job or a CodingAgentJob-like object with
    a `task_graph` attribute containing TaskNode-shaped dicts/objects.
    Returns (PlanDAG, node_tools_map).
    """
    task_graph = job.get("task_graph") if isinstance(job, dict) else getattr(job, "task_graph", None)
    # Guard: explicit error when task_graph present but malformed
    if task_graph is not None and not isinstance(task_graph, (list, tuple)):
        raise TypeError("task_graph must be a list of task nodes")
    nodes: List[tier_contracts.PlanNode] = []
    node_tools: Dict[str, List[str]] = {}

    if not task_graph:
        # fallback: single node representing the whole job
        node_id = (job.get("job_id") if isinstance(job, dict) else getattr(job, "job_id", "root"))
        desc = (job.get("summary") if isinstance(job, dict) else getattr(job, "summary", "job"))
        pn = tier_contracts.PlanNode(node_id=str(node_id), description=str(desc), depends_on=[], tier_hint=2)
        nodes.append(pn)
        node_tools[pn.node_id] = list(job.get("validation_commands") or [])
    else:
        for item in task_graph:
            # item may be dict or dataclass-like
            nid = item.get("task_id") if isinstance(item, dict) else getattr(item, "task_id")
            desc = item.get("task_type") if isinstance(item, dict) else getattr(item, "task_type")
            blocked = item.get("blocked_by") if isinstance(item, dict) else getattr(item, "blocked_by", ())
            tier_hint = int(item.get("tier", 2) if isinstance(item, dict) else getattr(item, "tier", 2))
            pn = tier_contracts.PlanNode(node_id=str(nid), description=str(desc or ""), depends_on=list(blocked or []), tier_hint=tier_hint)
            nodes.append(pn)
            allowed = item.get("allowed_tools") if isinstance(item, dict) else list(getattr(item, "allowed_tools", ()))
            node_tools[pn.node_id] = list(allowed or [])

    dag = tier_contracts.PlanDAG(nodes=nodes, created_at=datetime.utcnow().isoformat() + "Z")
    return dag, node_tools


def topological_sort(dag: tier_contracts.PlanDAG) -> List[tier_contracts.PlanNode]:
    """Return PlanNodes in topologically-sorted order. Raises ValueError on cycle."""
    nodes = {n.node_id: n for n in dag.nodes}
    indeg: Dict[str, int] = {nid: 0 for nid in nodes}
    adj: Dict[str, List[str]] = {nid: [] for nid in nodes}

    for n in dag.nodes:
        for dep in n.depends_on or []:
            if dep in nodes:
                indeg[n.node_id] += 1
                adj[dep].append(n.node_id)

    queue = [nid for nid, d in indeg.items() if d == 0]
    order: List[tier_contracts.PlanNode] = []

    while queue:
        cur = queue.pop(0)
        order.append(nodes[cur])
        for nb in adj.get(cur, []):
            indeg[nb] -= 1
            if indeg[nb] == 0:
                queue.append(nb)

    if len(order) != len(nodes):
        raise ValueError("cycle detected in PlanDAG")

    return order


def _estimate_tokens_for_node(node: tier_contracts.PlanNode) -> int:
    """Rudimentary token-estimate: base + length-based cost.

    This is intentionally conservative and deterministic so tests remain stable.
    """
    base = 50
    length_cost = max(0, len(node.description or "") // 4)
    return base + length_cost


def group_nodes_into_slices(
    dag: tier_contracts.PlanDAG, node_tools: Dict[str, List[str]], max_tokens_per_slice: int = 1024
) -> List[List[tier_contracts.PlanNode]]:
    """Group topologically-ordered PlanNodes into buckets not exceeding token budget.

    Returns list of node lists representing each slice's assignment.
    """
    ordered = topological_sort(dag)
    groups: List[List[tier_contracts.PlanNode]] = []
    cur: List[tier_contracts.PlanNode] = []
    cur_cost = 0

    for n in ordered:
        cost = _estimate_tokens_for_node(n)
        # if single node exceeds budget, place it alone (caller may reject later)
        if not cur:
            cur.append(n)
            cur_cost = cost
            continue

        if cur_cost + cost > max_tokens_per_slice:
            groups.append(cur)
            cur = [n]
            cur_cost = cost
        else:
            cur.append(n)
            cur_cost += cost

    if cur:
        groups.append(cur)

    return groups


def assign_task_slices(
    dag: tier_contracts.PlanDAG,
    node_tools: Dict[str, List[str]],
    allowed_tools: List[str],
    max_tokens_per_slice: int | None = None,
) -> List[tier_contracts.TaskSlice]:
    """Map PlanNodes to TaskSlices. If `max_tokens_per_slice` is set, group nodes.

    Filtering of allowed adapters is applied per-node and per-slice.
    """
    slices: List[tier_contracts.TaskSlice] = []
    allowed_set = set(allowed_tools or [])

    if max_tokens_per_slice:
        groups = group_nodes_into_slices(dag, node_tools, max_tokens_per_slice)
        for idx, group in enumerate(groups):
            # union allowed tools for the group but keep only globally allowed ones
            union_allowed = []
            for n in group:
                for t in node_tools.get(n.node_id, []):
                    if t in allowed_set and t not in union_allowed:
                        union_allowed.append(t)

            ts = tier_contracts.TaskSlice(
                slice_id=f"slice-{idx}",
                node_id=group[0].node_id,
                task_description="; ".join([n.description for n in group]),
                allowed_tools=union_allowed,
                context_budget_tokens=max_tokens_per_slice,
                tier=3,
            )
            slices.append(ts)
        return slices

    # default: one slice per node
    for n in dag.nodes:
        node_allowed = node_tools.get(n.node_id, [])
        filtered = [t for t in node_allowed if t in allowed_set]
        ts = tier_contracts.TaskSlice(
            slice_id=f"{n.node_id}-slice",
            node_id=n.node_id,
            task_description=n.description,
            allowed_tools=filtered,
            context_budget_tokens=1024,
            tier=3,
        )
        slices.append(ts)
    return slices
