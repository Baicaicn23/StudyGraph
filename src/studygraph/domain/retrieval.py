"""检索的领域算法（纯函数）：切块与 RRF 融合排名。

与具体存储无关——RRF 是通用的排名融合算法，切块是通用的文本处理，所以放在
领域层；FTS 的查询语法属于基础设施细节，放在 `infrastructure/knowledge.py`。
"""

from __future__ import annotations

from dataclasses import replace

from .models import SearchHit


def chunk_text(text: str, *, max_chars: int = 480, overlap: int = 80) -> list[str]:
    """把长文本切成带重叠的片段。重叠是为了避免答案正好被切在边界上。"""

    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = end - overlap
    return chunks


def rrf_fuse(rankings: list[list[SearchHit]], *, k: int = 60) -> list[SearchHit]:
    """Reciprocal Rank Fusion：把多路排名按 ``1/(k+rank)`` 相加融合。

    只用排名、不用原始分数，所以能把"关键词命中"和"语义相似"两种不可比的分数
    放在一起比较。
    """

    scores: dict[int, float] = {}
    hits: dict[int, SearchHit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            hits[hit.chunk_id] = hit
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [replace(hits[chunk_id], score=scores[chunk_id]) for chunk_id in ordered]
