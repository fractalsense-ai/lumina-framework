"""Smoke tests for the Coding Agent model pack skeleton."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = REPO_ROOT / "model-packs" / "coding-agent"
CTRL_DIR = PACK / "controllers"
PHYSICS_PATH = PACK / "modules" / "core" / "domain-physics.json"
SCHEMA_PATH = REPO_ROOT / "standards" / "domain-physics-schema-v1.json"
REGISTRY_PATH = REPO_ROOT / "model-packs" / "system" / "cfg" / "domain-registry.yaml"


def _import_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None, f"Cannot load spec from {path}"
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.base_framework
class TestCodingAgentPackFiles:
    def test_required_files_exist(self):
        required = [
            "pack.yaml",
            "cfg/runtime-config.yaml",
            "cfg/domain-profile-extension.yaml",
            "cfg/ui-config.yaml",
            "profiles/entity.yaml",
            "modules/core/module-config.yaml",
            "modules/core/domain-physics.json",
            "controllers/runtime_adapters.py",
            "controllers/nlp_pre_interpreter.py",
            "domain-lib/job_contracts.py",
            "domain-lib/reference/turn-interpretation-spec-v1.md",
            "prompts/domain-persona-v1.md",
            "README.md",
            "CHANGELOG.md",
        ]
        missing = [rel for rel in required if not (PACK / rel).is_file()]
        assert not missing

    def test_pack_manifest_identity(self):
        data = _load_yaml(PACK / "pack.yaml")
        assert data["pack_id"] == "coding-agent"
        assert data["default_module"] == "core"
        assert "core" in data["modules"]

    def test_runtime_config_binds_required_adapters(self):
        data = _load_yaml(PACK / "cfg" / "runtime-config.yaml")
        adapters = data["adapters"]
        for adapter_name in ("state_builder", "domain_step", "turn_interpreter"):
            assert adapter_name in adapters
            assert adapters[adapter_name]["module_path"] == "model-packs/coding-agent/controllers/runtime_adapters.py"
            assert adapters[adapter_name]["callable"]


@pytest.mark.base_framework
class TestCodingAgentAdapters:
    @pytest.fixture(autouse=True)
    def _load_adapters(self):
        self.mod = _import_module_from_path(
            "coding_agent_runtime_adapters",
            CTRL_DIR / "runtime_adapters.py",
        )

    def test_build_initial_state_returns_expected_keys(self):
        state = self.mod.build_initial_state({"entity_state": {"completed_jobs": 2}})
        assert state["turn_count"] == 0
        assert state["scoped_jobs_completed"] == 2
        assert state["boundary_violations"] == 0
        assert state["pending_validation"] is False

    def test_domain_step_rejects_missing_scope(self):
        state, decision = self.mod.domain_step({}, {"task_id": "job-1"}, {"job_scope_valid": False}, {})
        assert state["boundary_violations"] == 1
        assert decision["tier"] == "critical"
        assert decision["action"] == "reject_out_of_scope"

    def test_domain_step_requests_validation_for_failed_tests(self):
        state, decision = self.mod.domain_step(
            {},
            {"task_id": "job-1"},
            {"job_scope_valid": True, "patch_generated": True, "tests_passed": False},
            {},
        )
        assert state["pending_validation"] is True
        assert decision["tier"] == "minor"
        assert decision["action"] == "run_local_validation"

    def test_domain_step_stages_validated_patch(self):
        state, decision = self.mod.domain_step(
            {"scoped_jobs_completed": 0},
            {"task_id": "job-1"},
            {"job_scope_valid": True, "patch_generated": True, "tests_passed": True},
            {},
        )
        assert state["scoped_jobs_completed"] == 1
        assert decision["action"] == "stage_patch_for_review"

    def test_interpret_turn_input_merges_defaults_and_json(self):
        def mock_llm(system, user, model):
            return """```json
{"job_scope_valid": true, "requested_files": ["model-packs/coding-agent/pack.yaml"], "confidence": 0.9}
```"""

        evidence = self.mod.interpret_turn_input(mock_llm, "edit pack", {}, "prompt")
        assert evidence["job_scope_valid"] is True
        assert evidence["authority_boundary_violation"] is False
        assert evidence["requested_files"] == ["model-packs/coding-agent/pack.yaml"]
        assert evidence["confidence"] == 0.9

    def test_interpret_turn_input_allows_scope_checker_override(self):
        def mock_llm(system, user, model):
            return "{}"

        def scope_checker(payload):
            return {"job_scope_valid": True, "confidence": 1.0}

        evidence = self.mod.interpret_turn_input(
            mock_llm,
            "approved job",
            {},
            "prompt",
            tool_fns={"scope_checker": scope_checker},
        )
        assert evidence["job_scope_valid"] is True
        assert evidence["confidence"] == 1.0


@pytest.mark.base_framework
class TestCodingAgentPhysicsAndRegistry:
    def test_domain_physics_validates_against_schema(self):
        jsonschema.validate(instance=_load_json(PHYSICS_PATH), schema=_load_json(SCHEMA_PATH))

    def test_domain_physics_preserves_authority_air_gap(self):
        physics = _load_json(PHYSICS_PATH)
        invariant_ids = {item["id"] for item in physics["invariants"]}
        assert "system_pack_sole_ingress" in invariant_ids
        assert "no_authority_escalation_inside_pack" in invariant_ids

    def test_registry_contains_coding_agent(self):
        registry = _load_yaml(REGISTRY_PATH)
        entry = registry["domains"]["coding-agent"]
        assert entry["runtime_config_path"] == "model-packs/coding-agent/cfg/runtime-config.yaml"
        assert entry["module_prefix"] == "ca"