import importlib.util
import pathlib
import sys

base = pathlib.Path(__file__).parent.parent / "model-packs" / "coding-agent"
domain = base / "domain-lib"
controllers = base / "controllers"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dag_validator = _load("coding_agent_dag_validator_slice14", domain / "dag_validator.py")
tier_contracts = dag_validator.tier_contracts
tier1_architect = _load("coding_agent_tier1_architect_slice14", domain / "tier1_architect.py")
tier2_decomposer = _load("coding_agent_tier2_decomposer_slice14", domain / "tier2_decomposer.py")
tier_dispatcher = _load("coding_agent_tier_dispatcher_slice14", controllers / "tier_dispatcher.py")


def _dag(nodes):
    return tier_contracts.PlanDAG(nodes=nodes, created_at="now")


def test_validate_dag_rejects_duplicate_ids():
    dag = _dag([
        tier_contracts.PlanNode("a", "first", []),
        tier_contracts.PlanNode("a", "second", []),
    ])

    errors = dag_validator.validate_dag(dag)

    assert "duplicate_node_id: a" in errors


def test_validate_dag_rejects_dangling_dependency():
    dag = _dag([tier_contracts.PlanNode("a", "needs missing", ["missing"])])

    errors = dag_validator.validate_dag(dag)

    assert "dangling_depends_on: a -> missing" in errors


def test_validate_dag_rejects_cycle():
    dag = _dag([
        tier_contracts.PlanNode("a", "first", ["b"]),
        tier_contracts.PlanNode("b", "second", ["a"]),
    ])

    errors = dag_validator.validate_dag(dag)

    assert any(e.startswith("cycle_or_sort_error:") for e in errors)


def test_stable_topological_sort_orders_equal_ready_nodes_by_id():
    dag = _dag([
        tier_contracts.PlanNode("b", "second ready", []),
        tier_contracts.PlanNode("a", "first ready", []),
        tier_contracts.PlanNode("c", "after both", ["a", "b"]),
    ])

    ordered = [n.node_id for n in dag_validator.stable_topological_sort(dag)]

    assert ordered == ["a", "b", "c"]


def test_ready_node_ids_excludes_incomplete_dependencies():
    dag = _dag([
        tier_contracts.PlanNode("a", "root", []),
        tier_contracts.PlanNode("b", "child", ["a"]),
        tier_contracts.PlanNode("c", "other child", ["a"]),
        tier_contracts.PlanNode("d", "blocked", ["b", "c"]),
    ])

    assert dag_validator.ready_node_ids(dag, []) == ["a"]
    assert dag_validator.ready_node_ids(dag, ["a"]) == ["b", "c"]
    assert dag_validator.ready_node_ids(dag, ["a", "b", "c"]) == ["d"]


def test_architect_plan_serializes_global_dag_and_state_refs():
    job = {
        "job_id": "job-1",
        "system_state_refs": ["state://module/core", "state://manifest/current"],
        "task_graph": [
            {"task_id": "a", "task_type": "write docs", "blocked_by": [], "tier": 2},
            {"task_id": "b", "task_type": "implement code", "blocked_by": ["a"], "tier": 2},
        ],
    }

    plan = tier1_architect.architect_global_plan(job)
    payload = plan.to_dict()
    restored = tier_contracts.ArchitectPlan.from_dict(payload)

    assert restored.root_job_id == "job-1"
    assert restored.system_state_refs == ["state://module/core", "state://manifest/current"]
    assert [n.node_id for n in restored.global_dag.nodes] == ["a", "b"]
    assert restored.validation_errors == []
    assert restored.tier_assignments == {"a": 2, "b": 2}


def test_assign_task_slices_preserves_dependency_and_parent_lineage():
    dag = _dag([
        tier_contracts.PlanNode("a", "root", []),
        tier_contracts.PlanNode("b", "child", ["a"], parent_node_id="global-b"),
    ])

    slices = tier2_decomposer.assign_task_slices(
        dag,
        node_tools={"a": [], "b": []},
        allowed_tools=[],
        model_class_map={"a": "llm", "b": "slm"},
    )

    assert slices[0].depends_on == []
    assert slices[0].parent_node_id == "a"
    assert slices[1].depends_on == ["a"]
    assert slices[1].parent_node_id == "global-b"
    assert slices[1].model_class == "slm"


def test_tier1_dispatch_returns_valid_global_plan_and_slices():
    job = {
        "job_id": "job-2",
        "system_state_refs": ["state://repo/head"],
        "task_graph": [
            {"task_id": "doc", "task_type": "write README docs", "blocked_by": [], "tier": 2},
            {"task_id": "code", "task_type": "implement code", "blocked_by": ["doc"], "tier": 2},
        ],
    }

    result = tier_dispatcher.dispatch_to_tier(1, job)

    assert result["dispatched"] is True
    assert result["architect_plan"]["root_job_id"] == "job-2"
    assert result["architect_plan"]["system_state_refs"] == ["state://repo/head"]
    assert result["validation"] == []
    assert result["task_slices"][0]["model_class"] == "slm"
    assert result["task_slices"][1]["depends_on"] == ["doc"]


def test_tier2_dispatch_rejects_invalid_dag_before_slicing():
    job = {
        "job_id": "bad-job",
        "task_graph": [
            {"task_id": "a", "task_type": "first", "blocked_by": [], "tier": 2},
            {"task_id": "a", "task_type": "duplicate", "blocked_by": [], "tier": 2},
        ],
    }

    result = tier_dispatcher.dispatch_to_tier(2, job)

    assert result["dispatched"] is False
    assert result["reason"] == "invalid_dag"
    assert "duplicate_node_id: a" in result["validation"]
