"""Deterministic routing-decision tests for Slice 28."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from lumina.thread_routing.policy import ThreadRoutingPolicy
from lumina.thread_routing.router import ThreadCandidate, decide_thread_route

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "standards" / "thread-routing-decision-schema-v1.json"
SUMMARY_STATE_SCHEMA_PATH = REPO_ROOT / "standards" / "thread-summary-state-schema-v1.json"


def _policy(**overrides: object) -> ThreadRoutingPolicy:
    values: dict[str, object] = {
        "policy_version": 1,
        "attach_threshold": 0.85,
        "fork_threshold": 0.60,
        "ambiguity_margin": 0.04,
        "recap_interval_turns": 10,
        "candidate_limit": 5,
        "manual_only": False,
        "require_operator_confirmation_for": ("fork_from",),
        "organization_id": "org-a",
        "site_id": "site-a",
    }
    values.update(overrides)
    return ThreadRoutingPolicy(**values)  # type: ignore[arg-type]


def _candidate(thread_id: str, score: float) -> ThreadCandidate:
    return ThreadCandidate(thread_id, f"summary-{thread_id}", score)


@pytest.mark.unit
def test_high_confidence_candidate_attaches_with_stable_tie_break() -> None:
    decision = decide_thread_route(
        [_candidate("thread-b", 0.90), _candidate("thread-a", 0.90)],
        _policy(),
        actor_id="actor-a",
        new_thread_id="unused",
    )

    assert decision.decision == "attach_existing"
    assert decision.thread_id == "thread-a"
    assert decision.rationale_code == "ambiguous_attach"
    assert decision.operator_confirmation_required is True


@pytest.mark.unit
def test_unmatched_turn_creates_new_thread() -> None:
    decision = decide_thread_route(
        [_candidate("thread-a", 0.70)],
        _policy(),
        actor_id="actor-a",
        new_thread_id="thread-new",
    )

    assert decision.decision == "create_new"
    assert decision.thread_id == "thread-new"
    assert decision.rationale_code == "no_eligible_match"


@pytest.mark.unit
def test_active_thread_drift_forks_with_explicit_source() -> None:
    decision = decide_thread_route(
        [_candidate("thread-active", 0.20)],
        _policy(),
        actor_id="actor-a",
        active_thread_id="thread-active",
        new_thread_id="thread-fork",
    )

    assert decision.decision == "fork_from"
    assert decision.thread_id == "thread-fork"
    assert decision.source_thread_id == "thread-active"
    assert decision.rationale_code == "topic_drift"
    assert decision.operator_confirmation_required is True


@pytest.mark.unit
def test_manual_policy_requires_confirmation_without_attaching() -> None:
    decision = decide_thread_route(
        [_candidate("thread-a", 0.99)],
        _policy(manual_only=True),
        actor_id="actor-a",
        new_thread_id="thread-new",
    )

    assert decision.decision == "create_new"
    assert decision.rationale_code == "manual_policy"
    assert decision.operator_confirmation_required is True


@pytest.mark.unit
def test_decision_record_is_schema_valid_and_transcript_free() -> None:
    decision = decide_thread_route(
        [_candidate("thread-a", 0.90)],
        _policy(),
        actor_id="actor-a",
        decision_id="decision-1",
    )
    record = decision.as_record(created_utc=datetime(2026, 7, 19, tzinfo=UTC))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.validate(record, schema, format_checker=jsonschema.FormatChecker())
    assert "transcript" not in json.dumps(record).lower()


@pytest.mark.unit
def test_thread_summary_state_schema_is_transcript_free() -> None:
    summary_state = {
        "schema_version": "1.0.0",
        "thread_id": "thread-a",
        "organization_id": "org-a",
        "site_id": "site-a",
        "actor_id": "actor-a",
        "status": "open",
        "summary_record_id": "summary-a",
        "latest_routing_decision_id": "decision-a",
        "recap_version": 1,
        "turn_start": 1,
        "turn_end": 10,
        "topics": ["brake inspection"],
        "updated_utc": "2026-07-19T00:00:00Z",
    }
    schema = json.loads(SUMMARY_STATE_SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.validate(summary_state, schema, format_checker=jsonschema.FormatChecker())
    assert "transcript" not in json.dumps(summary_state).lower()


@pytest.mark.unit
def test_router_requires_actor_identity() -> None:
    with pytest.raises(ValueError, match="actor_id"):
        decide_thread_route([], _policy(), actor_id="")