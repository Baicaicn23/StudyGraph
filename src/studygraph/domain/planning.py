"""规划（Planning）：把请求拆成可执行步骤（纯函数）。

依据业界共识（IBM / arXiv 综述把 planning 列为 Agent 核心模块；Anthropic 的
orchestrator-workers 即"先规划再执行"）。这里只放**规则**：判断请求是否需要规划、
没模型时的兜底计划、以及解析模型返回的计划。模型调用在应用层（`application/planner.py`）。
"""

from __future__ import annotations

import json
import re

MAX_STEPS = 5

_COMPLEX_MARKERS = ("一步步", "步骤", "分步", "规划", "制定", "计划", "系统性", "完整流程")
_SEQUENCE_MARKERS = ("先", "然后", "接着", "再", "最后")


def is_complex(text: str) -> bool:
    """是否需要"先规划再执行"。短请求默认不需要（保持低延迟、低成本）。"""

    content = (text or "").strip()
    if len(content) >= 40:
        return True
    if any(marker in content for marker in _COMPLEX_MARKERS):
        return True
    separators = content.count("，") + content.count(",")
    return separators >= 2 and any(marker in content for marker in _SEQUENCE_MARKERS)


def fallback_plan(request: str) -> list[str]:  # noqa: ARG001 - 保持与模型版同签名
    """没有模型时的兜底计划（确定、零成本）。"""

    return [
        "弄清问题：明确学习者到底想要什么",
        "回顾相关概念与已有资料",
        "分步给出解答或计划，并说明理由",
    ]


def parse_plan(content: str) -> list[str] | None:
    """解析模型返回的 JSON 字符串数组；非法则返回 None。"""

    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    steps = [str(item).strip() for item in payload if str(item).strip()]
    return steps[:MAX_STEPS] or None
