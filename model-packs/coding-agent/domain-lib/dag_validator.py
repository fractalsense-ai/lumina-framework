from __future__ import annotations

from typing import List

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

    # Simple cycle check via attempt to topologically sort
    try:
        from . import tier2_decomposer

        tier2_decomposer.topological_sort(dag)
    except Exception as exc:
        errors.append(f"cycle_or_sort_error: {exc}")

    return errors
