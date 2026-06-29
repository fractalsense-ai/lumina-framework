from __future__ import annotations

from typing import Dict, Any, List

# Robust imports: allow module to be loaded as a standalone file during tests
try:
    from . import tool_adapters
    from ..domain_lib import tier_contracts, sequential_thinking_schema
except Exception:
    import importlib.util
    import pathlib
    import sys

    base = pathlib.Path(__file__).parent
    # load tool_adapters
    ta_path = base / "tool_adapters.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tool_adapters", str(ta_path))
    tool_adapters = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tool_adapters"] = tool_adapters
    spec.loader.exec_module(tool_adapters)

    # load tier_contracts
    tc_path = base.parent / "domain-lib" / "tier_contracts.py"
    spec = importlib.util.spec_from_file_location("coding_agent_tier_contracts", str(tc_path))
    tier_contracts = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_tier_contracts"] = tier_contracts
    spec.loader.exec_module(tier_contracts)

    # load sequential_thinking_schema
    st_path = base.parent / "domain-lib" / "sequential_thinking_schema.py"
    spec = importlib.util.spec_from_file_location("coding_agent_sequential_thinking_schema", str(st_path))
    sequential_thinking_schema = importlib.util.module_from_spec(spec)
    sys.modules["coding_agent_sequential_thinking_schema"] = sequential_thinking_schema
    spec.loader.exec_module(sequential_thinking_schema)


def _resolve_tool_registry() -> Dict[str, Any]:
    # Simple registry: adapter id -> backing function name
    return {
        "adapter/ca/read-file/v1": tool_adapters.read_file_tool,
        "adapter/ca/write-file/v1": tool_adapters.write_file_tool,
        "adapter/ca/run-tests/v1": tool_adapters.run_tests_tool,
        "adapter/ca/stage-patch/v1": tool_adapters.stage_patch_tool,
    }


def dispatch_to_tier(tier: int, task_slice: Dict[str, Any]) -> Dict[str, Any]:
    registry = _resolve_tool_registry()

    # Tier-2: perform decomposition/planning and return a PlanDAG + TaskSlices
    if tier == 2:
        try:
            # task_slice will be the job payload when called from runtime
            job = task_slice if isinstance(task_slice, dict) else {}
            # robust import of decomposer & validator (pack may be loaded as file)
            try:
                from ..domain_lib import tier2_decomposer, dag_validator
            except Exception:
                import importlib.util, pathlib, sys

                base = pathlib.Path(__file__).parent
                dec_path = base.parent / "domain-lib" / "tier2_decomposer.py"
                spec = importlib.util.spec_from_file_location("coding_agent_tier2_decomposer", str(dec_path))
                tier2_decomposer = importlib.util.module_from_spec(spec)
                sys.modules["coding_agent_tier2_decomposer"] = tier2_decomposer
                spec.loader.exec_module(tier2_decomposer)

                val_path = base.parent / "domain-lib" / "dag_validator.py"
                spec = importlib.util.spec_from_file_location("coding_agent_dag_validator", str(val_path))
                dag_validator = importlib.util.module_from_spec(spec)
                sys.modules["coding_agent_dag_validator"] = dag_validator
                spec.loader.exec_module(dag_validator)

            dag, node_tools = tier2_decomposer.decompose_job(job)
            errors = dag_validator.validate_dag(dag)
            allowed = job.get("allowed_tools") or [
                "adapter/ca/read-file/v1",
                "adapter/ca/write-file/v1",
                "adapter/ca/run-tests/v1",
                "adapter/ca/stage-patch/v1",
            ]
            slices = tier2_decomposer.assign_task_slices(dag, node_tools, allowed)
            return {
                "tier": 2,
                "dispatched": True,
                "plan": dag.to_dict(),
                "task_slices": [s.to_dict() for s in slices],
                "validation": errors,
            }
        except Exception as exc:
            return {"tier": 2, "dispatched": False, "reason": f"decompose_failed: {exc}"}

    if tier != 3:
        return {"tier": tier, "dispatched": False, "reason": "not_implemented_yet"}

    # Validate TaskSlice shape
    try:
        ts = tier_contracts.TaskSlice.from_dict(task_slice)
    except Exception as exc:
        return {"tier": 3, "dispatched": False, "reason": f"invalid_task_slice: {exc}"}

    denied = []
    allowed = []
    trace: List[Dict[str, Any]] = []

    for tool_id in ts.allowed_tools:
        if tool_id not in registry:
            denied.append(tool_id)
            continue
        allowed.append(tool_id)

    if not allowed:
        return {"tier": 3, "dispatched": False, "allowed_tools": allowed, "denied_tools": denied}

    # Execute each allowed tool with a minimal payload (TaskSlice-driven); callers may provide tool-specific payloads later.
    for tool_id in allowed:
        backing = registry[tool_id]
        # call with a conservative, safe payload per adapter signature
        if tool_id == "adapter/ca/read-file/v1":
            payload = {"path": ts.task_description}
        elif tool_id == "adapter/ca/run-tests/v1":
            payload = {"commands": ["pytest -q"]}
        elif tool_id == "adapter/ca/stage-patch/v1":
            payload = {"files": []}
        elif tool_id == "adapter/ca/write-file/v1":
            payload = {"path": "", "contents": ""}
        else:
            payload = {}

        try:
            result = backing(payload)
        except Exception as exc:  # defensive
            result = {"error": str(exc)}

        step = {
            "tool_id": tool_id,
            "payload": payload,
            "result": result,
        }
        trace.append(step)

    # Use classmethod for construction to be robust across versions
    seq_trace = sequential_thinking_schema.SequentialThinkingTrace.from_steps(trace)

    return {"tier": 3, "dispatched": True, "allowed_tools": allowed, "denied_tools": denied, "scratchpad": seq_trace.to_dict()}
