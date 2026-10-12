"""智能选库的回归测试（离线：模型替换成桩）。"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from zhiji.application.library_selector import select_libraries


class FakeModel:
    _llm_type = "fake"

    def __init__(self, content: str) -> None:
        self.content = content

    async def ainvoke(self, messages, **kwargs):  # noqa: ANN001, ANN003
        return AIMessage(content=self.content)


CANDIDATES = ["高等数学", "线性代数", "英语", "数据结构"]


@pytest.mark.asyncio
async def test_selects_relevant_subset() -> None:
    model = FakeModel('["高等数学", "线性代数"]')
    chosen = await select_libraries(
        model, question="泰勒公式怎么用", libraries=CANDIDATES
    )
    assert chosen == ["高等数学", "线性代数"]


@pytest.mark.asyncio
async def test_fabricated_names_are_filtered() -> None:
    model = FakeModel('["高等数学", "我编的库", 123]')
    chosen = await select_libraries(model, question="极限", libraries=CANDIDATES)
    assert chosen == ["高等数学"]


@pytest.mark.asyncio
async def test_json_in_code_fence_is_parsed() -> None:
    model = FakeModel('```json\n["数据结构"]\n```')
    chosen = await select_libraries(model, question="二叉树", libraries=CANDIDATES)
    assert chosen == ["数据结构"]


@pytest.mark.asyncio
async def test_empty_selection_falls_back_to_none() -> None:
    model = FakeModel("[]")
    assert (
        await select_libraries(model, question="今天天气", libraries=CANDIDATES)
        is None
    )


@pytest.mark.asyncio
async def test_unparseable_output_falls_back_to_none() -> None:
    model = FakeModel("我觉得应该查高等数学和线性代数。")
    assert (
        await select_libraries(model, question="极限", libraries=CANDIDATES) is None
    )


@pytest.mark.asyncio
async def test_mock_or_missing_model_falls_back_to_none() -> None:
    assert await select_libraries(None, question="q", libraries=CANDIDATES) is None

    class MockModel:
        _llm_type = "study-mock"

    assert (
        await select_libraries(MockModel(), question="q", libraries=CANDIDATES)
        is None
    )
