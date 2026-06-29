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


def assign_task_slices(dag: tier_contracts.PlanDAG, node_tools: Dict[str, List[str]], allowed_tools: List[str]) -> List[tier_contracts.TaskSlice]:
    """Map PlanNodes to TaskSlices filtering allowed_tools by global allowed_tools list."""
    slices: List[tier_contracts.TaskSlice] = []
    allowed_set = set(allowed_tools or [])
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
