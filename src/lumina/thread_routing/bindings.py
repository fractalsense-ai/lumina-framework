"""Durable, scope-safe bindings between logical threads and runtime sessions."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ThreadSessionBinding:
    thread_id: str
    session_id: str
    organization_id: str
    site_id: str
    actor_id: str


def _state_key(thread_id: str, organization_id: str, site_id: str) -> str:
    payload = "\x1f".join((organization_id, site_id, thread_id)).encode("utf-8")
    return f"thread-binding-{hashlib.sha256(payload).hexdigest()}"


def _validate_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"thread binding requires {field_name}")
    return value.strip()


def load_thread_session_binding(
    persistence: Any,
    *,
    thread_id: str,
    organization_id: str,
    site_id: str,
) -> ThreadSessionBinding | None:
    """Load a binding, rejecting malformed or scope-inconsistent persisted state."""
    thread_id = _validate_identifier(thread_id, "thread_id")
    organization_id = _validate_identifier(organization_id, "organization_id")
    site_id = _validate_identifier(site_id, "site_id")
    state = persistence.load_session_state(_state_key(thread_id, organization_id, site_id))
    if state is None:
        return None
    required = ("thread_id", "session_id", "organization_id", "site_id", "actor_id")
    if not isinstance(state, dict) or any(not isinstance(state.get(key), str) or not state[key].strip() for key in required):
        raise ValueError("stored thread binding is invalid")
    binding = ThreadSessionBinding(**{key: state[key].strip() for key in required})
    if (
        binding.thread_id != thread_id
        or binding.organization_id != organization_id
        or binding.site_id != site_id
    ):
        raise ValueError("stored thread binding scope does not match its key")
    return binding


def create_thread_session_binding(
    persistence: Any,
    *,
    thread_id: str,
    session_id: str,
    organization_id: str,
    site_id: str,
    actor_id: str,
) -> ThreadSessionBinding:
    """Persist a new binding; conflicting reuse is forbidden rather than overwritten."""
    binding = ThreadSessionBinding(
        thread_id=_validate_identifier(thread_id, "thread_id"),
        session_id=_validate_identifier(session_id, "session_id"),
        organization_id=_validate_identifier(organization_id, "organization_id"),
        site_id=_validate_identifier(site_id, "site_id"),
        actor_id=_validate_identifier(actor_id, "actor_id"),
    )
    existing = load_thread_session_binding(
        persistence,
        thread_id=binding.thread_id,
        organization_id=binding.organization_id,
        site_id=binding.site_id,
    )
    if existing is not None:
        if existing != binding:
            raise ValueError("thread is already bound to a different session")
        return existing
    persistence.save_session_state(
        _state_key(binding.thread_id, binding.organization_id, binding.site_id),
        {
            "thread_id": binding.thread_id,
            "session_id": binding.session_id,
            "organization_id": binding.organization_id,
            "site_id": binding.site_id,
            "actor_id": binding.actor_id,
        },
    )
    return binding