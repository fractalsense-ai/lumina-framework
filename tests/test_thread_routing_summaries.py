"""Tests for transcript-free, cadence-controlled thread recap persistence."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from lumina.persistence.adapter import NullPersistenceAdapter
from lumina.thread_routing.policy import ThreadRoutingPolicy
from lumina.thread_routing.summaries import record_thread_recap

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "standards" / "thread-summary-state-schema-v1.json"
SUMMARY_RECORD_SCHEMA_PATH = REPO_ROOT / "standards" / "thread-summary-record-schema-v1.json"


class _RecordingIndexer:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def ingest(self, records):
        self.records.extend(records)
        return {"records_seen": len(records), "records_indexed": len(records), "records_skipped": 0}


def _policy() -> ThreadRoutingPolicy:
    return ThreadRoutingPolicy(
        policy_version=1,
        attach_threshold=0.86,
        fork_threshold=0.62,
        ambiguity_margin=0.04,
        recap_interval_turns=3,
        candidate_limit=5,
        manual_only=False,
        require_operator_confirmation_for=("fork_from",),
        organization_id="org-a",
        site_id="site-a",
    )


def test_recap_indexes_first_turn_and_uses_schema_valid_transcript_free_state() -> None:
    persistence = NullPersistenceAdapter()
    indexer = _RecordingIndexer()
    message = "Please inspect brake failure details today."

    state = record_thread_recap(
        persistence=persistence,
        indexer=indexer,
        policy=_policy(),
        thread_id="thread-a",
        actor_id="actor-a",
        turn_count=1,
        message=message,
        action="continue",
        domain_id="operations",
    )

    assert state is not None
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(state, schema, format_checker=jsonschema.FormatChecker())
    assert len(indexer.records) == 1
    summary_schema = json.loads(SUMMARY_RECORD_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(indexer.records[0], summary_schema, format_checker=jsonschema.FormatChecker())
    serialized = json.dumps({"state": state, "record": indexer.records[0]}).lower()
    assert message.lower() not in serialized
    assert "transcript" not in serialized
    assert "message" not in indexer.records[0]
    assert indexer.records[0]["record_type"] == "ThreadSummaryRecord"
    assert indexer.records[0]["thread_id"] == "thread-a"


def test_recap_uses_configured_interval_and_advances_recap_version() -> None:
    persistence = NullPersistenceAdapter()
    indexer = _RecordingIndexer()
    first = record_thread_recap(
        persistence=persistence, indexer=indexer, policy=_policy(),
        thread_id="thread-a", actor_id="actor-a", turn_count=1,
        message="inventory review", action="continue", domain_id="operations",
    )
    skipped = record_thread_recap(
        persistence=persistence, indexer=indexer, policy=_policy(),
        thread_id="thread-a", actor_id="actor-a", turn_count=3,
        message="inventory count", action="continue", domain_id="operations",
    )
    second = record_thread_recap(
        persistence=persistence, indexer=indexer, policy=_policy(),
        thread_id="thread-a", actor_id="actor-a", turn_count=4,
        message="inventory reconciliation", action="continue", domain_id="operations",
    )

    assert first is not None
    assert skipped is None
    assert second is not None
    assert second["recap_version"] == 2
    assert second["turn_start"] == 2
    assert second["turn_end"] == 4
    assert len(indexer.records) == 2