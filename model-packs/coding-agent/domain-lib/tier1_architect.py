from __future__ import annotations

from typing import Dict

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from .tier_contracts import PlanDAG, PlanNode
except Exception:
    import importlib.util
    import pathlib
    import sys

    base = pathlib.Path(__file__).parent
    tc_path = base / "tier_contracts.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier_contracts", str(tc_path))
    tier_contracts = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier_contracts"] = tier_contracts
    spec.loader.exec_module(tier_contracts)

    PlanDAG = tier_contracts.PlanDAG
    PlanNode = tier_contracts.PlanNode


def _is_documentation_node(node: PlanNode) -> bool:
    desc = (node.description or "").lower()
    nid = (node.node_id or "").lower()
    keywords = ["doc", "docs", "documentation", "readme", "manpage", "spec", "guide"]
    for k in keywords:
        if k in desc or k in nid:
            return True
    return False


def classify_nodes(dag: PlanDAG) -> PlanDAG:
    """Return a new PlanDAG where nodes have `action_type` set deterministically.

    Heuristic (conservative): if the node id or description mentions documentation
    keywords, set action_type to 'document', otherwise 'code'.
    """
    classified = []
    for n in dag.nodes:
        try:
            action = "document" if _is_documentation_node(n) else (n.action_type or "code")
        except Exception:
            action = "code"
        new_node = PlanNode(
            node_id=n.node_id,
            description=n.description,
            depends_on=list(n.depends_on or []),
            tier_hint=int(n.tier_hint or 2),
            action_type=action,
        )
        classified.append(new_node)
    return PlanDAG(nodes=classified, created_at=dag.created_at)


def build_model_class_map(dag: PlanDAG) -> Dict[str, str]:
    """Return a mapping node_id -> model_class (e.g. 'slm' or 'llm').

    Rules:
    - documentation nodes use 'slm'
    - all others use 'llm'
    """
    mapping: Dict[str, str] = {}
    for n in dag.nodes:
        mapping[n.node_id] = "slm" if (n.action_type == "document") else "llm"
    return mapping
