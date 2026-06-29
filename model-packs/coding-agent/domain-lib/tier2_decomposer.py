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
    """Token estimate improved with length, priority, tool-costs, and dependency awareness.

    Parameters are intentionally deterministic so tests remain stable. The
    function accepts optional context via `node_tools` and `dag` when callers
    have that information; otherwise falls back to conservative defaults.
    """
    import math

    def _tool_weight(toolid: str) -> int:
        # lightweight cost model for adapters; defaults to 20 for unknown adapters
        weights = {
            "adapter/ca/run-tests/v1": 60,
            "adapter/ca/read-file/v1": 10,
            "adapter/ca/write-file/v1": 20,
            "adapter/ca/stage-patch/v1": 40,
        }
        return weights.get(toolid, 20)

    base = 40
    length_cost = max(0, len(node.description or "") // 6)

    # priority adjustment: higher tier_hint reduces effective cost
    tier_hint = getattr(node, "tier_hint", 2) if hasattr(node, "tier_hint") else 2
    priority_adjust = int(tier_hint) * 6

    # default tool cost is zero unless node_tools and dag are provided by caller
    tool_cost = 0
    dep_adjust = 0
    try:
        # node_tools and dag may be attached to the node for callers that pass them
        node_tools = getattr(node, "_node_tools", None)
    except Exception:
        node_tools = None

    if node_tools and isinstance(node_tools, dict):
        for t in node_tools.get(node.node_id, []):
            tool_cost += _tool_weight(t)

    # dependency awareness: prefer nodes with many downstream dependents (lower cost)
    if hasattr(node, "_dependents_map") and isinstance(node._dependents_map, dict):
        dep_count = node._dependents_map.get(node.node_id, 0)
        dep_adjust = int(math.log1p(dep_count + 1) * 4)

    effective = base + length_cost + tool_cost - priority_adjust - dep_adjust
    return max(8, int(effective))
    return base + length_cost


def group_nodes_into_slices(
    dag: tier_contracts.PlanDAG, node_tools: Dict[str, List[str]], max_tokens_per_slice: int = 1024
) -> List[List[tier_contracts.PlanNode]]:
    """Group topologically-ordered PlanNodes into buckets not exceeding token budget.

    Returns list of node lists representing each slice's assignment.
    """
    ordered = topological_sort(dag)
    # precompute dependents map and attach to nodes for _estimate_tokens_for_node
    dependents_map: Dict[str, int] = _count_dependents(dag)
    for n in ordered:
        # attach node_tools map and dependents map for richer estimates
        setattr(n, "_node_tools", node_tools)
        setattr(n, "_dependents_map", dependents_map)
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


def _count_dependents(dag: tier_contracts.PlanDAG) -> Dict[str, int]:
    """Return a map node_id -> count of downstream dependents (transitive).

    This is a simple BFS per node; DAGs are expected to be small so O(N^2)
    worst-case is acceptable and keeps implementation straightforward.
    """
    graph = {n.node_id: list(n.depends_on or []) for n in dag.nodes}
    # build forward adjacency (node -> children)
    children: Dict[str, List[str]] = {n.node_id: [] for n in dag.nodes}
    for nid, deps in graph.items():
        for d in deps:
            children.setdefault(d, []).append(nid)

    result: Dict[str, int] = {}
    for n in dag.nodes:
        seen = set()
        stack = list(children.get(n.node_id, []))
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            for ch in children.get(c, []):
                if ch not in seen:
                    stack.append(ch)
        result[n.node_id] = len(seen)
    return result


def assign_task_slices(
    dag: tier_contracts.PlanDAG,
    node_tools: Dict[str, List[str]],
    allowed_tools: List[str],
    max_tokens_per_slice: int | None = None,
    model_class_map: Dict[str, str] | None = None,
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

            # mark oversized nodes in the description so callers can surface warnings
            oversized = any(_estimate_tokens_for_node(n) > max_tokens_per_slice for n in group)
            desc = "; ".join([n.description for n in group])
            if oversized:
                desc = desc + " [OVERSIZED]"

            # determine model class for this slice: if any node requests 'slm', prefer that
            model_classes = {model_class_map.get(n.node_id, "llm") if model_class_map else "llm" for n in group}
            if "slm" in model_classes:
                slice_model = "slm"
            else:
                # default to the first model in the set (stable ordering)
                slice_model = sorted(list(model_classes))[0]

            ts = tier_contracts.TaskSlice(
                slice_id=f"slice-{idx}",
                node_id=group[0].node_id,
                task_description=desc,
                allowed_tools=union_allowed,
                context_budget_tokens=max_tokens_per_slice,
                tier=3,
                model_class=slice_model,
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
            model_class=(model_class_map.get(n.node_id) if model_class_map else "llm"),
        )
        slices.append(ts)
    return slices
