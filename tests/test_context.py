from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from zhiji.application.context import compact_messages


def test_compact_keeps_short_history_unchanged() -> None:
    messages = [HumanMessage("你好"), AIMessage("你好呀")]
    assert compact_messages(messages, max_messages=10) == messages


def test_compact_trims_to_recent_turns_with_note() -> None:
    messages: list = []
    for index in range(20):
        messages.append(HumanMessage(f"问题 {index}"))
        messages.append(AIMessage(f"回答 {index}"))

    compacted = compact_messages(messages, max_messages=10, keep_recent=6)

    assert len(compacted) < len(messages)
    assert isinstance(compacted[0], SystemMessage)
    assert "已省略" in str(compacted[0].content)


def test_compact_never_starts_with_orphan_tool_message() -> None:
    messages: list = [HumanMessage("问")]
    messages.append(
        AIMessage(
            content="",
            tool_calls=[{"name": "knowledge_search", "args": {}, "id": "1"}],
        )
    )
    messages.append(
        ToolMessage(content="结果", tool_call_id="1", name="knowledge_search")
    )
    messages.append(AIMessage("回答"))
    for index in range(10):
        messages.append(HumanMessage(f"追问 {index}"))
        messages.append(AIMessage(f"答复 {index}"))

    compacted = compact_messages(messages, max_messages=6, keep_recent=4)

    assert not isinstance(compacted[1] if len(compacted) > 1 else None, ToolMessage)
    assert not isinstance(compacted[0], ToolMessage)


def test_compact_summary_carries_early_questions() -> None:
    """压缩后不能只剩"已省略 N 条"——要留下被丢弃轮次的关键信息。

    回归背景：早期实现只写一句「已省略 N 条消息」，等于把前情整段丢掉；
    模型在后续回合会重复问已经问过的事，或与之前的结论自相矛盾。
    """

    messages: list = []
    for index in range(20):
        messages.append(HumanMessage(f"我想问第 {index} 个问题。补充说明略。"))
        messages.append(AIMessage(f"第 {index} 个问题的结论是这样。展开略。"))

    compacted = compact_messages(messages, max_messages=10, keep_recent=6)
    note = str(compacted[0].content)

    assert "已省略" in note
    assert "用户先后问过" in note
    assert "第 16 个问题" in note, "保留的应是最近被丢弃的那几个提问"
    assert "较早的助手结论" in note


def test_compact_summary_is_bounded() -> None:
    """摘要必须有字数上限，否则"压缩"会因超长消息变成新的膨胀源。"""

    messages: list = []
    for _ in range(20):
        messages.append(HumanMessage("很长的提问" * 120))
        messages.append(AIMessage("很长的回答" * 120))

    compacted = compact_messages(messages, max_messages=10, keep_recent=6)
    note = str(compacted[0].content)

    assert len(note) < 400, "整段前情提要应控制在数百字内"
