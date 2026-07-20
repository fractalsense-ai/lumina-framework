"""Validation tests for Slice 29 policy and transcript-free evidence contracts."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
import yaml

from lumina.decision_precedent.policy import resolve_decision_precedent_policy
from lumina.decision_precedent.scorer import PrecedentCandidate, score_decision_precedent

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS = REPO_ROOT / "standards"
POLICY_PATH = REPO_ROOT / "model-packs" / "business-ops" / "cfg" / "decision-precedent-policy.yaml"


def _schema(name: str) -> dict:
    return json.loads((STANDARDS / name).read_text(encoding="utf-8"))


def _score_record() -> dict:
    config = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    policy = resolve_decision_precedent_policy(config, organization_id="org-a", site_id="site-a")
    return score_decision_precedent(
        [PrecedentCandidate("summary-a", "thread-a", 0.91, datetime(2026, 7, 20, tzinfo=UTC))],
        policy,
        actor_id="actor-a",
        risk_class="routine",
        evaluated_utc=datetime(2026, 7, 20, tzinfo=UTC),
        record_id="confidence-a",
    ).as_record(created_utc=datetime(2026, 7, 20, tzinfo=UTC))


@pytest.mark.unit
def test_policy_schema_accepts_site_override() -> None:
    config = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    config["organizations"] = {"org-a": {"sites": {"site-a": {"candidate_limit": 3}}}}

    jsonschema.validate(config, _schema("decision-precedent-policy-schema-v1.json"))


@pytest.mark.unit
def test_confidence_score_and_match_records_validate() -> None:
    record = _score_record()

    jsonschema.validate(record, _schema("decision-confidence-score-schema-v1.json"), format_checker=jsonschema.FormatChecker())
    jsonschema.validate(record["precedent_matches"][0], _schema("precedent-match-schema-v1.json"), format_checker=jsonschema.FormatChecker())


@pytest.mark.unit
def test_confidence_contract_rejects_raw_message_field() -> None:
    record = _score_record()
    record["message"] = "raw transcript content"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, _schema("decision-confidence-score-schema-v1.json"))


@pytest.mark.unit
def test_escalation_packet_contract_rejects_provider_mutation_data() -> None:
    packet = {
        "packet_id": "packet-a", "organization_id": "org-a", "site_id": "site-a",
        "actor_id": "actor-a", "confidence_record_id": "confidence-a", "policy_version": 1,
        "risk_class": "financial", "tier": "mandatory_escalation",
        "target_role": "business-ops:owner-manager", "status": "pending",
        "precedent_summary_record_ids": ["summary-a"], "created_utc": "2026-07-20T00:00:00Z",
    }
    schema = _schema("business-escalation-packet-schema-v1.json")
    jsonschema.validate(packet, schema, format_checker=jsonschema.FormatChecker())
    unsafe_packet = deepcopy(packet)
    unsafe_packet["provider_mutation"] = {"operation": "create_work_order"}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(unsafe_packet, schema)