from __future__ import annotations

from types import SimpleNamespace

import pytest

from studygraph.generator import (
    build_mistake_instruction,
    parse_question,
    template_mistake_question,
    write_question,
)


class _StubModel:
    _llm_type = "stub"

    def __init__(self, content: str) -> None:
        self.content = content

    async def ainvoke(self, messages):  # noqa: ANN001
        return SimpleNamespace(content=self.content)


@pytest.mark.parametrize(
    "raw",
    [
        '{"question": "求 ∫₀²(3x²+2x)dx 的值。"}',
        '```json\n{"question": "求 ∫₀²(3x²+2x)dx 的值。"}\n```',
        '好的，这是题：{"question": "求 ∫₀²(3x²+2x)dx 的值。"} 希望有帮助',
    ],
)
def test_parse_question_accepts_valid_json(raw: str) -> None:
    assert parse_question(raw) == "求 ∫₀²(3x²+2x)dx 的值。"


@pytest.mark.parametrize(
    "raw",
    ["", "无法出题", "{不是 JSON}", '{"question": "略"}', '{"focus": "x"}'],
)
def test_parse_question_rejects_junk(raw: str) -> None:
    assert parse_question(raw) is None


async def test_write_question_uses_model_when_available() -> None:
    model = _StubModel('{"question": "请说明定积分与不定积分结果类型的区别。"}')
    written = await write_question(model, "任意要求", fallback="兜底")
    assert written.generator == "model"
    assert "定积分" in written.prompt


async def test_write_question_falls_back_for_mock_and_bad_output() -> None:
    class _Mock:
        _llm_type = "study-mock"

    assert (await write_question(_Mock(), "x", fallback="兜底")).generator == "template"
    assert (await write_question(None, "x", fallback="兜底")).prompt == "兜底"
    bad = _StubModel("模型没按格式答")
    assert (await write_question(bad, "x", fallback="兜底")).prompt == "兜底"


def test_mistake_template_and_instruction_include_note() -> None:
    template = template_mistake_question(question="什么是特征值？", note="我把特征向量搞混了")
    assert "什么是特征值？" in template
    assert "我把特征向量搞混了" in template
    instruction = build_mistake_instruction(
        subject="线性代数", question="什么是特征值？", note="搞混了"
    )
    assert "线性代数" in instruction
