from __future__ import annotations

import os


def test_resolve_provider_defaults():
    from model_packs.coding_agent.domain_lib import provider_routing

    info = provider_routing.resolve_provider_for_slice({"tier": 3})
    assert isinstance(info, dict)
    assert "provider" in info
    assert "requires_api_key" in info


def test_is_provider_allowed_env_false(monkeypatch):
    from model_packs.coding_agent.domain_lib import provider_routing

    monkeypatch.setenv("LUMINA_ALLOW_CLOUD", "false")
    assert not provider_routing.is_provider_allowed("openai", {"tier": 3})
    # local provider always allowed
    assert provider_routing.is_provider_allowed("local", {"tier": 3})
