from __future__ import annotations

import os
from typing import Dict, Any


DEFAULT_TIER_PROVIDER = {
    1: os.getenv("LUMINA_PROVIDER_TIER1", "local"),
    2: os.getenv("LUMINA_PROVIDER_TIER2", "local"),
    # Keep tier-3 default local to preserve offline-first and existing test expectations.
    3: os.getenv("LUMINA_PROVIDER_TIER3", os.getenv("LUMINA_PROVIDER_DEFAULT", "local")),
}

# Known provider -> typical API key env var mapping
PROVIDER_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
}


def resolve_provider_for_slice(task_slice: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve which provider should be used for a given TaskSlice.

    Returns a dict with keys: `provider` (str), `api_key_env` (str|None), `requires_api_key` (bool).
    This is intentionally conservative: if env configuration disallows cloud providers,
    callers should call `is_provider_allowed` to confirm.
    """
    try:
        tier = int(task_slice.get("tier", 3))
    except Exception:
        tier = 3

    provider = DEFAULT_TIER_PROVIDER.get(tier) or DEFAULT_TIER_PROVIDER.get(3) or "local"
    api_key_env = PROVIDER_API_KEY_ENV.get(provider)
    requires_api_key = api_key_env is not None and provider != "local"
    return {"provider": provider, "api_key_env": api_key_env, "requires_api_key": requires_api_key}


def is_provider_allowed(provider: str, task_slice: Dict[str, Any] | None = None) -> bool:
    """Return whether use of the given provider is allowed by local policy.

    Policy sources (in order of precedence):
    - If `LUMINA_ALLOW_CLOUD` is set to `false` (case-insensitive), cloud providers are disallowed.
    - `local` provider is always allowed.
    - Pack-level denies may be implemented in the future; for now callers can opt-out by
      setting `LUMINA_ALLOW_CLOUD=false`.
    """
    if not provider or provider == "local":
        return True

    allow_cloud = os.getenv("LUMINA_ALLOW_CLOUD", "true").lower()
    if allow_cloud in ("0", "false", "no"):
        return False

    # Default allow
    return True


def get_api_key_env_for(provider: str) -> str | None:
    return PROVIDER_API_KEY_ENV.get(provider)
