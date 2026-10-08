"""出题的领域逻辑（纯函数）：提示词拼装、题面解析、模板兜底。

这里不碰任何模型调用——"让模型写题、失败回退"是应用层的编排（见
`application/question_writer.py`）。本模块只回答"该给模型什么要求""怎么判断它
答得合不合格""没有模型时怎么拼一道题"。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

MAX_INSTRUCTION_CHARS = 1200
MIN_QUESTION_CHARS = 8
MAX_QUESTION_CHARS = 600


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
