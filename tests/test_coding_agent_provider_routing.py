from __future__ import annotations

import os


def test_resolve_provider_defaults():
    # Load canonical module from model-packs path (avoid importing model_packs package)
    import importlib.util, pathlib

    base = pathlib.Path(__file__).resolve().parents[1]
    pr_path = base / "model-packs" / "coding-agent" / "domain-lib" / "provider_routing.py"
    spec = importlib.util.spec_from_file_location("provider_routing", str(pr_path))
    provider_routing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider_routing)

    info = provider_routing.resolve_provider_for_slice({"tier": 3})
    assert isinstance(info, dict)
    assert "provider" in info
    assert "requires_api_key" in info


def test_is_provider_allowed_env_false(monkeypatch):
    import importlib.util, pathlib

    base = pathlib.Path(__file__).resolve().parents[1]
    pr_path = base / "model-packs" / "coding-agent" / "domain-lib" / "provider_routing.py"
    spec = importlib.util.spec_from_file_location("provider_routing", str(pr_path))
    provider_routing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider_routing)

    monkeypatch.setenv("LUMINA_ALLOW_CLOUD", "false")
    assert not provider_routing.is_provider_allowed("openai", {"tier": 3})
    # local provider always allowed
    assert provider_routing.is_provider_allowed("local", {"tier": 3})
