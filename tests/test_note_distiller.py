"""「智能沉淀」的回归测试：把对话回复提炼成独立笔记。

锁死的规则：
- 模型输出「标题：… + 正文」→ 正确拆分，正文重复的 H1 去掉；
- 回复里没有知识内容（模型输出 NONE / 太短）→ NoteDistillError，不硬凑；
- Mock / None 模型 → 原文转存（generator="raw"，与旧行为一致，不消耗额度）；
- 模型调用异常 → 同样原文转存，绝不阻塞。
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from studygraph.application.note_distiller import NoteDistillError, distill_note


class FakeModel:
    """按脚本返回内容的假模型。"""

    _llm_type = "fake"

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def ainvoke(self, messages, **kwargs):  # noqa: ANN001, ANN003
        self.calls += 1
        return AIMessage(content=self.content)


@pytest.mark.asyncio
async def test_distill_extracts_title_and_strips_duplicate_h1() -> None:
    model = FakeModel(
        "标题：埃氏筛法\n\n"
        "## 定义\n**一句话版本：用质数把合数筛掉。**\n\n"
        "## 要点\n- 从 2 开始，划掉质数的倍数\n\n"
        "# 埃氏筛法（重复标题）"
    )
    result = await distill_note(model, question="什么是筛法", reply="……对话回复……")
    assert result["generator"] == "model"
    assert result["title"] == "埃氏筛法"
    assert "状态转移" not in result["content"]
    assert result["content"].startswith("## 定义")
    assert "# 埃氏筛法" not in result["content"]


@pytest.mark.asyncio
async def test_distill_raises_when_reply_has_no_knowledge() -> None:
    model = FakeModel("NONE")
    with pytest.raises(NoteDistillError, match="还没有可以沉淀"):
        await distill_note(model, question="你好", reply="你好呀，我是 StudyGraph。")

    short = FakeModel("标题：x\n\n太短")
    with pytest.raises(NoteDistillError, match="知识密度太低"):
        await distill_note(short, question="q", reply="r")


@pytest.mark.asyncio
async def test_distill_falls_back_to_raw_without_model() -> None:
    result = await distill_note(None, question="什么是筛法", reply="我先讲一下筛法……")
    assert result["generator"] == "raw"
    assert result["content"].startswith("我先讲一下筛法")
    assert result["title"].startswith("什么是筛法")


@pytest.mark.asyncio
async def test_distill_falls_back_to_raw_on_model_error() -> None:
    class BrokenModel:
        _llm_type = "fake"

        async def ainvoke(self, messages, **kwargs):  # noqa: ANN001, ANN003
            raise RuntimeError("boom")

    result = await distill_note(BrokenModel(), question="q", reply="回复原文")
    assert result["generator"] == "raw"
    assert result["content"] == "回复原文"


@pytest.mark.asyncio
async def test_distill_strips_markdown_fences() -> None:
    model = FakeModel(
        "标题：快速排序\n```markdown\n## 定义\n**分而治之的排序。**\n\n"
        "## 要点\n- 每轮选定基准后分区，递归处理两侧\n"
        "- 平均复杂度 $O(n\\log n)$，最坏 $O(n^2)$\n```\n"
    )
    result = await distill_note(model, question="快排", reply="r")
    assert result["content"].startswith("## 定义")
    assert "```" not in result["content"]
