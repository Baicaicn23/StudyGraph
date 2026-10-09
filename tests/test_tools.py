from __future__ import annotations

from pathlib import Path
from typing import Any

from studygraph.application import tools
from studygraph.application.tools import (
    calculator,
    knowledge_search,
    mistake_search,
    safe_eval,
)
from studygraph.infrastructure.knowledge import KnowledgeStore


def test_calculator_evaluates_arithmetic() -> None:
    assert calculator.invoke({"expression": "7 * 9"}) == "63"
    assert calculator.invoke({"expression": "(2 + 3) / 2"}) == "2.5"


def test_safe_eval_rejects_non_arithmetic() -> None:
    import pytest

    for bad in ["__import__('os')", "1; 2", "abc"]:
        with pytest.raises(ValueError):
            safe_eval(bad)


def test_calculator_reports_error_gracefully() -> None:
    assert calculator.invoke({"expression": "1 / 0"}).startswith("计算出错")


def test_knowledge_search_uses_selected_libraries(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    store.add_note("高等数学", "导数", "导数是瞬时变化率，反映切线斜率。")
    store.add_note("大学物理", "加速度", "加速度是速度对时间的导数。")
    tools.configure(store)

    tools.set_current_libraries(["高等数学"])
    result = knowledge_search.invoke({"query": "导数是瞬时变化率吗"})

    assert "高等数学" in result
    assert "大学物理" not in result


def test_knowledge_search_reports_empty(tmp_path: Path) -> None:
    tools.configure(KnowledgeStore(tmp_path / "kb.db"))
    tools.set_current_libraries(None)

    assert "没有找到" in knowledge_search.invoke({"query": "完全不存在的内容"})


class _FakeLearningRepo:
    """最小学习仓库桩：只实现 mistake_search 用到的 list_feedback。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def list_feedback(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._rows)

    def __getattr__(self, name):  # 其余端口方法不需要
        raise AssertionError(f"unexpected repo call: {name}")


def test_mistake_search_filters_by_keyword_and_counts(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    repo = _FakeLearningRepo(
        [
            {
                "library": "高等数学-微积分",
                "question": "求 f(x)=x^2 的导数",
                "note": "把导数公式和差公式记混",
            },
            {
                "library": "高等数学-微积分",
                "question": "复合函数的导数求解",
                "note": "外层内层求导顺序错",
            },
            {
                "library": "大学英语四级",
                "question": "阅读理解主旨题",
                "note": "过度推断作者意图",
            },
        ]
    )
    tools.configure(store, repo)
    tools.set_current_user("tester")

    result = mistake_search.invoke({"query": "导数"})

    assert "共匹配到 2 条误区记录" in result
    assert "高等数学-微积分 2 条" in result
    assert "导数公式和差公式记混" in result
    assert "大学英语四级" not in result


def test_mistake_search_overview_without_keyword(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    repo = _FakeLearningRepo(
        [
            {"library": "线性代数", "question": "行列式计算", "note": "符号抄错"},
        ]
    )
    tools.configure(store, repo)
    tools.set_current_user("tester")

    result = mistake_search.invoke({})

    assert "线性代数 1 条" in result
    assert "符号抄错" in result


def test_mistake_search_reports_empty_mistake_book(tmp_path: Path) -> None:
    tools.configure(KnowledgeStore(tmp_path / "kb.db"), _FakeLearningRepo([]))
    tools.set_current_user("tester")

    assert "还没有记录" in mistake_search.invoke({"query": "任意"})
