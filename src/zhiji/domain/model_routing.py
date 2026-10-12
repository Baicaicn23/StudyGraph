"""模型路由（Model Routing）：按请求复杂度/成本选择模型档位（纯函数）。

依据 Super Agent System 等设计：用"小模型跑简单意图、大模型接复杂请求"来省成本、
控延迟（OpenAI 指南也建议用更小的模型替换大模型做成本优化）。
"""

from __future__ import annotations

_SMALL_INTENTS = {"calculation", "smalltalk"}
_THINKING_INTENTS = {"concept_explain", "practice"}
_LARGE_LENGTH = 60


def model_tier(intent: str, text: str) -> str:
    """返回 "small" / "standard" / "large"。"""

    if intent in _SMALL_INTENTS:
        return "small"
    if len((text or "").strip()) > _LARGE_LENGTH:
        return "large"
    return "standard"


def thinking_level(intent: str, text: str) -> str | None:
    """轮级思考档位（架构位）→ "off" / "low" / "high" / "max" / None。

    实测（DeepSeek V4.1-Flash）：有效控制轴是 thinking 开/关（disabled 后
    思考 token 归零），reasoning_effort 分档对该模型无效。因此自动策略取
    两端：轻意图（计算/闲聊）关思考省时省钱，重思考意图（讲解/出题/长文本）
    开思考保质量，中间档 None 交给模型默认。是否真正附加由 llm 层按
    provider 决定（DeepSeek 用 thinking 开关，GLM 用开关 + effort 分档）。
    """

    if intent in _SMALL_INTENTS:
        return "off"
    if intent in _THINKING_INTENTS or len((text or "").strip()) > _LARGE_LENGTH:
        return "max"
    return None
