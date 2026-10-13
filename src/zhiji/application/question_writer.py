""""让模型写题，失败回退模板"——应用层编排。

提示词与解析属于领域规则（`domain/quiz.py`），这里只负责：调用（端口注入的）
模型、解析结果、任何失败都退回模板。**永不抛异常**，所以调用方不需要处理。

详解（`write_explanation`）是例外：**没有模板可退**——答案对错由学科事实决定，
拼不出来。拿不到就返回 None，由调用方诚实告知用户。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from ..domain.quiz import (
    MAX_INSTRUCTION_CHARS,
    WrittenExplanation,
    WrittenQuestion,
    parse_explanation,
    parse_question,
)
from .json_mode import invoke_json
from .ports import ChatModelPort

_SYSTEM_PROMPT = (
    "你是一位出题教练，为一位大学生出一道练习题。"
    "严格遵守用户消息里给出的【难度】要求——难度决定考察方式，不只是措辞。"
    "只输出 JSON，不要解释、不要 markdown 代码块，格式为："
    '{"question": "题目正文"}。'
    "题面要自成一体（学习者不看资料也能作答），简体中文，"
    "数学式子用纯文本写清楚，不要给出答案或解题步骤，题面不超过 200 字。"
)

_EXPLANATION_SYSTEM_PROMPT = (
    "你是一位学科老师，为学生刚做的一道练习题写参考答案与关键步骤。"
    "只输出 JSON，不要解释、不要 markdown 代码块，格式为："
    '{"answer": "参考答案", "steps": ["关键步骤一", "关键步骤二"]}。'
    "answer 结论先行、两三句话就能对照判断对错（有数值/结论的必须写明确）；"
    "steps 写 2 到 5 条，每条一句话说明决定得分的依据与理由，"
    "不要复述题目、不要写鼓励或提醒的话。全部用简体中文，"
    "数学式子写成纯文本。"
)


async def write_question(
    model: ChatModelPort | None, instruction: str, *, fallback: str
) -> WrittenQuestion:
    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return WrittenQuestion(prompt=fallback, generator="template")
    try:
        response = await invoke_json(
            model,
            [
                SystemMessage(_SYSTEM_PROMPT),
                HumanMessage(instruction[:MAX_INSTRUCTION_CHARS]),
            ],
        )
        question = parse_question(getattr(response, "content", ""))
    except Exception:  # noqa: BLE001 — 出题失败绝不阻塞，退回模板
        return WrittenQuestion(prompt=fallback, generator="template")
    if question is None:
        return WrittenQuestion(prompt=fallback, generator="template")
    return WrittenQuestion(prompt=question, generator="model")


async def write_explanation(
    model: ChatModelPort | None, instruction: str
) -> WrittenExplanation | None:
    """让模型写详解；Mock 模式 / 调用失败 / 解析不合法一律返回 None。

    返回 None 是**有意**的：详解没有模板兜底（编不出来），调用方应把它翻译成
    「需要真实模型」或「稍后重试」这类可读提示，而不是塞一段假解析给用户。
    """

    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return None
    try:
        response = await invoke_json(
            model,
            [
                SystemMessage(_EXPLANATION_SYSTEM_PROMPT),
                HumanMessage(instruction[:MAX_INSTRUCTION_CHARS]),
            ],
        )
    except Exception:  # noqa: BLE001 — 调用失败即"没拿到详解"，由调用方提示
        return None
    return parse_explanation(getattr(response, "content", ""))
