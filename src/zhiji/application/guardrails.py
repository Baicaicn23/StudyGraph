"""护栏的编排：把领域层检查组装成"拒绝话术 / 警告原因"。

接口层（API / CLI）在调用图之前 `screen_input`，在拿到最终回答之后 `screen_output`。
"""

from __future__ import annotations

from ..domain.guardrails import check_input, check_output

_INPUT_REFUSAL = "抱歉，这条请求被安全策略拦截：{reason}。换个方式再试试？"


def screen_input(text: str) -> str | None:
    """返回拒绝话术；通过则返回 None。"""

    result = check_input(text)
    if result.allowed:
        return None
    return _INPUT_REFUSAL.format(reason=result.reason)


def screen_output(text: str) -> str | None:
    """返回警告原因（回答需要复核）；通过则返回 None。"""

    result = check_output(text)
    return None if result.allowed else result.reason
