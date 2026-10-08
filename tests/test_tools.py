from __future__ import annotations

from pathlib import Path

from studygraph import tools
from studygraph.knowledge import KnowledgeStore
from studygraph.tools import calculator, knowledge_search, safe_eval


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
