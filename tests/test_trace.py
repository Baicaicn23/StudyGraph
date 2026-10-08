from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from studygraph.application.trace import diagnose, render


def _tool_call(call_id: str = "c1"):
    return {"name": "knowledge_search", "args": {"query": "x"}, "id": call_id}


def test_diagnose_attributes_empty_retrieval() -> None:
    messages = [
        HumanMessage("我的笔记里怎么讲导数的？"),
        AIMessage(content="", tool_calls=[_tool_call()]),
        ToolMessage(
            content="知识库里没有找到相关片段。",
            tool_call_id="c1",
            name="knowledge_search",
        ),
        AIMessage(content="（回答）"),
    ]

    diagnosis = diagnose(messages, {"intent": "retrieval", "agent": "retriever"})

    assert diagnosis["empty_sources"] is True
    assert diagnosis["attribution"] == "retrieval"
    assert any("空结果" in w for w in diagnosis["warnings"])


def test_diagnose_attributes_tool_error() -> None:
    messages = [
        HumanMessage("出题考考我"),
        AIMessage(content="", tool_calls=[_tool_call()]),
        ToolMessage(
            content="[tool_not_allowed] 当前模式下不允许调用「save_note」。",
            tool_call_id="c1",
            name="save_note",
        ),
        AIMessage(content="（回答）"),
    ]

    diagnosis = diagnose(messages, {"intent": "practice", "agent": "practice"})

    assert diagnosis["attribution"] == "tool"


def test_diagnose_attributes_missing_answer() -> None:
    messages = [
        HumanMessage("讲解一下特征值"),
        AIMessage(content="", tool_calls=[_tool_call()]),
    ]

    diagnosis = diagnose(messages, {"intent": "concept_explain", "agent": "tutor"})

    assert diagnosis["answered"] is False
    assert diagnosis["attribution"] == "model"
    assert "没有产出最终回答" in diagnosis["warnings"]


def test_render_contains_layers() -> None:
    diagnosis = diagnose([HumanMessage("你好")], {"intent": "smalltalk", "agent": "chat"})
    text = render(diagnosis, thread="t1")
    assert "thread=t1" in text
    assert "归因" in text
