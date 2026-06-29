from pathlib import Path
import importlib.util

BASE = Path(__file__).resolve().parents[1] / "model-packs" / "coding-agent" / "domain-lib"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_grouping_respects_token_budget():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    nodes = [
        tier_contracts.PlanNode(node_id=f"N{i}", description=("x" * (i * 10)), depends_on=[]) for i in range(1, 8)
    ]
    dag = tier_contracts.PlanDAG(nodes=nodes, created_at="now")
    node_tools = {n.node_id: ["adapter/ca/read-file/v1"] for n in nodes}

    groups = dec.group_nodes_into_slices(dag, node_tools, max_tokens_per_slice=120)
    # with small budget, there should be multiple groups
    assert len(groups) > 1
    # Flatten nodes and ensure count preserved
    flat = [n for g in groups for n in g]
    assert [n.node_id for n in flat] == [n.node_id for n in nodes]


def test_assign_task_slices_groups_into_slices():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    nodes = [
        tier_contracts.PlanNode(node_id=f"N{i}", description=("y" * (i * 20)), depends_on=[]) for i in range(1, 6)
    ]
    dag = tier_contracts.PlanDAG(nodes=nodes, created_at="now")
    node_tools = {n.node_id: ["adapter/ca/read-file/v1", "adapter/ca/run-tests/v1"] for n in nodes}

    slices = dec.assign_task_slices(dag, node_tools, ["adapter/ca/run-tests/v1"], max_tokens_per_slice=160)
    assert len(slices) >= 1
    for s in slices:
        assert all(t == "adapter/ca/run-tests/v1" for t in s.allowed_tools)


def test_decompose_job_type_errors():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    try:
        dec.decompose_job({"job_id": "bad", "task_graph": "not-a-list"})
        raised = False
    except TypeError:
        raised = True
    assert raised


def test_priority_reduces_estimated_cost():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    n_low = tier_contracts.PlanNode(node_id="L", description="short desc", depends_on=[])
    n_low.tier_hint = 1
    n_high = tier_contracts.PlanNode(node_id="H", description="short desc", depends_on=[])
    n_high.tier_hint = 4

    c_low = dec._estimate_tokens_for_node(n_low)
    c_high = dec._estimate_tokens_for_node(n_high)
    assert c_high <= c_low


def test_missing_allowed_tools_results_empty_allowed():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    nodes = [tier_contracts.PlanNode(node_id="A", description="d", depends_on=[])]
    dag = tier_contracts.PlanDAG(nodes=nodes, created_at="now")
    node_tools = {"A": ["adapter/ca/read-file/v1"]}

    slices = dec.assign_task_slices(dag, node_tools, allowed_tools=[])
    assert len(slices) == 1
    assert slices[0].allowed_tools == []


def test_oversized_node_marked_in_description():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    # make a very long description to exceed budget
    long_desc = "x" * 5000
    nodes = [tier_contracts.PlanNode(node_id="BIG", description=long_desc, depends_on=[])]
    dag = tier_contracts.PlanDAG(nodes=nodes, created_at="now")
    node_tools = {"BIG": ["adapter/ca/read-file/v1"]}

    slices = dec.assign_task_slices(dag, node_tools, allowed_tools=["adapter/ca/read-file/v1"], max_tokens_per_slice=200)
    assert len(slices) == 1
    assert "OVERSIZED" in slices[0].task_description


def test_dependency_aware_cost_reduction():
    dec = _load("tier2_decomposer", BASE / "tier2_decomposer.py")
    from model_packs.coding_agent.domain_lib import tier_contracts

    # A is a root with many dependents; B is a leaf
    A = tier_contracts.PlanNode(node_id="A", description="root", depends_on=[])
    B = tier_contracts.PlanNode(node_id="B", description="leaf", depends_on=["A"])
    C = tier_contracts.PlanNode(node_id="C", description="leaf2", depends_on=["A"])
    D = tier_contracts.PlanNode(node_id="D", description="leaf3", depends_on=["A"])

    dag = tier_contracts.PlanDAG(nodes=[A, B, C, D], created_at="now")
    node_tools = {n.node_id: [] for n in [A, B, C, D]}

    groups = dec.group_nodes_into_slices(dag, node_tools, max_tokens_per_slice=1024)
    # estimator should have attached dependents map
    cost_A = dec._estimate_tokens_for_node(A)
    cost_B = dec._estimate_tokens_for_node(B)
    assert cost_A <= cost_B
