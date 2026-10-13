from __future__ import annotations

from pathlib import Path

from zhiji.domain.models import SearchHit
from zhiji.domain.retrieval import rrf_fuse
from zhiji.infrastructure.embeddings import MockHashEmbedding
from zhiji.infrastructure.knowledge import KnowledgeStore, short_cjk_terms


def _store(tmp_path: Path, **kwargs) -> KnowledgeStore:
    """不带向量：隔离出关键词/扩写路的真实行为（Mock 向量会掩盖问题）。"""

    return KnowledgeStore(tmp_path / "kb.db", **kwargs)


def test_synonym_expansion_recalls_document_with_different_wording(
    tmp_path: Path,
) -> None:
    """「本征值」应该能找到写着「特征值」的资料——字面零重叠。"""

    store = _store(tmp_path)
    store.add_note(
        "线性代数",
        "特征值与特征向量",
        "特征值刻画线性变换在特征方向上的伸缩倍数，对应方向由特征向量给出。",
    )
    store.add_note("高等数学", "导数", "导数是函数在某一点的瞬时变化率。")

    hits = store.search("本征值", limit=3)

    assert hits
    assert hits[0].title == "特征值与特征向量"


def test_english_term_recalls_chinese_document(tmp_path: Path) -> None:
    """中英对照：「queue」应该能找到「队列」的资料。"""

    store = _store(tmp_path)
    store.add_note("数据结构", "队列", "队列是先进先出的线性表，入队在一端、出队另一端。")
    store.add_note("高等数学", "导数", "导数是瞬时变化率。")

    hits = store.search("queue 这种结构有什么特点", limit=3)

    assert hits
    assert hits[0].title == "队列"


def test_expansion_can_be_disabled(tmp_path: Path) -> None:
    """关掉扩写后，「本征值」就召不回来了——证明命中的是扩写路而非别的通道。"""

    store = _store(tmp_path, synonym_groups=())
    store.add_note(
        "线性代数", "特征值与特征向量", "特征值刻画线性变换在特征方向上的伸缩倍数。"
    )

    assert store.search("本征值", limit=3) == []


def test_short_cjk_terms_drops_stopwords_and_caps(tmp_path: Path) -> None:
    """两字词提取：剔虚词、限量，留下信息量高的术语。"""

    terms = short_cjk_terms("矩阵的秩怎么求")

    assert "矩阵" in terms
    assert "怎么" not in terms  # 虚词
    assert len(terms) <= 4


def test_short_terms_like_channel_orders_by_coverage(tmp_path: Path) -> None:
    """短词 LIKE 路：命中词数多的片段排前（覆盖度排序）。"""

    store = _store(tmp_path)
    store.add_note("线代", "矩阵的秩", "矩阵的秩等于其行阶梯形中非零行的数目。")
    store.add_note("线代", "矩阵", "矩阵是一个数表。")

    hits = store._search_terms_like(["矩阵", "秩"], None, 5)

    assert hits
    assert hits[0].title == "矩阵的秩"
    assert hits[0].score >= hits[-1].score


def test_short_query_still_searchable(tmp_path: Path) -> None:
    """短查询（两字词）端到端仍能命中。"""

    store = _store(tmp_path)
    store.add_note("线性代数", "矩阵的秩", "矩阵的秩等于其行阶梯形中非零行的数目。")

    hits = store.search("秩", limit=3)

    assert hits
    assert "非零行" in hits[0].content


def test_rrf_fuse_weights_lower_confidence_channel(tmp_path: Path) -> None:
    """权重：同分两命中时，高权通道里的片段排前。"""

    primary = [SearchHit(1, "A", "t", "c1", 1.0)]
    weak = [SearchHit(2, "A", "t", "c2", 1.0)]

    fused = rrf_fuse([primary, weak], k=60, weights=[1.0, 0.3])

    assert [hit.chunk_id for hit in fused] == [1, 2]


def test_rrf_fuse_zero_weight_channel_ignored() -> None:
    fused = rrf_fuse(
        [[SearchHit(1, "A", "t", "c1", 1.0)], [SearchHit(2, "A", "t", "c2", 1.0)]],
        k=60,
        weights=[1.0, 0.0],
    )

    assert [hit.chunk_id for hit in fused] == [1]


def test_library_scope_still_respected_with_expansion(tmp_path: Path) -> None:
    """扩写与短词路都必须守住学科库过滤，不能越界召回。"""

    store = _store(tmp_path)
    store.add_note("高等数学", "特征值与特征向量", "特征值描述伸缩倍数。")
    store.add_note("大学物理", "特征频率", "特征频率是系统的固有振动频率。")

    hits = store.search("本征值", libraries=["高等数学"], limit=5)

    assert hits
    assert all(hit.library == "高等数学" for hit in hits)


def test_expansion_does_not_break_hybrid_with_embedder(tmp_path: Path) -> None:
    """接上向量路后，扩写命中仍能排进前列。"""

    store = KnowledgeStore(
        tmp_path / "kb.db", embedder=MockHashEmbedding(256)
    )
    store.add_note(
        "线性代数", "特征值与特征向量", "特征值刻画线性变换在特征方向上的伸缩倍数。"
    )
    store.add_note("高等数学", "导数", "导数是瞬时变化率。")

    hits = store.search("本征值", limit=3)

    assert hits
    assert hits[0].title == "特征值与特征向量"
