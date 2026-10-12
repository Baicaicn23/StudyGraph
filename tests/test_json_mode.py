"""JSON 模式统一入口（invoke_json）与系统提示词缓存友好结构的测试。"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from zhiji.application.graph import build_system_prompt
from zhiji.application.json_mode import invoke_json


class _FakeModel:
    """记录调用 kwargs 的假模型：可配置为「拒绝 response_format」。"""

    def __init__(self, *, reject_json_mode: bool) -> None:
        self.reject_json_mode = reject_json_mode
        self.calls: list[dict] = []

    async def ainvoke(self, messages, **kwargs):
        self.calls.append(dict(kwargs))
        if self.reject_json_mode and "response_format" in kwargs:
            raise ValueError("response_format is not supported")
        return AIMessage(content='["步骤"]')


async def test_invoke_json_prefers_response_format() -> None:
    model = _FakeModel(reject_json_mode=False)
    response = await invoke_json(model, [HumanMessage("出个计划")])
    assert response.content == '["步骤"]'
    assert model.calls[0]["response_format"] == {"type": "json_object"}


async def test_invoke_json_falls_back_when_unsupported() -> None:
    model = _FakeModel(reject_json_mode=True)
    response = await invoke_json(model, [HumanMessage("出个计划")])
    assert response.content == '["步骤"]'
    # 第一次带 response_format 被拒，第二次自动去掉
    assert "response_format" not in model.calls[1]


def test_system_prompt_keeps_stable_prefix_before_dynamic_parts() -> None:
    """缓存友好：静态规范（笔记规范）在动态内容（记忆/掌握度）之前，
    且动态内容只是**追加**——静态前缀逐字节一致，才可能命中上游上下文缓存。"""

    state = {
        "memories": ["学生在准备期末"],
        "progress": [{"library": "高等数学", "mastery": 70}],
    }
    prompt = build_system_prompt("tutor", state)
    note_style_index = prompt.find("笔记")
    memory_index = prompt.find("关于这位学习者")
    assert note_style_index != -1 and memory_index != -1
    assert note_style_index < memory_index

    static_part = build_system_prompt("tutor", {})
    assert prompt.startswith(static_part)
