from __future__ import annotations

import pytest

from studygraph.application.routing import (
    CALCULATION,
    CONCEPT_EXPLAIN,
    PRACTICE,
    PROGRESS,
    RETRIEVAL,
    SMALLTALK,
    allowed_tools,
    classify,
    is_tool_allowed,
    profile_for_intent,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("帮我算一下 37 * 43", CALCULATION),
        ("7 + 8 等于几", CALCULATION),
        ("出几道线性代数的练习题", PRACTICE),
        ("考考我正态分布", PRACTICE),
        ("我的笔记里怎么讲导数的？", RETRIEVAL),
        ("查一下资料里关于矩阵的秩的内容", RETRIEVAL),
        ("我的复习进度怎么样了", PROGRESS),
        ("讲解一下特征值是什么", CONCEPT_EXPLAIN),
        ("你好呀", SMALLTALK),
    ],
)
def test_classify_rules(text: str, expected: str) -> None:
    intent, confidence = classify(text)
    assert intent == expected
    assert 0.0 < confidence <= 1.0


def test_classify_does_not_mistake_chapter_range_for_math() -> None:
    # "第 3-4 章" 只有数字和短横线，没有"数字 运算符 数字"的结构化算式，
    # 不应被判成计算。
    intent, _confidence = classify("第 3 章和第 4 章的区别")
    assert intent != CALCULATION


def test_practice_agent_is_read_only() -> None:
    profile = profile_for_intent(PRACTICE)
    assert "knowledge_search" in allowed_tools(profile)
    assert "save_note" not in allowed_tools(profile)
    # 执行层：即使模型硬发写工具，也不允许。
    assert is_tool_allowed(profile, "knowledge_search") is True
    assert is_tool_allowed(profile, "save_note") is False


def test_progress_agent_denies_all_tools() -> None:
    profile = profile_for_intent(PROGRESS)
    assert allowed_tools(profile) == []
    assert is_tool_allowed(profile, "knowledge_search") is False
