from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from studygraph.application import tools
from studygraph.application.graph import build_graph
from studygraph.infrastructure.knowledge import KnowledgeStore
from studygraph.infrastructure.llm import MockChatModel


def _build(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "kb.db")
    tools.configure(store)
    graph = build_graph(
        model=MockChatModel(), checkpointer=InMemorySaver(), max_tool_rounds=4
    )
    return graph, store


async def _run(graph, payload, config):
    """跑一轮，返回 (最终状态, 中断列表)。"""

    final = None
    interrupts = []
    async for mode, chunk in graph.astream(
        payload, config, stream_mode=["values", "updates"]
    ):
        if mode == "values":
            final = chunk
        elif isinstance(chunk, dict) and "__interrupt__" in chunk:
            interrupts = list(chunk["__interrupt__"])
    return final, interrupts


def _payload(text: str, **extra):
    return {"messages": [HumanMessage(text)], "user_id": "tester", **extra}


async def test_calculation_turn_runs_the_calculator(tmp_path: Path) -> None:
    graph, _store = _build(tmp_path)
    config = {"configurable": {"thread_id": "calc"}}

    final, interrupts = await _run(graph, _payload("帮我算一下 7 * 9"), config)

    assert interrupts == []
    assert final["intent"] == "calculation"
    assert final["agent"] == "calculator"
    tool_messages = [m for m in final["messages"] if isinstance(m, ToolMessage)]
    assert any(m.name == "calculator" and m.content == "63" for m in tool_messages)
    assert "63" in str(final["messages"][-1].content)


async def test_retrieval_turn_searches_the_library(tmp_path: Path) -> None:
    graph, store = _build(tmp_path)
    store.add_note("线性代数", "特征值", "特征值描述线性变换在某个方向上的缩放倍数。")
    config = {"configurable": {"thread_id": "retrieval"}}

    final, _interrupts = await _run(
        graph,
        _payload("我的笔记里怎么讲特征值的？", knowledge_bases=["线性代数"]),
        config,
    )

    assert final["intent"] == "retrieval"
    tool_messages = [m for m in final["messages"] if isinstance(m, ToolMessage)]
    assert any(m.name == "knowledge_search" for m in tool_messages)
    assert "缩放倍数" in str(final["messages"][-1].content)


async def test_library_filter_survives_across_nodes(tmp_path: Path) -> None:
    """回归（P1 缺陷①）：选中的知识库过滤必须传到 tools 节点。

    LangGraph 各节点在独立 context 执行，contextvar 不跨节点传播——曾经只在
    agent 节点 set_current_libraries，tools 节点读到 None 导致检索落到全库
    （选了「高等数学」却返回《四级英语》的片段）。修复后 tools 节点从 state
    重新设置，这里用"两个库都能命中同一关键词"的布局来锁住这个行为。
    """

    graph, store = _build(tmp_path)
    # 两库内容都含与查询重叠的 3-gram（"导数的"），保证全库检索时两边都命中——
    # 这样才能检验"选中库之后是否真的把另一个库过滤掉"。
    store.add_note("高等数学", "导数定义", "导数的定义：导数是瞬时变化率，反映切线斜率。")
    store.add_note("大学英语四级", "导数词汇", "derivative（导数的英文）是四级高频词汇。")
    config = {"configurable": {"thread_id": "filter-regression"}}

    final, _interrupts = await _run(
        graph,
        _payload("我的笔记里怎么讲导数的？", knowledge_bases=["高等数学"]),
        config,
    )

    tool_messages = [
        m.content
        for m in final["messages"]
        if isinstance(m, ToolMessage) and m.name == "knowledge_search"
    ]
    assert tool_messages, "检索回合应产生 knowledge_search 工具消息"
    joined = "\n".join(str(content) for content in tool_messages)
    assert "高等数学" in joined
    assert "大学英语四级" not in joined, "选了库之后不允许串到未选中的库"


async def test_save_note_asks_for_confirmation_then_persists(tmp_path: Path) -> None:
    graph, store = _build(tmp_path)
    config = {"configurable": {"thread_id": "hitl"}}

    _final, interrupts = await _run(
        graph, _payload("记住：我在准备月底的微积分测验"), config
    )
    assert interrupts, "save_note 应该先触发 HITL 确认"
    assert interrupts[0].value["action"] == "save_note"
    assert store.list_libraries() == []  # 确认之前不能落库

    await _run(graph, Command(resume=True), config)

    hits = store.search("微积分测验", limit=3)
    assert hits, "确认后笔记应已入库"


async def test_save_note_can_be_rejected(tmp_path: Path) -> None:
    graph, store = _build(tmp_path)
    config = {"configurable": {"thread_id": "hitl-reject"}}

    _final, interrupts = await _run(graph, _payload("帮我记下：明天要交作业"), config)
    assert interrupts

    await _run(graph, Command(resume=False), config)

    assert store.list_libraries() == []


async def test_conversation_persists_across_turns(tmp_path: Path) -> None:
    graph, _store = _build(tmp_path)
    config = {"configurable": {"thread_id": "persist"}}

    first, _ = await _run(graph, _payload("计算 3 * 4"), config)
    count_after_first = len(first["messages"])

    second, _ = await _run(graph, _payload("你好"), config)

    # 第二轮带着第一轮的历史继续（checkpoint 持久化）。
    assert len(second["messages"]) > count_after_first
