from __future__ import annotations

from types import SimpleNamespace

import pytest

from zhiji.application.question_writer import write_explanation, write_question
from zhiji.domain.quiz import (
    MAX_EXPLANATION_STEPS,
    build_explanation_instruction,
    build_mistake_instruction,
    parse_explanation,
    parse_question,
    template_mistake_question,
)


class _StubModel:
    _llm_type = "stub"

    def __init__(self, content: str) -> None:
        self.content = content

    async def ainvoke(self, messages):  # noqa: ANN001
        return SimpleNamespace(content=self.content)


class _BoomModel:
    _llm_type = "stub"

    async def ainvoke(self, messages):  # noqa: ANN001
        raise RuntimeError("模型挂了")


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


# -- 详解（参考答案 + 关键步骤） -----------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        '{"answer": "极限等于 4。", "steps": ["约分得 x+2", "代入得 4"]}',
        '```json\n{"answer": "极限等于 4。", "steps": ["约分得 x+2", "代入得 4"]}\n```',
        '好的：{"answer": "极限等于 4。", "steps": ["约分得 x+2", "代入得 4"]} 完毕',
    ],
)
def test_parse_explanation_accepts_valid_json(raw: str) -> None:
    parsed = parse_explanation(raw)
    assert parsed is not None
    assert parsed.answer == "极限等于 4。"
    assert parsed.steps == ("约分得 x+2", "代入得 4")
    assert parsed.generator == "model"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "没法给答案",
        "{不是 JSON}",
        '{"answer": ""}',
        '{"answer": "略"}',
        '{"steps": ["只有步骤没有答案"]}',
        '["不是对象"]',
    ],
)
def test_parse_explanation_rejects_invalid(raw: str) -> None:
    assert parse_explanation(raw) is None


def test_parse_explanation_tolerates_dirty_steps() -> None:
    """步骤是"有最好、没有也行"：缺失/含空串/超量都不该让整次生成失败。"""

    no_steps = parse_explanation('{"answer": "答案是对还是错，这里给结论。"}')
    assert no_steps is not None and no_steps.steps == ()

    dirty = parse_explanation(
        '{"answer": "结论。", "steps": ["有内容", "", "   ", "也有内容"]}'
    )
    assert dirty is not None and dirty.steps == ("有内容", "也有内容")

    many = parse_explanation(
        '{"answer": "结论。", "steps": ['
        + ", ".join(f'"第{i}步"' for i in range(1, 12))
        + "]}"
    )
    assert many is not None and len(many.steps) == MAX_EXPLANATION_STEPS

    # steps 不是数组时按"没有步骤"处理，不影响答案可用
    wrong_type = parse_explanation('{"answer": "结论。", "steps": "第一步第二步"}')
    assert wrong_type is not None and wrong_type.steps == ()


def test_build_explanation_instruction_carries_prompt_and_context() -> None:
    instruction = build_explanation_instruction(
        "求 lim(x→2)(x²−4)/(x−2)", context="学科：高等数学-微积分"
    )
    assert "求 lim(x→2)(x²−4)/(x−2)" in instruction
    assert "高等数学-微积分" in instruction

    bare = build_explanation_instruction("任意题面")
    assert "任意题面" in bare and bare.startswith("题目：")


async def test_write_explanation_uses_model_when_available() -> None:
    model = _StubModel('{"answer": "极限存在且等于 4。", "steps": ["约分", "代入"]}')
    written = await write_explanation(model, "任意要求")
    assert written is not None
    assert written.answer == "极限存在且等于 4。"
    assert written.steps == ("约分", "代入")


async def test_write_explanation_returns_none_without_usable_model() -> None:
    """详解**没有模板兜底**：Mock / 无模型 / 模型挂了 / 输出不合法都返回 None，
    由调用方诚实提示，而不是编一段假解析糊弄用户。
    """

    class _Mock:
        _llm_type = "study-mock"

    assert await write_explanation(_Mock(), "x") is None
    assert await write_explanation(None, "x") is None
    assert await write_explanation(_BoomModel(), "x") is None
    assert await write_explanation(_StubModel("没按格式答"), "x") is None
