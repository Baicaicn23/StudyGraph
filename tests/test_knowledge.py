from __future__ import annotations

from pathlib import Path

from zhiji.domain.retrieval import chunk_text
from zhiji.infrastructure.knowledge import KnowledgeStore


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


# -- 轻量精排（词面证据重排） --------------------------------------------------

def _hit(chunk_id: int, title: str, content: str, score: float):
    from zhiji.domain.models import SearchHit

    return SearchHit(
        chunk_id=chunk_id, library="高等数学", title=title, content=content, score=score
    )


def test_rerank_demotes_noise_without_lexical_overlap() -> None:
    """语义路权重高、但词面毫无关系的候选，应被真正贴题的候选压过去。

    回归背景：RRF 只看排名，无法识别"某一路召回其实不可靠"（例如没接真实
    embedding 时），噪声候选会以同样的票数挤掉真正命中的结果。
    """

    from zhiji.domain.retrieval import rerank_hits

    hits = [
        _hit(1, "行列式的性质", "交换两行其值变号；两行成比例时行列式为零。", 0.016),
        _hit(2, "特征值与特征向量", "特征值刻画线性变换在特征方向上的伸缩倍数。", 0.013),
    ]

    ranked = rerank_hits(hits, "本征值到底是什么含义", expansion=("特征值",))

    assert [item.chunk_id for item in ranked] == [2, 1]


def test_rerank_keeps_order_when_query_has_no_units() -> None:
    """查询没有可用检索单元时原样返回，避免空转。"""

    from zhiji.domain.retrieval import rerank_hits

    hits = [_hit(1, "甲", "内容一", 0.02), _hit(2, "乙", "内容二", 0.01)]
    assert [item.chunk_id for item in rerank_hits(hits, "？！")] == [1, 2]


def test_rerank_does_not_drop_candidates() -> None:
    """精排只调顺序、不增删候选——召回集合的职责不在这里。"""

    from zhiji.domain.retrieval import rerank_hits

    hits = [
        _hit(index, f"标题{index}", "无关内容", 0.01) for index in range(1, 6)
    ]
    assert len(rerank_hits(hits, "极限的运算法则")) == len(hits)
