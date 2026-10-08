"""规划的编排：先让模型出计划，失败回退规则计划（永不失败）。"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..domain.planning import fallback_plan, parse_plan
from .ports import ChatModelPort

_SYSTEM_PROMPT = (
    "你是学习任务的规划者。把用户的请求拆成 2~4 个可执行步骤。"
    "只输出 JSON 字符串数组，不要解释，例如："
    '["弄清问题", "回顾资料", "分步解答"]'
)


async def build_plan(model: ChatModelPort | None, request: str) -> list[str]:
    """返回执行计划；无模型或解析失败时用规则兜底。"""

    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return fallback_plan(request)
    try:
        response = await model.ainvoke(
            [SystemMessage(_SYSTEM_PROMPT), HumanMessage(request[:600])]
        )
        plan = parse_plan(getattr(response, "content", ""))
    except Exception:  # noqa: BLE001 - 规划失败不阻塞，退回规则计划
        plan = None
    return plan or fallback_plan(request)
