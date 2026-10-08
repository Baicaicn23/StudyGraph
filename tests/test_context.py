from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from studygraph.application.context import compact_messages


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
