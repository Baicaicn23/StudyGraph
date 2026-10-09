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

# 出题难度三档：与"记忆 / 应用 / 迁移"的梯度主张一一对应。
DIFFICULTIES = ("basic", "apply", "transfer")
DIFFICULTY_LABELS = {
    "basic": "基础",
    "apply": "进阶",
    "transfer": "迁移",
}
# 每档给模型的出题要求（拼进出题指令与 system prompt）。
DIFFICULTY_GUIDES = {
    "basic": "难度【基础】：直接考察资料里的概念定义与核心关系，"
    "让学习者复述、辨认或解释，不绕弯、不设陷阱。",
    "apply": "难度【进阶】：给出一个具体情境或数字，让学习者把概念用上去"
    "解决一个小问题，不能只靠复述原文作答。",
    "transfer": "难度【迁移】：把概念换到一个资料里没有出现过的情境，"
    "考察学习者能否举一反三；允许一定开放性，但题面要求必须清晰。",
}


def normalize_difficulty(value: str) -> str | None:
    """校验并归一难度值；非法返回 None。"""

    cleaned = str(value or "").strip().lower()
    return cleaned if cleaned in DIFFICULTIES else None


def difficulty_sentence(difficulty: str) -> str:
    label = DIFFICULTY_LABELS.get(difficulty, difficulty)
    guide = DIFFICULTY_GUIDES.get(difficulty, "")
    return f"出题难度：{label}。{guide}"


@dataclass(frozen=True)
class WrittenQuestion:
    prompt: str
    generator: str  # "model" | "template"


def template_excerpt_question(excerpt: str, difficulty: str = "apply") -> str:
    label = DIFFICULTY_LABELS.get(difficulty, "进阶")
    if difficulty == "basic":
        body = (
            "请用自己的话解释下面这段资料。回答时说明核心概念、"
            "关键关系和一个具体例子。"
        )
    elif difficulty == "transfer":
        body = (
            "请把下面这段资料里的核心概念用到资料没有出现过的情境中，"
            "举一个你自己的例子，并说明它为什么成立。"
        )
    else:
        body = (
            "请结合一个具体情境应用下面这段资料：说明在什么场景会遇到它、"
            "怎么用它解决一个小问题。"
        )
    return f"【难度：{label}】{body}\n\n资料摘录：\n「{excerpt}」"


def template_mistake_question(
    *, question: str, note: str, difficulty: str = "apply"
) -> str:
    label = DIFFICULTY_LABELS.get(difficulty, "进阶")
    parts = [
        f"【难度：{label}】你之前在这一块卡过。现在不看资料、也不看当时的答案，"
        "重新独立做一遍。"
    ]
    if str(question or "").strip():
        parts.append(f"【当时的问题】\n{question.strip()}")
    if str(note or "").strip():
        parts.append(f"【你当时记下的误区】\n{note.strip()}")
    parts.append("先写出你的完整思路，再对照检查卡在哪一步。")
    return "\n\n".join(parts)


def build_excerpt_instruction(excerpt: str, difficulty: str = "apply") -> str:
    return (
        f"资料摘录：\n{excerpt}\n\n"
        f"{difficulty_sentence(difficulty)}\n\n"
        "请根据这段资料出一道新题：考察资料里的核心概念或关键关系，"
        "要求学习者自己组织答案，而不是照抄原文。"
    )


def build_mistake_instruction(
    *, subject: str, question: str, note: str, difficulty: str = "apply"
) -> str:
    lines: list[str] = []
    if str(subject or "").strip():
        lines.append(f"学科：{subject.strip()}")
    if str(question or "").strip():
        lines.append(f"学习者当时问的问题：{question.strip()}")
    if str(note or "").strip():
        lines.append(f"学习者自己记下的误区：{note.strip()}")
    lines.append(f"{difficulty_sentence(difficulty)}")
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
