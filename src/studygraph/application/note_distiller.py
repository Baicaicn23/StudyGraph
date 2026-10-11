"""「智能沉淀」：把一段对话回复提炼成独立的学习笔记。

加入知识库的消息操作不再原文转存——回复里的苏格拉底提问、引导语、
过渡寒暄对复习毫无价值。这里用模型按 `domain/note_style` 规范提炼；
只有真的没有知识内容可沉淀时才明确报错（NoteDistillError），
让前端提示用户"等讲完再存"，而不是硬把半截对话塞进知识库。
模型不可用（Mock / None）时退回原文转存（generator="raw"），
行为与旧版一致，也不消耗额度。
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from ..domain.note_style import NOTE_STYLE_GUIDE
from .ports import ChatModelPort


class NoteDistillError(ValueError):
    """这段回复里没有足够的知识内容可以沉淀。"""


_MAX_REPLY_CHARS = 6000
_MIN_NOTE_CHARS = 60


def _fallback_title(question: str) -> str:
    question = question.strip().replace("\n", " ")
    if not question:
        return "对话沉淀"
    return question[:30] + ("…" if len(question) > 30 else "")


def _clean_note_text(text: str) -> str:
    text = text.strip()
    # 剥掉 markdown 代码围栏（可能出现在标题行之后，用多行模式逐行匹配）
    text = re.sub(r"^```(?:markdown|md)?\s*$", "", text, flags=re.M)
    text = re.sub(r"^```\s*$", "", text, flags=re.M)
    return text.strip()


def _split_title(content: str, fallback: str) -> tuple[str, str]:
    """标题来源：第一行「标题：xxx」或「# xxx」；正文去掉重复的 H1。"""

    lines = content.split("\n")
    title = fallback
    body_start = 0
    first = lines[0].strip() if lines else ""
    meta = re.match(r"^标题[:：]\s*(.+)$", first)
    if meta:
        title = meta.group(1).strip()
        body_start = 1
    elif first.startswith("# "):
        title = first[2:].strip()
        body_start = 1
    body = "\n".join(lines[body_start:]).strip()
    if body.startswith("# "):
        # 模型在正文里重复了 H1 标题 → 去掉（doc 阅读器会单独渲染标题）
        body = re.sub(r"^#\s+.+\n+", "", body)
    # 正文任何位置重复的 H1（含标题）也去掉——阅读器会单独渲染标题
    body = re.sub(rf"^#\s+.*{re.escape(title)}.*$", "", body, flags=re.M)
    return title, body.strip()


async def distill_note(
    model: ChatModelPort | None,
    *,
    question: str,
    reply: str,
) -> dict[str, str]:
    """把一段助手回复提炼成 {title, content, generator}。

    - generator="model"：模型提炼成功；
    - generator="raw"：模型不可用 / 调用失败 → 原文转存（与旧行为一致）；
    - 没有知识内容可沉淀 → NoteDistillError（前端提示等讲完再存）。
    """

    reply_text = (reply or "").strip()
    if not reply_text:
        raise NoteDistillError("回复内容为空，没有可沉淀的内容。")
    fallback_title = _fallback_title(question)

    # Mock / 未接模型：退回原文转存（与旧行为一致，不消耗额度）
    if model is None or getattr(model, "_llm_type", "") == "study-mock":
        return {
            "title": fallback_title,
            "content": reply_text[:2000],
            "generator": "raw",
        }

    instruction = (
        f"学生的原问题：\n{question[:1000]}\n\n"
        f"助手的回复（要提炼的素材）：\n{reply_text[:_MAX_REPLY_CHARS]}\n\n"
        "请把上面的回复提炼成一篇可以独立存在的 Markdown 学习笔记。"
    )
    system = (
        "你是笔记整理员，把教学对话里助手的回复提炼成学习笔记。"
        + NOTE_STYLE_GUIDE
        + "\n【提炼硬规则】\n"
        "一、只保留知识内容（定义 / 要点 / 例子 / 易错点 / 口语说法对照 / 结论）；\n"
        "二、删掉一切对话性内容：苏格拉底式提问、等待学生回答的话、过渡寒暄、\n"
        "对学生的称呼与鼓励、「我们先…」「你试试…」这类引导语；\n"
        "三、如果回复里纠正了学生的理解，保留纠正后的正确版本；\n"
        "四、回复里的知识不完整时，按你自己的知识把定义补完整（仍围绕同一主题），\n"
        "但不要引入回复完全没有提到的新主题；\n"
        "五、第一行输出「标题：xxx」（不加 #），空一行后输出笔记正文"
        "（正文以 H2 小节开始，不要再写 H1）；\n"
        "六、如果这段回复里根本没有足够的知识内容可以成文（例如只有开场白、\n"
        "反问学生、或纯计划安排），整个输出只写一个词：NONE。"
    )
    try:
        response = await model.ainvoke(
            [SystemMessage(system), HumanMessage(instruction)]
        )
        content = _clean_note_text(str(getattr(response, "content", "")))
    except Exception:  # noqa: BLE001 — 模型故障退回原文转存
        return {
            "title": fallback_title,
            "content": reply_text[:2000],
            "generator": "raw",
        }

    if not content or content.strip() in {"NONE", "无"}:
        raise NoteDistillError(
            "这轮回复还没有可以沉淀的知识内容（多半还在引导提问）——等讲解展开后再存。"
        )
    if len(content) < _MIN_NOTE_CHARS:
        raise NoteDistillError(
            "这段回复的知识密度太低，提炼不出像样的笔记——等讲解展开后再存。"
        )
    title, body = _split_title(content, fallback_title)
    if not body:
        raise NoteDistillError("提炼结果里没有正文。")
    return {"title": title, "content": body, "generator": "model"}
