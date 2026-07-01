"""System Pack activation/approval gate for Coding Agent slices. (compat path)

This mirrors the implementation under model-packs for CI and import compatibility.
"""
from __future__ import annotations

from typing import Any, Dict


def requires_system_approval(evidence: Dict[str, Any]) -> bool:
    if not isinstance(evidence, dict):
        return False
    return bool(evidence.get("activation_request"))


def is_system_approved(evidence: Dict[str, Any]) -> bool:
    if not isinstance(evidence, dict):
        return False
    ap = evidence.get("system_approval")
    if not isinstance(ap, dict):
        return False
    return bool(ap.get("approved") is True and ap.get("issuer") == "system_pack")


def validate_activation(evidence: Dict[str, Any]) -> bool:
    if not requires_system_approval(evidence):
        return True
    return is_system_approved(evidence)
