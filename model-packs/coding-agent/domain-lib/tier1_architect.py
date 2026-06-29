from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from .tier_contracts import ArchitectPlan, PlanDAG, PlanNode
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
    ArchitectPlan = tier_contracts.ArchitectPlan


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


def architect_global_plan(job: Dict[str, Any], system_state_refs: List[str] | None = None) -> ArchitectPlan:
    """Build a deterministic global architect plan for a coding-agent job.

    This is intentionally model-free: Tier 1 establishes a validated global DAG
    and tier assignments so downstream tiers can slice and execute only valid,
    dependency-aware work.
    """
    try:
        from . import tier2_decomposer, dag_validator
    except Exception:
        import importlib.util
        import pathlib
        import sys

        base = pathlib.Path(__file__).parent

        dec_path = base / "tier2_decomposer.py"
        spec = importlib.util.spec_from_file_location("coding_agent_tier2_decomposer", str(dec_path))
        tier2_decomposer = importlib.util.module_from_spec(spec)
        sys.modules["coding_agent_tier2_decomposer"] = tier2_decomposer
        spec.loader.exec_module(tier2_decomposer)

        val_path = base / "dag_validator.py"
        spec = importlib.util.spec_from_file_location("coding_agent_dag_validator", str(val_path))
        dag_validator = importlib.util.module_from_spec(spec)
        sys.modules["coding_agent_dag_validator"] = dag_validator
        spec.loader.exec_module(dag_validator)

    dag, _node_tools = tier2_decomposer.decompose_job(job or {})
    dag = classify_nodes(dag)
    validation_errors = dag_validator.validate_dag(dag)
    root_job_id = str((job or {}).get("job_id") or "root")
    tier_assignments = {n.node_id: int(getattr(n, "tier_hint", 2) or 2) for n in dag.nodes}
    return ArchitectPlan(
        plan_id=f"architect-plan-{root_job_id}",
        root_job_id=root_job_id,
        global_dag=dag,
        system_state_refs=list(system_state_refs or (job or {}).get("system_state_refs") or []),
        tier_assignments=tier_assignments,
        validation_errors=validation_errors,
        created_at=datetime.utcnow().isoformat() + "Z",
    )
