import importlib.util
import pathlib
import sys

base = pathlib.Path(__file__).parent.parent / "model-packs" / "coding-agent" / "domain-lib"

def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

tier_contracts = _load("coding_agent_tier_contracts", base / "tier_contracts.py")
tier1_architect = _load("coding_agent_tier1_architect", base / "tier1_architect.py")


def test_classify_documentation_node():
    n1 = tier_contracts.PlanNode(node_id="doc-1", description="Write README docs", depends_on=[], tier_hint=1)
    n2 = tier_contracts.PlanNode(node_id="code-1", description="Implement feature X", depends_on=[], tier_hint=2)
    dag = tier_contracts.PlanDAG(nodes=[n1, n2], created_at="now")

    classified = tier1_architect.classify_nodes(dag)
    m = tier1_architect.build_model_class_map(classified)

    assert classified.nodes[0].action_type == "document"
    assert classified.nodes[1].action_type == "code"
    assert m["doc-1"] == "slm"
    assert m["code-1"] == "llm"
