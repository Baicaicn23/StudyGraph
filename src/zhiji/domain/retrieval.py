"""检索的领域算法（纯函数）：切块与 RRF 融合排名。

与具体存储无关——RRF 是通用的排名融合算法，切块是通用的文本处理，所以放在
领域层；FTS 的查询语法属于基础设施细节，放在 `infrastructure/knowledge.py`。
"""

from __future__ import annotations

import re
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


def chunk_pages(
    pages: list[tuple[str | None, str]], *, max_chars: int = 480, overlap: int = 80
) -> list[str]:
    """按页切块：每页独立走 `chunk_text`，每块前带页码出处（如「【第 3 页】」）。

    PPT 一页 slide、PDF 一页就是一个自然边界，比整篇盲切更贴合出处引用——
    检索命中后引文能落到具体页。页码标签随块进入 FTS/向量索引，是无害的可搜文本。
    """

    chunks: list[str] = []
    for label, page_text in pages:
        cleaned = (page_text or "").strip()
        if not cleaned:
            continue
        prefix = f"【{label}】" if label else ""
        for piece in chunk_text(cleaned, max_chars=max_chars, overlap=overlap):
            chunks.append(f"{prefix}{piece}" if prefix else piece)
    return chunks


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")


def chunk_markdown(
    content: str, *, max_chars: int = 480, overlap: int = 80
) -> list[str]:
    """按 Markdown 标题结构切块：标题做块前缀出处（如「【三、方法】」）。

    资料自带结构（# 标题）时按结构切比盲切贴合语义——标题和它的内容不分离，
    长小节再按字数细切。无标题的纯文本回落 `chunk_text` 盲切。
    """

    text = (content or "").strip()
    if not text:
        return []
    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    body_lines: list[str] = []
    for line in text.splitlines():
        heading = _MD_HEADING_RE.match(line)
        if heading:
            if current_title is not None or body_lines:
                sections.append((current_title, body_lines))
            current_title = heading.group(2).strip()
            body_lines = []
        else:
            body_lines.append(line)
    sections.append((current_title, body_lines))

    # 没有任何标题 → 纯文本，盲切
    if len(sections) == 1 and sections[0][0] is None:
        return chunk_text(text, max_chars=max_chars, overlap=overlap)

    chunks: list[str] = []
    for title, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        prefix = f"【{title}】" if title else ""
        for piece in chunk_text(body, max_chars=max_chars, overlap=overlap):
            chunks.append(f"{prefix}{piece}" if prefix else piece)
    return chunks or chunk_text(text, max_chars=max_chars, overlap=overlap)


def rrf_fuse(
    rankings: list[list[SearchHit]],
    *,
    k: int = 60,
    weights: list[float] | None = None,
) -> list[SearchHit]:
    """Reciprocal Rank Fusion：把多路排名按 ``weight/(k+rank)`` 相加融合。

    只用排名、不用原始分数，所以能把"关键词命中"和"语义相似"两种不可比的分数
    放在一起比较。

    ``weights`` 与 ``rankings`` 一一对应（缺省全 1.0）——用于给**置信度较低**
    的召回路降权：同义词扩写路靠推断补召回，不该与"原查询字面命中"平起平坐。
    """

    scores: dict[int, float] = {}
    hits: dict[int, SearchHit] = {}
    for channel, ranking in enumerate(rankings):
        weight = 1.0
        if weights is not None and channel < len(weights):
            weight = float(weights[channel])
        if weight <= 0:
            continue
        for rank, hit in enumerate(ranking):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + weight / (
                k + rank + 1
            )
            hits[hit.chunk_id] = hit
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [replace(hits[chunk_id], score=scores[chunk_id]) for chunk_id in ordered]
