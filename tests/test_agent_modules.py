from __future__ import annotations

import time
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from studygraph.application import tools
from studygraph.application.graph import build_graph
from studygraph.infrastructure.knowledge import KnowledgeStore
from studygraph.infrastructure.llm import MockChatModel
from studygraph.infrastructure.usage_repository import SqliteUsageRepository


async def _run(graph, payload, config):
    final = None
    async for mode, chunk in graph.astream(
        payload, config, stream_mode=["values", "updates"]
    ):
        if mode == "values":
            final = chunk
    return final


def _build(tmp_path: Path, **kwargs):
    store = KnowledgeStore(tmp_path / "kb.db")
    tools.configure(store)
    graph = build_graph(
        model=MockChatModel(), checkpointer=InMemorySaver(), max_tool_rounds=4, **kwargs
    )
    return graph


async def test_complex_request_gets_a_plan(tmp_path: Path) -> None:
    graph = _build(tmp_path)
    config = {"configurable": {"thread_id": "plan-1"}}

    final = await _run(
        graph,
        {"messages": [HumanMessage("请一步步教我：先讲导数的定义，然后讲几何意义，再给两道例题")]},
        config,
    )

    assert final.get("plan")
    assert final["intent"] == "concept_explain"


async def test_simple_request_skips_planning(tmp_path: Path) -> None:
    graph = _build(tmp_path)
    config = {"configurable": {"thread_id": "plan-2"}}

    final = await _run(graph, {"messages": [HumanMessage("讲解一下导数")]}, config)

    assert final.get("plan") == []


async def test_model_router_receives_tier(tmp_path: Path) -> None:
    seen: list[str] = []

    def router(tier: str) -> MockChatModel:
        seen.append(tier)
        return MockChatModel()

    graph = _build(tmp_path, model_router=router)

    await _run(
        graph,
        {"messages": [HumanMessage("帮我算一下 6 * 7")]},
        {"configurable": {"thread_id": "route-small"}},
    )
    assert "small" in seen

    seen.clear()
    await _run(
        graph,
        {"messages": [HumanMessage("讲解一下导数的几何意义")]},
        {"configurable": {"thread_id": "route-standard"}},
    )
    assert "standard" in seen


async def test_usage_is_recorded(tmp_path: Path) -> None:
    db = tmp_path / "kb.db"
    store = KnowledgeStore(db)
    tools.configure(store)
    repository = SqliteUsageRepository(db)
    graph = build_graph(
        model=MockChatModel(),
        checkpointer=InMemorySaver(),
        max_tool_rounds=4,
        usage_repository=repository,
    )

    await _run(
        graph,
        {"messages": [HumanMessage("帮我算一下 6 * 7")]},
        {"configurable": {"thread_id": "usage-1"}},
    )

    assert repository.total_since(user_id="local", since=0) > 0


async def test_budget_blocks_real_calls(tmp_path: Path) -> None:
    db = tmp_path / "kb.db"
    store = KnowledgeStore(db)
    tools.configure(store)
    repository = SqliteUsageRepository(db)
    repository.record(
        user_id="local",
        model="m",
        input_tokens=100,
        output_tokens=100,
        total_tokens=200,
        created_at=time.time(),
    )
    graph = build_graph(
        model=MockChatModel(),
        checkpointer=InMemorySaver(),
        max_tool_rounds=4,
        usage_repository=repository,
        daily_token_budget=100,
    )

    final = await _run(
        graph,
        {"messages": [HumanMessage("帮我算一下 6 * 7")]},
        {"configurable": {"thread_id": "budget-1"}},
    )

    assert "预算" in str(final["messages"][-1].content)
