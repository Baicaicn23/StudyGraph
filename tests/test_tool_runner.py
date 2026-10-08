from __future__ import annotations

import pytest

from studygraph.application.tool_runner import ToolTimeoutError, run_tool


async def test_run_tool_returns_result() -> None:
    async def ok(args: dict) -> str:
        return "结果"

    assert await run_tool(ok, {}) == "结果"


async def test_run_tool_retries_transient_errors_then_succeeds() -> None:
    calls = {"count": 0}

    async def flaky(args: dict) -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError
        return "成功"

    result = await run_tool(flaky, {}, retries=3, base_delay=0)
    assert result == "成功"
    assert calls["count"] == 3


async def test_run_tool_does_not_retry_value_errors() -> None:
    calls = {"count": 0}

    async def bad(args: dict) -> str:
        calls["count"] += 1
        raise ValueError("参数错误")

    with pytest.raises(ValueError):
        await run_tool(bad, {}, retries=3, base_delay=0)
    assert calls["count"] == 1


async def test_run_tool_gives_up_after_retries() -> None:
    calls = {"count": 0}

    async def always_timeout(args: dict) -> str:
        calls["count"] += 1
        raise TimeoutError

    with pytest.raises(ToolTimeoutError):
        await run_tool(always_timeout, {}, retries=2, base_delay=0)
    assert calls["count"] == 3
