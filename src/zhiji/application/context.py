"""上下文工程：历史压缩（Anthropic《Effective context engineering》）。

对话变长后不把整段历史塞给模型，而是**保留最近的若干条**，更早的压成一段
**抽取式摘要**（从被丢弃的消息里摘首句，不做 LLM 生成——确定、零成本、可单测）。

为什么从"只报条数"改成"摘首句"：只写「已省略 N 条」等于把整段前情丢了，模型
在后续回合里会忘记"用户之前问过什么、结论是什么"，表现为反复问同一件事或
自相矛盾。抽取式摘要不引入模型调用，却把这部分信息留了下来。

关键：裁剪只从**整轮边界**（HumanMessage）开始，避免把"工具调用/工具结果"这对
消息拆散（拆散会让模型看到孤立的工具结果而报错）。
"""

from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

# 摘要里每条保留的字数 / 整段摘要的字数上限
_PER_ITEM_CHARS = 40
_SUMMARY_CHARS = 240
_SENTENCE_ENDINGS = ("。", "？", "！", "；", "\n")


def _first_sentence(text: str, limit: int = _PER_ITEM_CHARS) -> str:
    """取一段文本的首句（截到句末标点或字数上限），用于压缩成要点。"""

    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    for mark in _SENTENCE_ENDINGS:
        index = cleaned.find(mark)
        if 0 <= index < limit:
            return cleaned[: index + 1]
    return cleaned[:limit]


def _extractive_summary(dropped: list[BaseMessage]) -> str:
    """从被丢弃的消息里摘要点：最近 3 个提问 + 最后一处助手结论。

    只取"问过什么 / 结论是什么"，不复述中间的工具结果——工具细节对后续对话
    几乎无用，留着只会占额度。
    """

    questions = [
        _first_sentence(message.content)
        for message in dropped
        if isinstance(message, HumanMessage)
    ]
    answers = [
        _first_sentence(message.content)
        for message in dropped
        if isinstance(message, AIMessage)
        and not getattr(message, "tool_calls", None)
    ]
    questions = [item for item in questions if item]
    answers = [item for item in answers if item]

    parts: list[str] = []
    if questions:
        parts.append("用户先后问过：" + "；".join(questions[-3:]))
    if answers:
        parts.append("较早的助手结论：" + answers[-1])
    return "；".join(parts)[:_SUMMARY_CHARS]


def compact_messages(
    messages: list[BaseMessage], *, max_messages: int = 24, keep_recent: int = 14
) -> list[BaseMessage]:
    if len(messages) <= max_messages:
        return messages

    window = messages[-keep_recent:]
    for index, message in enumerate(window):
        if isinstance(message, HumanMessage):
            window = window[index:]
            break

    dropped_count = len(messages) - len(window)
    if dropped_count <= 0:
        return messages

    summary = _extractive_summary(messages[:dropped_count])
    note = f"（前情提要：已省略较早的 {dropped_count} 条消息。"
    if summary:
        tail = "" if summary[-1] in "。！？；" else "。"
        note += f" {summary}{tail}"
    note += "）"
    return [SystemMessage(content=note), *window]
