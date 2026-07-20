"""Tests for Slice 29 Business Ops decision-precedent policy resolution."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from lumina.decision_precedent.policy import (
    load_decision_precedent_policy,
    resolve_decision_precedent_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "model-packs" / "business-ops" / "cfg" / "decision-precedent-policy.yaml"
SCHEMA_PATH = REPO_ROOT / "standards" / "decision-precedent-policy-schema-v1.json"


def _config() -> dict:
    return {
        "schema_version": "1.0.0",
        "policy_version": 3,
        "defaults": {
            "candidate_limit": 5,
            "suggest_threshold": 0.85,
            "confirmation_threshold": 0.65,
            "stale_after_days": 60,
            "stale_penalty": 0.20,
            "missing_precedent_penalty": 1.0,
            "high_risk_classes": ["financial"],
            "confirmation_risk_classes": ["operational"],
        },
        "organizations": {},
    }


@pytest.mark.unit
def test_business_ops_policy_file_matches_schema() -> None:
    import yaml

    config = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(config, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.mark.unit
def test_policy_resolves_default_organization_and_site_precedence() -> None:
    config = _config()
    config["organizations"] = {
        "org-a": {
            "suggest_threshold": 0.90,
            "stale_after_days": 30,
            "sites": {"site-a": {"confirmation_threshold": 0.75, "candidate_limit": 3}},
        }
    }

    policy = resolve_decision_precedent_policy(config, organization_id="org-a", site_id="site-a")

    assert policy.suggest_threshold == 0.90
    assert policy.confirmation_threshold == 0.75
    assert policy.stale_after_days == 30
    assert policy.candidate_limit == 3
    assert policy.organization_id == "org-a"
    assert policy.site_id == "site-a"


@pytest.mark.unit
def test_policy_does_not_leak_another_organization_override() -> None:
    config = _config()
    config["organizations"] = {"org-a": {"suggest_threshold": 0.99}}

    policy = resolve_decision_precedent_policy(config, organization_id="org-b", site_id="site-a")

    assert policy.suggest_threshold == 0.85


@pytest.mark.unit
@pytest.mark.parametrize("organization_id,site_id", [("", "site-a"), ("org-a", "")])
def test_policy_requires_authenticated_scope(organization_id: str, site_id: str) -> None:
    with pytest.raises(ValueError, match="requires"):
        resolve_decision_precedent_policy(_config(), organization_id=organization_id, site_id=site_id)


@pytest.mark.unit
def test_policy_rejects_reversed_thresholds() -> None:
    config = _config()
    config["defaults"]["confirmation_threshold"] = 0.86

    with pytest.raises(ValueError, match="cannot exceed"):
        resolve_decision_precedent_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_rejects_overlapping_risk_classes() -> None:
    config = _config()
    config["defaults"]["confirmation_risk_classes"] = ["financial"]

    with pytest.raises(ValueError, match="cannot overlap"):
        resolve_decision_precedent_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_rejects_unknown_override_fields() -> None:
    config = deepcopy(_config())
    config["organizations"] = {"org-a": {"skip_audit": True}}

    with pytest.raises(ValueError, match="unknown fields"):
        resolve_decision_precedent_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_rejects_unknown_top_level_fields() -> None:
    config = _config()
    config["skip_audit"] = True

    with pytest.raises(ValueError, match="unknown top-level"):
        resolve_decision_precedent_policy(config, organization_id="org-a", site_id="site-a")


@pytest.mark.unit
def test_policy_file_loads_through_core_yaml_loader() -> None:
    policy = load_decision_precedent_policy(POLICY_PATH, organization_id="org-a", site_id="site-a")

    assert policy.policy_version == 1
    assert policy.high_risk_classes == ("financial", "safety", "legal")