from __future__ import annotations

from typing import List

from . import tier_contracts


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

    # Simple cycle check via attempt to topologically sort
    try:
        from . import tier2_decomposer

        tier2_decomposer.topological_sort(dag)
    except Exception as exc:
        errors.append(f"cycle_or_sort_error: {exc}")

    return errors
