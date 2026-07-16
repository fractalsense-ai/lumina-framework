"""Validation tests for Slice 26 provider-neutral memory contracts."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = sorted((REPO_ROOT / "standards").glob("*-record-schema-v1.json"))
MEMORY_SCHEMA_PATHS = [
    path for path in SCHEMA_PATHS
    if path.name in {
        "institutional-memory-record-schema-v1.json",
        "decision-precedent-record-schema-v1.json",
        "thread-summary-record-schema-v1.json",
        "business-system-event-mirror-record-schema-v1.json",
    }
]


def _schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_record(path: Path) -> dict:
    record_type = _schema(path)["properties"]["record_type"]["const"]
    record = {
        "record_type": record_type,
        "record_id": "record-001",
        "organization_id": "org-001",
        "site_id": "site-001",
        "actor_id": "actor-001",
        "created_utc": "2026-07-15T12:00:00Z",
    }
    if record_type == "InstitutionalMemoryRecord":
        record.update({"memory_type": "observation", "summary": "A scoped observation."})
    elif record_type == "DecisionPrecedentRecord":
        record.update({"decision_summary": "Use the approved procedure.", "outcome": "successful"})
    elif record_type == "ThreadSummaryRecord":
        record.update({"thread_id": "thread-001", "summary": "The thread was resolved.", "status": "resolved"})
    else:
        record.update({
            "event_type": "work_order.updated",
            "occurred_utc": "2026-07-15T11:59:00Z",
            "external_system_reference": {
                "connector_instance_id": "connector-001",
                "external_record_type": "work_order",
                "external_record_id": "wo-001",
            },
        })
    return record


@pytest.mark.unit
@pytest.mark.parametrize("path", MEMORY_SCHEMA_PATHS, ids=lambda path: path.stem)
def test_scoped_memory_record_accepts_valid_payload(path: Path) -> None:
    jsonschema.validate(_base_record(path), _schema(path), format_checker=jsonschema.FormatChecker())


@pytest.mark.unit
@pytest.mark.parametrize("field", ["organization_id", "site_id", "actor_id"])
def test_memory_records_require_scope_fields(field: str) -> None:
    for path in MEMORY_SCHEMA_PATHS:
        record = _base_record(path)
        record.pop(field)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(record, _schema(path))


@pytest.mark.unit
def test_device_id_is_optional_but_nonblank_when_present() -> None:
    for path in MEMORY_SCHEMA_PATHS:
        record = _base_record(path)
        record["device_id"] = "device-001"
        jsonschema.validate(record, _schema(path))
        record["device_id"] = ""
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(record, _schema(path))


@pytest.mark.unit
def test_external_reference_requires_provider_neutral_identity_fields() -> None:
    for path in MEMORY_SCHEMA_PATHS:
        schema = _schema(path)
        if "external_system_reference" not in schema["properties"]:
            continue
        record = _base_record(path)
        record["external_system_reference"] = {"connector_instance_id": "connector-001"}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(record, schema)


@pytest.mark.unit
def test_provider_details_are_namespaced_and_credentials_are_not_canonical() -> None:
    for path in MEMORY_SCHEMA_PATHS:
        schema = _schema(path)
        record = _base_record(path)
        reference = record.get("external_system_reference")
        if reference is None:
            reference = {
                "connector_instance_id": "connector-001",
                "external_record_type": "case",
                "external_record_id": "case-001",
            }
            record["external_system_reference"] = reference
        reference["provider_data"] = {"doctype": "Work Order"}
        jsonschema.validate(record, schema)

        credential_record = deepcopy(record)
        credential_record["api_key"] = "must-not-be-canonical"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(credential_record, schema)
