"""Tests for lumina.core.slm_ppa_worker — async SLM PPA enrichment worker.

Covers lifecycle (start/stop/is_running), enrichment dispatch, and
graceful shutdown via sentinel.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumina.core.slm_ppa_worker import (
    EnrichmentKind,
    EnrichmentRequest,
    enqueue,
    is_running,
    start,
    stop,
)


def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)


def _reset_worker():
    """Reset worker module-level state between tests."""
    import lumina.core.slm_ppa_worker as w
    w._running = False
    w._worker_task = None
    w._queue = asyncio.Queue()


# ── Lifecycle ─────────────────────────────────────────────────────────────────


class TestWorkerLifecycle:

    @pytest.mark.unit
    def test_start_sets_running(self) -> None:
        async def _test():
            _reset_worker()
            await start()
            assert is_running()
            await stop()
            assert not is_running()
        _run(_test())

    @pytest.mark.unit
    def test_duplicate_start_is_noop(self) -> None:
        async def _test():
            import lumina.core.slm_ppa_worker as w
            _reset_worker()
            await start()
            task1 = w._worker_task
            await start()  # duplicate — should be no-op
            assert w._worker_task is task1
            await stop()
        _run(_test())

    @pytest.mark.unit
    def test_stop_without_start_is_safe(self) -> None:
        async def _test():
            _reset_worker()
            await stop()  # should not raise
        _run(_test())


# ── Enrichment Dispatch ───────────────────────────────────────────────────────


class TestEnrichmentDispatch:

    @pytest.mark.unit
    def test_physics_enrichment(self) -> None:
        async def _test():
            _reset_worker()
            with patch(
                "lumina.core.slm_ppa_worker._enrich_physics",
                new_callable=AsyncMock,
                return_value={"matched_invariants": ["inv1"]},
            ) as mock_physics:
                await start()
                result = await enqueue(
                    EnrichmentKind.PHYSICS_CONTEXT,
                    {"incoming_signals": {"x": 1}, "domain_physics": {}},
                )
                assert result == {"matched_invariants": ["inv1"]}
                mock_physics.assert_awaited_once()
                await stop()
        _run(_test())

    @pytest.mark.unit
    def test_command_enrichment(self) -> None:
        async def _test():
            _reset_worker()
            with patch(
                "lumina.core.slm_ppa_worker._enrich_command",
                new_callable=AsyncMock,
                return_value={"operation": "update_domain_physics", "target": "t", "params": {}},
            ) as mock_cmd:
                await start()
                result = await enqueue(
                    EnrichmentKind.COMMAND_PARSE,
                    {"natural_language": "update something"},
                )
                assert result is not None
                assert result["operation"] == "update_domain_physics"
                mock_cmd.assert_awaited_once()
                await stop()
        _run(_test())

    @pytest.mark.unit
    def test_enrichment_failure_propagates(self) -> None:
        async def _test():
            _reset_worker()
            with patch(
                "lumina.core.slm_ppa_worker._enrich_physics",
                new_callable=AsyncMock,
                side_effect=RuntimeError("SLM unavailable"),
            ):
                await start()
                with pytest.raises(RuntimeError, match="SLM unavailable"):
                    await enqueue(
                        EnrichmentKind.PHYSICS_CONTEXT,
                        {"incoming_signals": {}, "domain_physics": {}},
                    )
                await stop()
        _run(_test())


# ── EnrichmentRequest ─────────────────────────────────────────────────────────


class TestEnrichmentRequest:

    @pytest.mark.unit
    def test_request_has_future(self) -> None:
        async def _test():
            req = EnrichmentRequest(
                kind=EnrichmentKind.PHYSICS_CONTEXT,
                payload={"incoming_signals": {}, "domain_physics": {}},
            )
            assert isinstance(req.future, asyncio.Future)
        _run(_test())

    @pytest.mark.unit
    def test_enrichment_kind_values(self) -> None:
        assert EnrichmentKind.PHYSICS_CONTEXT.value == "physics_context"
        assert EnrichmentKind.COMMAND_PARSE.value == "command_parse"


# ── Log Bus Event Emission ────────────────────────────────────────────────────


class TestWorkerEventEmission:
    """Verify that the SLM PPA worker emits events to the log bus."""

    @pytest.mark.unit
    def test_emits_info_on_success(self) -> None:
        from lumina.system_log.event_payload import LogLevel
        import lumina.system_log.log_bus as bus

        received = []

        async def _test():
            _reset_worker()
            bus._running = False
            bus._task = None
            bus._queue = asyncio.Queue()
            bus._subscriptions.clear()

            bus.subscribe(lambda e: received.append(e), level_filter=[LogLevel.INFO])
            await bus.start()

            with patch(
                "lumina.core.slm_ppa_worker._enrich_physics",
                new_callable=AsyncMock,
                return_value={"matched_invariants": []},
            ):
                await start()
                await enqueue(
                    EnrichmentKind.PHYSICS_CONTEXT,
                    {"incoming_signals": {}, "domain_physics": {}},
                )
                await asyncio.sleep(0.05)
                await stop()

            await bus.stop()

        _run(_test())
        info_events = [e for e in received if e.source == "slm_ppa_worker"]
        assert len(info_events) >= 1
        assert info_events[0].category == "inference_parsing"

    @pytest.mark.unit
    def test_emits_warning_on_failure(self) -> None:
        from lumina.system_log.event_payload import LogLevel
        import lumina.system_log.log_bus as bus

        received = []

        async def _test():
            _reset_worker()
            bus._running = False
            bus._task = None
            bus._queue = asyncio.Queue()
            bus._subscriptions.clear()

            bus.subscribe(lambda e: received.append(e), level_filter=[LogLevel.WARNING])
            await bus.start()

            with patch(
                "lumina.core.slm_ppa_worker._enrich_physics",
                new_callable=AsyncMock,
                side_effect=RuntimeError("SLM down"),
            ):
                await start()
                with pytest.raises(RuntimeError):
                    await enqueue(
                        EnrichmentKind.PHYSICS_CONTEXT,
                        {"incoming_signals": {}, "domain_physics": {}},
                    )
                await asyncio.sleep(0.05)
                await stop()

            await bus.stop()

        _run(_test())
        warn_events = [e for e in received if e.source == "slm_ppa_worker"]
        assert len(warn_events) >= 1
        assert "SLM down" in warn_events[0].message
b

# ── is_running before start ───────────────────────────────────────────────────


class TestIsRunning:

    @pytest.mark.unit
    def test_is_running_returns_false_before_start(self) -> None:
        _reset_worker()
        assert not is_running()


# ── _dispatch internals ───────────────────────────────────────────────────────


class TestDispatch:
    """Direct unit tests for _dispatch, _enrich_physics, _enrich_command."""

    @pytest.mark.unit
    def test_unknown_kind_raises_value_error(self) -> None:
        import lumina.core.slm_ppa_worker as w

        async def _test():
            loop = asyncio.get_running_loop()
            req = EnrichmentRequest(
                kind="not_a_real_kind",  # type: ignore[arg-type]
                payload={},
                future=loop.create_future(),
            )
            with pytest.raises(ValueError, match="Unknown enrichment kind"):
                await w._dispatch(req)

        _run(_test())

    @pytest.mark.unit
    def test_enrich_physics_passes_all_args_to_slm(self) -> None:
        import lumina.core.slm_ppa_worker as w

        captured: dict = {}

        def fake_physics(incoming_signals, domain_physics, glossary=None, actor_input=None):
            captured["incoming_signals"] = incoming_signals
            captured["domain_physics"] = domain_physics
            captured["glossary"] = glossary
            captured["actor_input"] = actor_input
            return {"matched_invariants": ["inv-x"]}

        async def _test():
            with patch("lumina.core.slm.slm_interpret_physics_context", fake_physics):
                result = await w._enrich_physics({
                    "incoming_signals": {"sig": 42},
                    "domain_physics": {"id": "dom"},
                    "glossary": [{"term": "eigenvalue"}],
                    "actor_input": "test input",
                })
            assert result == {"matched_invariants": ["inv-x"]}

        _run(_test())
        assert captured["incoming_signals"] == {"sig": 42}
        assert captured["domain_physics"] == {"id": "dom"}
        assert captured["glossary"] == [{"term": "eigenvalue"}]
        assert captured["actor_input"] == "test input"

    @pytest.mark.unit
    def test_enrich_physics_optional_args_default_to_none(self) -> None:
        import lumina.core.slm_ppa_worker as w

        captured: dict = {}

        def fake_physics(incoming_signals, domain_physics, glossary=None, actor_input=None):
            captured["glossary"] = glossary
            captured["actor_input"] = actor_input
            return {}

        async def _test():
            with patch("lumina.core.slm.slm_interpret_physics_context", fake_physics):
                await w._enrich_physics({
                    "incoming_signals": {},
                    "domain_physics": {},
                    # glossary and actor_input omitted
                })

        _run(_test())
        assert captured["glossary"] is None
        assert captured["actor_input"] is None

    @pytest.mark.unit
    def test_enrich_command_passes_available_operations(self) -> None:
        import lumina.core.slm_ppa_worker as w

        captured: dict = {}

        def fake_parse(natural_language, available_operations=None):
            captured["natural_language"] = natural_language
            captured["available_operations"] = available_operations
            return {"operation": "add_module", "target": "x", "params": {}}

        async def _test():
            with patch("lumina.core.slm.slm_parse_admin_command", fake_parse):
                result = await w._enrich_command({
                    "natural_language": "add module X",
                    "available_operations": ["add_module", "remove_module"],
                })
            assert result["operation"] == "add_module"

        _run(_test())
        assert captured["natural_language"] == "add module X"
        assert captured["available_operations"] == ["add_module", "remove_module"]

    @pytest.mark.unit
    def test_enrich_command_optional_operations_defaults_to_none(self) -> None:
        import lumina.core.slm_ppa_worker as w

        captured: dict = {}

        def fake_parse(natural_language, available_operations=None):
            captured["available_operations"] = available_operations
            return None

        async def _test():
            with patch("lumina.core.slm.slm_parse_admin_command", fake_parse):
                await w._enrich_command({"natural_language": "do something"})

        _run(_test())
        assert captured["available_operations"] is None


# ── Multiple enqueues ─────────────────────────────────────────────────────────


class TestMultipleEnqueues:

    @pytest.mark.unit
    def test_multiple_sequential_enqueues_all_resolve(self) -> None:
        async def _test():
            _reset_worker()
            call_count = 0

            async def fake_physics(payload):
                nonlocal call_count
                call_count += 1
                return {"n": call_count}

            with patch(
                "lumina.core.slm_ppa_worker._enrich_physics",
                new_callable=AsyncMock,
                side_effect=[{"n": 1}, {"n": 2}, {"n": 3}],
            ):
                await start()
                r1 = await enqueue(EnrichmentKind.PHYSICS_CONTEXT, {"incoming_signals": {}, "domain_physics": {}})
                r2 = await enqueue(EnrichmentKind.PHYSICS_CONTEXT, {"incoming_signals": {}, "domain_physics": {}})
                r3 = await enqueue(EnrichmentKind.PHYSICS_CONTEXT, {"incoming_signals": {}, "domain_physics": {}})
                await stop()

            assert r1 == {"n": 1}
            assert r2 == {"n": 2}
            assert r3 == {"n": 3}

        _run(_test())
