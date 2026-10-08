from __future__ import annotations

from pathlib import Path

from studygraph.domain.models import SearchHit
from studygraph.domain.retrieval import rrf_fuse
from studygraph.infrastructure.embeddings import MockHashEmbedding, cosine
from studygraph.infrastructure.knowledge import KnowledgeStore, build_match_query


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


def test_build_match_query_expands_cjk_into_trigrams() -> None:
    query = build_match_query("特征值描述")
    assert '"特征值"' in query
    assert '"征值描"' in query
    assert " OR " in query


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
