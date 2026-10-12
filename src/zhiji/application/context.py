"""上下文工程：历史压缩（Anthropic《Effective context engineering》）。

对话变长后不把整段历史塞给模型，而是**保留最近的若干条**，更早的用一句"前情提要"
概括（这里只做计数与提示，不做 LLM 摘要——确定、零成本）。

关键：裁剪只从**整轮边界**（HumanMessage）开始，避免把"工具调用/工具结果"这对
消息拆散（拆散会让模型看到孤立的工具结果而报错）。
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


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

    dropped = len(messages) - len(window)
    if dropped <= 0:
        return messages
    note = SystemMessage(content=f"（前情提要：已省略较早的 {dropped} 条消息。）")
    return [note, *window]
