""""让模型写题，失败回退模板"——应用层编排。

提示词与解析属于领域规则（`domain/quiz.py`），这里只负责：调用（端口注入的）
模型、解析结果、任何失败都退回模板。**永不抛异常**，所以调用方不需要处理。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..domain.quiz import (
    MAX_INSTRUCTION_CHARS,
    WrittenQuestion,
    parse_question,
)
from .ports import ChatModelPort

_SYSTEM_PROMPT = (
    "你是一位出题教练，为一位大学生出一道练习题。"
    "只输出 JSON，不要解释、不要 markdown 代码块，格式为："
    '{"question": "题目正文"}。'
    "题面要自成一体（学习者不看资料也能作答），简体中文，"
    "数学式子用纯文本写清楚，不要给出答案或解题步骤，题面不超过 200 字。"
)


async def write_question(
    model: ChatModelPort | None, instruction: str, *, fallback: str
) -> WrittenQuestion:
    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return WrittenQuestion(prompt=fallback, generator="template")
    try:
        response = await model.ainvoke(
            [
                SystemMessage(_SYSTEM_PROMPT),
                HumanMessage(instruction[:MAX_INSTRUCTION_CHARS]),
            ]
        )
        question = parse_question(getattr(response, "content", ""))
    except Exception:  # noqa: BLE001 — 出题失败绝不阻塞，退回模板
        return WrittenQuestion(prompt=fallback, generator="template")
    if question is None:
        return WrittenQuestion(prompt=fallback, generator="template")
    return WrittenQuestion(prompt=question, generator="model")
