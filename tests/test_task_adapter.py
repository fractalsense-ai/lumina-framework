"""Tests for lumina.daemon.task_adapter."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lumina.daemon.preemption import PreemptionToken, TaskPreempted
from lumina.daemon.task_adapter import run_task_preemptible
from lumina.daemon.report import TaskResult


# ── Helpers ───────────────────────────────────────────────────────────────────


def _dummy_task(domain_id: str, domain_physics: dict, persistence=None, call_slm_fn=None) -> TaskResult:
    return TaskResult(task="dummy", domain_id=domain_id, success=True)


def _failing_task(domain_id: str, domain_physics: dict, persistence=None, call_slm_fn=None) -> TaskResult:
    raise RuntimeError("boom")


# ── Basic execution ───────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_task_single_domain() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_task", return_value=_dummy_task):
        result = await run_task_preemptible("dummy", token)

    assert result["task"] == "dummy"
    assert result["preempted"] is False
    assert result["completed_domains"] == 1
    assert result["total_domains"] == 1


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_task_multiple_domains() -> None:
    token = PreemptionToken()
    domains = [
        {"domain_id": "d1", "physics": {}},
        {"domain_id": "d2", "physics": {}},
    ]
    with patch("lumina.daemon.task_adapter.get_task", return_value=_dummy_task):
        result = await run_task_preemptible(
            "dummy", token, domain_loader=lambda: domains,
        )

    assert result["completed_domains"] == 2
    assert result["total_domains"] == 2
    assert result["preempted"] is False


# ── Unknown task ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_unknown_task() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_task", return_value=None):
        result = await run_task_preemptible("nonexistent", token)

    assert "error" in result
    assert result["completed_domains"] == 0


# ── Preemption mid-task ──────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_preemption_before_second_domain() -> None:
    """Token yields before the second domain is processed."""
    token = PreemptionToken()
    domains = [
        {"domain_id": "d1", "physics": {}},
        {"domain_id": "d2", "physics": {}},
        {"domain_id": "d3", "physics": {}},
    ]
    call_count = 0

    def _counting_task(domain_id, domain_physics, persistence=None, call_slm_fn=None):
        nonlocal call_count
        call_count += 1
        return TaskResult(task="counting", domain_id=domain_id, success=True)

    # Request yield after first domain completes
    original_checkpoint = token.checkpoint_sync
    check_calls = 0

    def _yielding_checkpoint():
        nonlocal check_calls
        check_calls += 1
        if check_calls >= 2:  # yield before 2nd domain
            raise TaskPreempted("test")
        original_checkpoint()

    token.checkpoint_sync = _yielding_checkpoint  # type: ignore[assignment]

    with patch("lumina.daemon.task_adapter.get_task", return_value=_counting_task):
        result = await run_task_preemptible(
            "counting", token, domain_loader=lambda: domains,
        )

    assert result["preempted"] is True
    assert result["completed_domains"] == 1  # only first domain
    assert result["total_domains"] == 3


# ── Task failure ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_task_failure_captured() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_task", return_value=_failing_task):
        result = await run_task_preemptible("failing", token)

    assert result["completed_domains"] == 1  # error result still counted
    assert result["results"][0]["success"] is False
    assert "boom" in result["results"][0]["error"]


# ── run_cross_domain_task_preemptible ─────────────────────────────────────────

from lumina.daemon.task_adapter import run_cross_domain_task_preemptible


def _cross_domain_task(domains, **kw):
    return {"processed": len(domains)}


def _cross_domain_task_result(domains, **kw):
    return TaskResult(task="cross_domain", domain_id="all", success=True)


def _failing_cross_domain_task(domains, **kw):
    raise RuntimeError("cross-domain boom")


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_cross_domain_task_unknown() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_cross_domain_task", return_value=None):
        result = await run_cross_domain_task_preemptible("unknown_cross", token)

    assert "error" in result
    assert result["preempted"] is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_cross_domain_task_success() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_cross_domain_task",
               return_value=_cross_domain_task):
        result = await run_cross_domain_task_preemptible("cross_domain", token)

    assert result["preempted"] is False
    assert result["results"] is not None


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_cross_domain_task_task_result_wrapping() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_cross_domain_task",
               return_value=_cross_domain_task_result):
        result = await run_cross_domain_task_preemptible("cross_domain", token)

    assert result["preempted"] is False
    assert len(result["results"]) == 1


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_cross_domain_task_preempted() -> None:
    token = PreemptionToken()

    def _preempting_checkpoint():
        raise TaskPreempted("test")

    token.checkpoint_sync = _preempting_checkpoint  # type: ignore[assignment]
    with patch("lumina.daemon.task_adapter.get_cross_domain_task",
               return_value=_cross_domain_task):
        result = await run_cross_domain_task_preemptible("cross_domain", token)

    assert result["preempted"] is True


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_cross_domain_task_failure() -> None:
    token = PreemptionToken()
    with patch("lumina.daemon.task_adapter.get_cross_domain_task",
               return_value=_failing_cross_domain_task):
        result = await run_cross_domain_task_preemptible("cross_domain", token)

    assert result["preempted"] is False
    assert "error" in result


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_cross_domain_task_task_preempted_internally() -> None:
    """TaskPreempted raised inside the task function."""
    token = PreemptionToken()

    def _task_raises_preempted(domains, **kw):
        raise TaskPreempted("inside task")

    with patch("lumina.daemon.task_adapter.get_cross_domain_task",
               return_value=_task_raises_preempted):
        result = await run_cross_domain_task_preemptible("cross_domain", token)

    assert result["preempted"] is True


@pytest.mark.unit
@pytest.mark.anyio
async def test_run_task_result_dict_pass_through() -> None:
    """When task returns a plain dict (not TaskResult), a success entry is recorded."""
    token = PreemptionToken()

    def _plain_dict_task(domain_id, domain_physics, persistence=None, call_slm_fn=None):
        return {"custom": "output", "domain_id": domain_id}

    with patch("lumina.daemon.task_adapter.get_task", return_value=_plain_dict_task):
        result = await run_task_preemptible("plain_dict", token)

    assert result["completed_domains"] == 1
    # Non-TaskResult returns are wrapped with a success=True entry
    assert result["results"][0]["success"] is True
