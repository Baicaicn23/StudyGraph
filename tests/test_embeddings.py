from __future__ import annotations

from pathlib import Path

from zhiji.domain.models import SearchHit
from zhiji.domain.retrieval import rrf_fuse
from zhiji.infrastructure.embeddings import MockHashEmbedding, cosine
from zhiji.infrastructure.knowledge import KnowledgeStore, build_match_query


def test_mock_embedding_is_deterministic_and_normalized() -> None:
    embedder = MockHashEmbedding(dim=128)
    first = embedder.embed(["特征值描述缩放倍数"])[0]
    second = embedder.embed(["特征值描述缩放倍数"])[0]
    assert first == second
    assert len(first) == 128
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_similar_text_scores_higher_than_unrelated() -> None:
    embedder = MockHashEmbedding(dim=256)
    base, similar, other = embedder.embed(
        ["导数是瞬时变化率", "导数是变化率", "矩阵的秩是非零行的数目"]
    )
    assert cosine(base, similar) > cosine(base, other)


def test_build_match_query_uses_jieba_word_terms() -> None:
    """jieba 词级查询：≥3 字词做短语；不再产生跨词 3-gram（"征值描"这类噪声）。"""

    query = build_match_query("特征值描述")
    assert '"特征值"' in query
    assert '"征值描"' not in query
    assert '"值描述"' not in query


def test_build_match_query_falls_back_to_trigrams_without_words() -> None:
    """jieba 可用 → 词级短语；切不出 ≥3 字词或不可用 → 回落旧 3-gram 策略。"""

    # jieba 把 ≥3 字的词做成短语（无跨词垃圾 gram）
    query = build_match_query("求解定积分的计算方法")
    assert '"计算方法"' in query
    assert '"算的计"' not in query  # 旧 3-gram 的跨词噪声不再出现

    # 无 jieba 时的旧路径仍能构造
    from zhiji.infrastructure import knowledge

    saved = knowledge.jieba
    knowledge.jieba = None
    try:
        query = build_match_query("特征值描述")
        assert '"特征值"' in query and '"征值描"' in query
    finally:
        knowledge.jieba = saved


def test_rrf_fuse_merges_two_rankings() -> None:
    fts = [
        SearchHit(1, "A", "t", "c1", 3.0),
        SearchHit(2, "A", "t", "c2", 2.0),
    ]
    vectors = [
        SearchHit(2, "A", "t", "c2", 0.9),
        SearchHit(3, "A", "t", "c3", 0.8),
    ]

    fused = rrf_fuse([fts, vectors], k=60)

    # 2 在两路都出现，理应排第一。
    assert fused[0].chunk_id == 2
    assert {hit.chunk_id for hit in fused} == {1, 2, 3}


def test_vector_search_finds_lexically_different_chunk(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db", embedder=MockHashEmbedding(256))
    store.add_note("线性代数", "特征值与特征向量", "特征值刻画线性变换在特征方向上的伸缩比。")
    store.add_note("高等数学", "导数", "导数衡量函数在某点的瞬时变化快慢。")

    vectors = store._search_vectors("特征向量对应的伸缩比", None, 5)

    assert vectors
    assert vectors[0].library == "线性代数"


def test_hybrid_search_still_returns_sources(tmp_path: Path) -> None:
    store = KnowledgeStore(tmp_path / "kb.db", embedder=MockHashEmbedding(256))
    store.add_note("高等数学", "导数", "导数是瞬时变化率，反映切线斜率。")

    hits = store.search("导数是瞬时变化率吗", libraries=["高等数学"], limit=3)

    assert hits
    assert hits[0].library == "高等数学"
    assert "切线斜率" in hits[0].content
