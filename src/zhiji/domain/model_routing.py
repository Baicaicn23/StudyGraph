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


def reasoning_effort(intent: str, text: str) -> str | None:
    """轮级推理力度（推理模型的 reasoning_effort 架构位）→ "low" / "max" / None。

    参考 GLM reasoning_effort 的分级思路：讲解/出题这类重思考意图拉满（max），
    计算/闲聊压到 low（快且省），中间档返回 None 交给模型自动判断。是否真正
    把该参数附到请求里，由基础设施层按 provider 白名单决定（非推理模型/不支持
    的服务商会拒绝该参数）。
    """

    if intent in _SMALL_INTENTS:
        return "low"
    if intent in _THINKING_INTENTS or len((text or "").strip()) > _LARGE_LENGTH:
        return "max"
    return None
