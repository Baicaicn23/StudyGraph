from __future__ import annotations

import time
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from zhiji.application import tools
from zhiji.application.graph import build_graph
from zhiji.infrastructure.knowledge import KnowledgeStore
from zhiji.infrastructure.llm import MockChatModel
from zhiji.infrastructure.usage_repository import SqliteUsageRepository


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
    seen: list[tuple[str, str | None]] = []

    def router(tier: str, effort: str | None = None) -> MockChatModel:
        seen.append((tier, effort))
        return MockChatModel()

    graph = _build(tmp_path, model_router=router)

    await _run(
        graph,
        {"messages": [HumanMessage("帮我算一下 6 * 7")]},
        {"configurable": {"thread_id": "route-small"}},
    )
    assert ("small", "off") in seen

    seen.clear()
    await _run(
        graph,
        {"messages": [HumanMessage("讲解一下导数的几何意义")]},
        {"configurable": {"thread_id": "route-standard"}},
    )
    assert ("standard", "max") in seen


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


def test_system_prompt_contains_teaching_charter_and_progress() -> None:
    from zhiji.application.graph import build_system_prompt

    state = {
        "messages": [],
        "agent": "tutor",
        "progress": [
            {"library": "线性代数", "mastery": 85},
            {"library": "高等数学-微积分", "mastery": 40},
        ],
    }

    prompt = build_system_prompt("tutor", state)

    # 教学总纲（三条红线）对所有子智能体生效。
    assert "三条红线" in prompt
    assert "引导优先于告知" in prompt
    # 掌握度按从薄弱到较好排列，薄弱学科在前——模型据此调整讲解深度。
    assert "掌握度" in prompt
    assert prompt.index("高等数学-微积分（掌握度 40%）") < prompt.index(
        "线性代数（掌握度 85%）"
    )


def test_teaching_charter_carries_output_spec_and_concealment() -> None:
    """输出规格 + 技术过程内隐——对所有角色共享的总纲约束。"""

    from zhiji.application.graph import build_system_prompt

    for agent in ("tutor", "practice", "progress", "retriever", "calculator", "chat"):
        prompt = build_system_prompt(agent, {"messages": [], "agent": agent})
        # 输出规格：结论先行 / 结尾必须落到下一步。
        assert "结论先行" in prompt, agent
        assert "结尾必须落到下一步" in prompt, agent
        # 技术过程内隐：正文不提工具/步骤/报错，失败要降级为可用结论。
        assert "技术过程内隐" in prompt, agent
        assert "只讲教学" in prompt, agent
        assert "稍后同步到你的知识库中" in prompt, agent
        # 绝对禁止清单。
        assert "绝对禁止" in prompt, agent


def test_scenario_skeletons_live_in_their_own_profiles() -> None:
    """分场景输出骨架挂在对应角色上——不该把讲解骨架挂到出题/进度角色。"""

    from zhiji.application.graph import build_system_prompt

    tutor = build_system_prompt("tutor", {"messages": [], "agent": "tutor"})
    assert "知识点讲解的骨架" in tutor
    assert "错题分析的骨架" in tutor

    progress = build_system_prompt("progress", {"messages": [], "agent": "progress"})
    assert "学习规划 / 备考方案的骨架" in progress
    # 规划骨架用表格呈现阶段：| 阶段 | 核心内容 | 目标 |
    assert "| 阶段 | 核心内容 | 目标 |" in progress
    # 讲解骨架不外溢到进度角色。
    assert "知识点讲解的骨架" not in progress


def test_progress_keywords_cover_study_planning() -> None:
    """「学习计划 / 备考」这类说法要能路由到 progress，否则会掉进闲聊。"""

    from zhiji.application import routing

    for text in ("帮我制定一个学习计划", "我要备考期末考试", "给我一个复习规划"):
        intent, _ = routing.classify(text)
        assert intent == routing.PROGRESS, text


def test_system_prompt_omits_progress_when_empty() -> None:
    from zhiji.application.graph import build_system_prompt

    prompt = build_system_prompt("tutor", {"messages": [], "agent": "tutor"})

    assert "各学科掌握度" not in prompt


def test_note_style_guide_only_for_note_writing_agents() -> None:
    from zhiji.application.graph import build_system_prompt

    for agent in ("tutor", "chat", "retriever"):
        prompt = build_system_prompt(agent, {"messages": [], "agent": agent})
        assert "Markdown 笔记写作规范" in prompt, agent
        assert "自测三问" in prompt, agent

    for agent in ("calculator", "progress"):
        prompt = build_system_prompt(agent, {"messages": [], "agent": agent})
        assert "Markdown 笔记写作规范" not in prompt, agent


def test_save_note_tool_description_carries_style_requirement() -> None:
    from zhiji.application.tools import save_note

    description = save_note.description
    assert "Markdown 笔记写作规范" in description
    assert "自测三问" in description
