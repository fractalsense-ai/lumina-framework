"""Tests for deterministic Slice 29 decision-precedent confidence scoring."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lumina.decision_precedent.policy import DecisionPrecedentPolicy
from lumina.decision_precedent.scorer import PrecedentCandidate, score_decision_precedent

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _policy() -> DecisionPrecedentPolicy:
    return DecisionPrecedentPolicy(
        policy_version=1, candidate_limit=3, suggest_threshold=0.88,
        confirmation_threshold=0.70, stale_after_days=90, stale_penalty=0.18,
        missing_precedent_penalty=1.0, high_risk_classes=("financial",),
        confirmation_risk_classes=("operational",), organization_id="org-a", site_id="site-a",
    )


def _candidate(score: float, *, age_days: int = 1, record_id: str = "summary-a") -> PrecedentCandidate:
    return PrecedentCandidate(
        summary_record_id=record_id, thread_id="thread-a", similarity=score,
        created_utc=NOW - timedelta(days=age_days),
    )


@pytest.mark.unit
def test_high_confidence_low_risk_precedent_is_suggest_only() -> None:
    score = score_decision_precedent([_candidate(0.91)], _policy(), actor_id="actor-a", risk_class="routine", evaluated_utc=NOW, record_id="score-a")

    assert score.final_score == 0.91
    assert score.tier == "suggest_only"
    assert score.rationale_codes == ("high_confidence_precedent",)


@pytest.mark.unit
def test_high_risk_overrides_high_similarity() -> None:
    score = score_decision_precedent([_candidate(0.99)], _policy(), actor_id="actor-a", risk_class="financial", evaluated_utc=NOW)

    assert score.tier == "mandatory_escalation"
    assert "high_risk_class" in score.rationale_codes


@pytest.mark.unit
def test_missing_precedent_always_escalates() -> None:
    score = score_decision_precedent([], _policy(), actor_id="actor-a", risk_class="routine", evaluated_utc=NOW)

    assert score.final_score == 0.0
    assert score.tier == "mandatory_escalation"
    assert score.missing_precedent_penalty == 1.0


@pytest.mark.unit
def test_stale_precedent_applies_policy_penalty() -> None:
    score = score_decision_precedent([_candidate(0.90, age_days=91)], _policy(), actor_id="actor-a", risk_class="routine", evaluated_utc=NOW)

    assert score.final_score == 0.72
    assert score.tier == "require_confirmation"
    assert score.precedent_matches[0].recency_band == "stale"


@pytest.mark.unit
def test_equal_scores_have_stable_record_id_ordering() -> None:
    score = score_decision_precedent([_candidate(0.80, record_id="summary-z"), _candidate(0.80, record_id="summary-a")], _policy(), actor_id="actor-a", risk_class="routine", evaluated_utc=NOW)

    assert [match.summary_record_id for match in score.precedent_matches] == ["summary-a", "summary-z"]


@pytest.mark.unit
def test_score_record_is_transcript_free_and_schema_ready() -> None:
    record = score_decision_precedent([_candidate(0.91)], _policy(), actor_id="actor-a", risk_class="routine", evaluated_utc=NOW, record_id="score-a").as_record(created_utc=NOW)

    assert record["record_id"] == "score-a"
    assert "summary" not in record
    assert "message" not in record