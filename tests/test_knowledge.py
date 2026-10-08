from __future__ import annotations

from pathlib import Path

from studygraph.domain.retrieval import chunk_text
from studygraph.infrastructure.knowledge import KnowledgeStore


def test_chunk_text_splits_with_overlap() -> None:
    text = "a" * 1000
    chunks = chunk_text(text, max_chars=400, overlap=50)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 400 for chunk in chunks)


def test_chunk_text_keeps_short_text_intact() -> None:
    assert chunk_text("只有一句话。") == ["只有一句话。"]


def test_add_note_and_search_by_long_query(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    store.add_note(
        "线性代数",
        "特征值与特征向量",
        "特征值描述线性变换在某个方向上的缩放倍数，对应方向由特征向量给出。",
    )

    hits = store.search("特征值描述什么", libraries=["线性代数"], limit=3)

    assert hits
    assert hits[0].library == "线性代数"
    assert "缩放倍数" in hits[0].content


def test_short_query_falls_back_to_like(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    store.add_note("线性代数", "秩", "矩阵的秩等于其行阶梯形中非零行的数目。")

    # 两字查询进不了 trigram FTS，应走 LIKE 兜底。
    hits = store.search("秩", libraries=["线性代数"], limit=3)

    assert hits
    assert "非零行" in hits[0].content


def test_search_respects_library_scope(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    store.add_note("高等数学", "导数", "导数是瞬时变化率，反映曲线的切线斜率。")
    store.add_note("大学物理", "速度", "速度是位移对时间的导数。")

    hits = store.search("导数", libraries=["高等数学"], limit=5)

    assert hits
    assert all(hit.library == "高等数学" for hit in hits)


def test_list_libraries_counts_documents(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db")
    store.add_note("高等数学", "导数", "内容甲")
    store.add_note("高等数学", "积分", "内容乙")
    store.add_note("线性代数", "行列式", "内容丙")

    libraries = {item["name"]: item["document_count"] for item in store.list_libraries()}

    assert libraries["高等数学"] == 2
    assert libraries["线性代数"] == 1
