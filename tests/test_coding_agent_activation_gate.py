from __future__ import annotations

import importlib.util
import pathlib
import sys


BASE = pathlib.Path(__file__).parent.parent / "model-packs" / "coding-agent"
CONTROLLERS = BASE / "controllers"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_activation_blocks_without_system_approval():
    runtime = _load("coding_agent_runtime_slice22", CONTROLLERS / "runtime_adapters.py")

    state = {"turn_count": 0}
    task_spec = {"task_id": "job-22"}
    evidence = {
        "job_scope_valid": True,
        "patch_generated": True,
        "tests_passed": True,
        "activation_request": True,
    }

    next_state, out = runtime.domain_step(state, task_spec, evidence, {})

    assert next_state.get("turn_count") == 1
    assert out.get("action") == "awaiting_system_approval"
    assert out.get("reason") == "activation_requires_system_approval"


def test_activation_allows_with_system_approval():
    runtime = _load("coding_agent_runtime_slice22b", CONTROLLERS / "runtime_adapters.py")

    state = {"turn_count": 0}
    task_spec = {"task_id": "job-22b"}
    evidence = {
        "job_scope_valid": True,
        "patch_generated": True,
        "tests_passed": True,
        "activation_request": True,
        "system_approval": {"approved": True, "issuer": "system_pack"},
    }

    next_state, out = runtime.domain_step(state, task_spec, evidence, {})

    assert next_state.get("turn_count") == 1
    assert out.get("action") == "stage_patch_for_review"
    assert out.get("approved") is True
