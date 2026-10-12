"""工具执行的可靠性：单次超时 + 有限次指数退避重试。

依据生产 Agent 的共识（工具调用是"手脚"，必须抗抖动）：
- **只对可重试错误重试**：超时、网络类（OSError/ConnectionError）。参数错误
  （ValueError 等）立即失败，重试没有意义。
- **有界**：总尝试次数有限，退避上限可控，避免把一次回合拖死。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class ToolTimeoutError(Exception):
    """单次工具执行超时。"""


async def run_tool(
    call: Callable[[dict[str, Any]], Awaitable[Any]],
    args: dict[str, Any],
    *,
    timeout: float = 10.0,
    retries: int = 2,
    base_delay: float = 0.1,
) -> Any:
    """执行工具；可重试错误按指数退避重试 ``retries`` 次后仍失败则抛出。"""

    last_error: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(call(args), timeout=timeout)
        except TimeoutError:
            last_error = ToolTimeoutError("工具执行超时")
        except (OSError, ConnectionError) as exc:
            last_error = exc
        if attempt < retries:
            await asyncio.sleep(base_delay * (2**attempt))
    assert last_error is not None
    raise last_error
