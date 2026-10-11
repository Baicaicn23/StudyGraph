"""PDF 智能格式化的回归测试（离线：模型替换成桩）。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from studygraph.application.pdf_formatter import (
    _chunk_text,
    format_pdf_markdown,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeModel:
    _llm_type = "fake"

    def __init__(self, content: str) -> None:
        self.content = content
        self.inputs: list[str] = []

    async def ainvoke(self, messages, **kwargs):  # noqa: ANN001, ANN003
        self.inputs.append(messages[-1].content)
        return AIMessage(content=self.content)


@pytest.mark.asyncio
async def test_formats_into_structured_markdown() -> None:
    model = FakeModel("## 第 1 章 绪论\n- 什么是人机交互技术？")
    raw = FIXTURES and "第 1 章 绪论\n1. 什么是人机交互技术？"
    out = await format_pdf_markdown(model, raw_text=str(raw))
    assert out.startswith("## 第 1 章")
    assert model.inputs and "PDF 抽取文本" in model.inputs[0]


@pytest.mark.asyncio
async def test_long_text_is_chunked() -> None:
    model = FakeModel("## 重排版")
    raw = "\n".join(f"第 {i} 行的正文内容，长度足够触发分块逻辑。" for i in range(200))
    out = await format_pdf_markdown(model, raw_text=raw)
    assert len(model.inputs) > 1  # 分成了多块
    assert "## 重排版" in out


@pytest.mark.asyncio
async def test_block_failure_keeps_original_text() -> None:
    class BrokenModel:
        _llm_type = "fake"

        async def ainvoke(self, messages, **kwargs):  # noqa: ANN001, ANN003
            raise RuntimeError("boom")

    raw = "原始正文第一块内容，应该原样保留下来。"
    out = await format_pdf_markdown(BrokenModel(), raw_text=raw)
    assert out == raw


def test_chunking_never_splits_lines() -> None:
    text = "\n".join(f"第 {i} 行" for i in range(500))
    chunks = _chunk_text(text, chunk_chars=500)
    assert all(len(c) <= 520 for c in chunks)
    # 不丢行
    assert sum(c.count("\n") + 1 for c in chunks) == 500


def test_sample_pdf_fixture_extracts() -> None:
    from studygraph.infrastructure.extract import extract_text

    text = extract_text("sample.pdf", (FIXTURES / "sample.pdf").read_bytes())
    assert "人机交互" in text or "绪论" in text
