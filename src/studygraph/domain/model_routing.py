"""模型路由（Model Routing）：按请求复杂度/成本选择模型档位（纯函数）。

依据 Super Agent System 等设计：用"小模型跑简单意图、大模型接复杂请求"来省成本、
控延迟（OpenAI 指南也建议用更小的模型替换大模型做成本优化）。
"""

from __future__ import annotations

_SMALL_INTENTS = {"calculation", "smalltalk"}
_LARGE_LENGTH = 60


def model_tier(intent: str, text: str) -> str:
    """返回 "small" / "standard" / "large"。"""

    if intent in _SMALL_INTENTS:
        return "small"
    if len((text or "").strip()) > _LARGE_LENGTH:
        return "large"
    return "standard"
