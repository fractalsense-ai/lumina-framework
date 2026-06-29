from pathlib import Path
import importlib.util
import sys

BASE = Path(__file__).resolve().parents[1] / "model-packs" / "coding-agent" / "domain-lib"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_decompose_job_no_task_graph():
    decomposer = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    job = {"job_id": "j1", "summary": "Do work", "validation_commands": ["adapter/ca/run-tests/v1"]}
    dag, node_tools = decomposer.decompose_job(job)
    assert len(dag.nodes) == 1
    assert list(node_tools.keys())[0] == dag.nodes[0].node_id


def test_decompose_job_with_task_graph():
    decomposer = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    job = {
        "job_id": "j2",
        "summary": "Multi",
        "task_graph": [
            {"task_id": "A", "task_type": "read", "tier": 3, "allowed_tools": ["adapter/ca/read-file/v1"], "blocked_by": []},
            {"task_id": "B", "task_type": "tests", "tier": 3, "allowed_tools": ["adapter/ca/run-tests/v1"], "blocked_by": ["A"]},
            {"task_id": "C", "task_type": "stage", "tier": 3, "allowed_tools": ["adapter/ca/stage-patch/v1"], "blocked_by": ["B"]},
        ],
    }
    dag, node_tools = decomposer.decompose_job(job)
    assert len(dag.nodes) == 3
    ids = {n.node_id for n in dag.nodes}
    assert ids == {"A", "B", "C"}
    assert node_tools["B"] == ["adapter/ca/run-tests/v1"]


def test_topological_sort_linear_chain():
    decomposer = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    job = {
        "job_id": "j3",
        "task_graph": [
            {"task_id": "A", "task_type": "a", "blocked_by": []},
            {"task_id": "B", "task_type": "b", "blocked_by": ["A"]},
            {"task_id": "C", "task_type": "c", "blocked_by": ["B"]},
        ],
    }
    dag, node_tools = decomposer.decompose_job(job)
    order = decomposer.topological_sort(dag)
    assert [n.node_id for n in order] == ["A", "B", "C"]


def test_topological_sort_cycle_raises():
    from model_packs.coding_agent.domain_lib import tier_contracts
    from model_packs.coding_agent.domain_lib.tier2_decomposer import topological_sort

    n1 = tier_contracts.PlanNode(node_id="A", description="", depends_on=["B"])
    n2 = tier_contracts.PlanNode(node_id="B", description="", depends_on=["A"])
    dag = tier_contracts.PlanDAG(nodes=[n1, n2], created_at="now")

    try:
        topological_sort(dag)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_assign_task_slices_filters_tools():
    decomposer = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    n = tier_contracts.PlanNode(node_id="X", description="x", depends_on=[])
    dag = tier_contracts.PlanDAG(nodes=[n], created_at="now")
    node_tools = {"X": ["adapter/ca/read-file/v1", "adapter/ca/run-tests/v1"]}
    slices = decomposer.assign_task_slices(dag, node_tools, ["adapter/ca/run-tests/v1"]) 
    assert len(slices) == 1
    assert slices[0].allowed_tools == ["adapter/ca/run-tests/v1"]


def test_validate_dag_duplicate_node_ids():
    validator = _load("dag_validator", BASE / "dag_validator.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    n1 = tier_contracts.PlanNode(node_id="A", description="", depends_on=[])
    n2 = tier_contracts.PlanNode(node_id="A", description="dup", depends_on=[])
    dag = tier_contracts.PlanDAG(nodes=[n1, n2], created_at="now")
    errors = validator.validate_dag(dag)
    assert any("duplicate_node_id" in e for e in errors)


def test_validate_dag_dangling_depends_on():
    validator = _load("dag_validator", BASE / "dag_validator.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    n1 = tier_contracts.PlanNode(node_id="A", description="", depends_on=["MISSING"])
    dag = tier_contracts.PlanDAG(nodes=[n1], created_at="now")
    errors = validator.validate_dag(dag)
    assert any("dangling_depends_on" in e for e in errors)
