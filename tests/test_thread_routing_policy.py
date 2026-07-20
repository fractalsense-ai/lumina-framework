"""Tests for Slice 28 Business Ops thread-routing policy resolution."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from lumina.thread_routing.policy import load_thread_routing_policy, resolve_thread_routing_policy

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "model-packs" / "business-ops" / "cfg" / "thread-routing-policy.yaml"
SCHEMA_PATH = REPO_ROOT / "standards" / "thread-routing-policy-schema-v1.json"


def _config() -> dict:
    return {
        "schema_version": "1.0.0",
        "policy_version": 3,
        "defaults": {
            "attach_threshold": 0.80,
            "fork_threshold": 0.60,
            "ambiguity_margin": 0.05,
            "recap_interval_turns": 10,
            "candidate_limit": 5,
            "manual_only": False,
            "require_operator_confirmation_for": ["fork_from"],
        },
        "organizations": {},
    }


@pytest.mark.unit
def test_business_ops_policy_file_matches_schema() -> None:
    import yaml

    config = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(config, schema)


@pytest.mark.unit
def test_policy_resolves_default_organization_and_site_precedence() -> None:
    config = _config()
    config["organizations"] = {
        "org-a": {
            "attach_threshold": 0.90,
            "recap_interval_turns": 8,
            "sites": {
                "site-a": {
                    "fork_threshold": 0.70,
                    "candidate_limit": 3,
                },
            },
        },
    }

    policy = resolve_thread_routing_policy(config, organization_id="org-a", site_id="site-a")

    assert policy.attach_threshold == 0.90
    assert policy.fork_threshold == 0.70
    assert policy.recap_interval_turns == 8
    assert policy.candidate_limit == 3
    assert policy.ambiguity_margin == 0.05
    assert policy.organization_id == "org-a"
    assert policy.site_id == "site-a"


@pytest.mark.unit
def test_policy_does_not_leak_another_organization_override() -> None:
    config = _config()
    config["organizations"] = {"org-a": {"attach_threshold": 0.95}}

    policy = resolve_thread_routing_policy(config, organization_id="org-b", site_id="site-a")

    assert policy.attach_threshold == 0.80


@pytest.mark.unit
@pytest.mark.parametrize("organization_id,site_id", [("", "site-a"), ("org-a", "")])
def test_policy_requires_authenticated_scope(organization_id: str, site_id: str) -> None:
    with pytest.raises(ValueError, match="requires"):
        resolve_thread_routing_policy(_config(), organization_id=organization_id, site_id=site_id)


@pytest.mark.unit
def test_policy_rejects_thresholds_that_weaken_fork_boundary() -> None:
    config = _config()
    config["defaults"]["fork_threshold"] = 0.81

    with pytest.raises(ValueError, match="cannot exceed"):
        resolve_thread_routing_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_rejects_unknown_override_fields() -> None:
    config = deepcopy(_config())
    config["organizations"] = {"org-a": {"skip_audit": True}}

    with pytest.raises(ValueError, match="unknown fields"):
        resolve_thread_routing_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_rejects_unknown_top_level_fields() -> None:
    config = _config()
    config["skip_audit"] = True

    with pytest.raises(ValueError, match="unknown top-level"):
        resolve_thread_routing_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_file_loads_through_core_yaml_loader() -> None:
    policy = load_thread_routing_policy(POLICY_PATH, organization_id="org-a", site_id="site-a")

    assert policy.policy_version == 1
    assert policy.require_operator_confirmation_for == ("fork_from", "ambiguous_attach")