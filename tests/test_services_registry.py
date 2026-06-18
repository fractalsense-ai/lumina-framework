"""Tests for lumina.services.registry.

Verifies that SERVICES and CORE_ROUTES are correctly defined and importable.
"""
from __future__ import annotations

import pytest

from lumina.services.registry import CORE_ROUTES, SERVICES


# ── SERVICES dict ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_services_is_dict() -> None:
    assert isinstance(SERVICES, dict)
    assert len(SERVICES) > 0


@pytest.mark.unit
def test_services_required_keys() -> None:
    for name, entry in SERVICES.items():
        assert "package" in entry, f"Service {name!r} missing 'package'"
        assert "app" in entry, f"Service {name!r} missing 'app'"
        assert "port" in entry, f"Service {name!r} missing 'port'"
        assert isinstance(entry["port"], int), f"Service {name!r} port is not int"


@pytest.mark.unit
def test_services_known_names() -> None:
    expected = {"auth", "system_log", "ingestion", "domain", "dashboard", "admin"}
    assert expected.issubset(set(SERVICES.keys()))


@pytest.mark.unit
def test_services_ports_unique() -> None:
    ports = [e["port"] for e in SERVICES.values()]
    assert len(ports) == len(set(ports)), "Duplicate service ports detected"


# ── CORE_ROUTES list ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_core_routes_is_list() -> None:
    assert isinstance(CORE_ROUTES, list)
    assert len(CORE_ROUTES) > 0


@pytest.mark.unit
def test_core_routes_contains_chat() -> None:
    assert "chat" in CORE_ROUTES


@pytest.mark.unit
def test_core_routes_are_strings() -> None:
    for route in CORE_ROUTES:
        assert isinstance(route, str), f"Non-string route entry: {route!r}"
