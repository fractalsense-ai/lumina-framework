"""Evidence harvest contract for Coding Agent.

This module defines an `EvidencePacket` used to persist test/artifact
evidence after a plan/slice reaches the `Registered` state. The module is
minimal and serialization-friendly.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List
from datetime import datetime, UTC


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class EvidencePacket:
    plan_id: str
    slice_id: str
    node_id: str
    artifacts: List[Dict[str, Any]]
    test_summary: Dict[str, Any]
    checksums: Dict[str, str]
    collected_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_evidence_from_orchestration(plan_id: str, slice_result: Dict[str, Any]) -> EvidencePacket:
    node_id = slice_result.get("node_id") or slice_result.get("slice_id") or ""
    artifacts = slice_result.get("artifacts") or []
    test_summary = slice_result.get("tests") or {}
    checksums = slice_result.get("checksums") or {}
    return EvidencePacket(plan_id=plan_id, slice_id=slice_result.get("slice_id", ""), node_id=node_id, artifacts=artifacts, test_summary=test_summary, checksums=checksums)
