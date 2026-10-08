"""用模型写练习题（失败/无模型一律回退模板）。

结构照搬意图识别那一层：提示词是纯函数、要求模型返回结构化 JSON、**任何失败都
回退模板**。"出题"是用户主动发起的动作，不能因为模型不可用而失败——所以调用方
不需要处理异常，模板题照样能用。

Mock 模型直接走模板（它的输出不遵循本模块的 JSON 约定，问它没有信息量）。
要覆盖模型路径，请在测试里用一个自定义的假模型。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

MAX_INSTRUCTION_CHARS = 1200
MIN_QUESTION_CHARS = 8
MAX_QUESTION_CHARS = 600

_SYSTEM_PROMPT = (
    "你是一位出题教练，为一位大学生出一道练习题。"
    "只输出 JSON，不要解释、不要 markdown 代码块，格式为："
    '{"question": "题目正文"}。'
    "题面要自成一体（学习者不看资料也能作答），简体中文，"
    "数学式子用纯文本写清楚，不要给出答案或解题步骤，题面不超过 200 字。"
)


@dataclass(frozen=True)
class WrittenQuestion:
    prompt: str
    generator: str  # "model" | "template"


def template_excerpt_question(excerpt: str) -> str:
    return (
        "请用自己的话解释下面这段资料。回答时说明核心概念、"
        "关键关系和一个具体例子。\n\n"
        f"资料摘录：\n「{excerpt}」"
    )


def template_mistake_question(*, question: str, note: str) -> str:
    parts = ["你之前在这一块卡过。现在不看资料、也不看当时的答案，重新独立做一遍。"]
    if str(question or "").strip():
        parts.append(f"【当时的问题】\n{question.strip()}")
    if str(note or "").strip():
        parts.append(f"【你当时记下的误区】\n{note.strip()}")
    parts.append("先写出你的完整思路，再对照检查卡在哪一步。")
    return "\n\n".join(parts)


def build_excerpt_instruction(excerpt: str) -> str:
    return (
        f"资料摘录：\n{excerpt}\n\n"
        "请根据这段资料出一道新题：考察资料里的核心概念或关键关系，"
        "要求学习者自己组织答案，而不是照抄原文。"
    )


def build_mistake_instruction(*, subject: str, question: str, note: str) -> str:
    lines: list[str] = []
    if str(subject or "").strip():
        lines.append(f"学科：{subject.strip()}")
    if str(question or "").strip():
        lines.append(f"学习者当时问的问题：{question.strip()}")
    if str(note or "").strip():
        lines.append(f"学习者自己记下的误区：{note.strip()}")
    lines.append(
        "请针对这个误区出一道新题：考察同一个知识点，但换个问法或换组数字，"
        "让学习者能自己验证是不是真的弄懂了。"
    )
    return "\n".join(lines)


def parse_question(content: str) -> str | None:
    """解析模型返回的 JSON 题面；格式/取值非法或明显敷衍时返回 None。"""

    text = str(content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    question = " ".join(str(payload.get("question") or "").split())
    if len(question) < MIN_QUESTION_CHARS:
        return None
    return question[:MAX_QUESTION_CHARS]


async def write_question(
    model: Any | None, instruction: str, *, fallback: str
) -> WrittenQuestion:
    """先让模型写题，失败或没有可用模型就用 ``fallback``。本函数永不抛异常。"""

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
