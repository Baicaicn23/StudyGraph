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


# -- 轻量精排（词面证据重排） --------------------------------------------------
#
# 为什么需要它：RRF 只用**排名**融合，本身不判断"这条命中是否真的贴着查询"。
# 当某一路召回不可靠时（典型：没接真实 embedding、或语义模型与本领域不匹配），
# 它会以同样的权重把"词面毫无关系"的候选混进结果。精排用**字面证据**对这些
# 候选重新打分——纯函数、零模型、零网络，可离线单测。
#
# 注意：这里**不复用** `knowledge._query_terms()`。那条路径决定召回集合，动它会
# 改变评测基线；精排只调**顺序**，不增删候选，两者职责分离。

_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fd5]+")
_ASCII_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]*")

# 只在疑问句里出现、对匹配没有区分度的二字组合（命中它们不代表相关）
_LOW_VALUE_SHINGLES = frozenset(
    {
        "什么", "到底", "怎么", "怎样", "多少", "哪个", "哪些", "如何", "为什",
        "是否", "是不", "不是", "可以", "需要", "一下", "这个", "那个", "它的",
        "的吗", "了吗", "有什", "么含", "含义", "意思", "区别",
    }
)


def _shingles(text: str) -> set[str]:
    """把文本压成"检索单元"集合：中文用二字切片、英文用整词（小写）。

    中文不做分词而用二字切片，是因为切片不依赖词典，且天然覆盖"征值"这类
    跨词边界但仍有区分度的片段。
    """

    units: set[str] = set()
    for run in _CJK_RUN_RE.findall(str(text or "")):
        for index in range(len(run) - 1):
            gram = run[index : index + 2]
            if gram not in _LOW_VALUE_SHINGLES:
                units.add(gram)
    for word in _ASCII_WORD_RE.findall(str(text or "")):
        if len(word) >= 2:
            units.add(word.lower())
    return units


def rerank_hits(
    hits: list[SearchHit],
    query: str,
    *,
    expansion: tuple[str, ...] | list[str] = (),
    blend: float = 0.6,
) -> list[SearchHit]:
    """按词面证据对候选重排（确定性）。

    打分 = RRF 归一化分 + ``blend × 词面分``；词面分由三部分构成：

    - **原查询字面覆盖**（0.50）：查询自身的二字切片 / 英文词命中比例，最有说服力；
    - **同义扩写覆盖**（0.15）：由扩写词命中，权重更低——扩写是推断；
    - **标题命中**（0.35）：命中落在标题上，通常意味着"这份资料就是在讲这件事"。

    只调顺序、不增删候选；查询无可用单元时原样返回。
    """

    query_units = _shingles(query)
    extra_units = _shingles(" ".join(str(item) for item in expansion)) - query_units
    if not query_units and not extra_units:
        return hits

    top = max((hit.score for hit in hits), default=0.0) or 1.0
    scored: list[tuple[float, float, SearchHit]] = []
    for hit in hits:
        doc_units = _shingles(f"{hit.title} {hit.content}")
        title_units = _shingles(hit.title)
        literal = (
            len(query_units & doc_units) / len(query_units) if query_units else 0.0
        )
        expanded = (
            len(extra_units & doc_units) / len(extra_units) if extra_units else 0.0
        )
        in_title = (
            len(query_units & title_units) / len(query_units) if query_units else 0.0
        )
        lexical = 0.50 * literal + 0.15 * expanded + 0.35 * in_title
        blended = hit.score / top + blend * lexical
        scored.append((blended, hit.score, hit))

    # 融合分相同再按原始 RRF 分（保证同分时不让纯词面把基础排序完全推翻）
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [replace(hit, score=round(blended, 6)) for blended, _raw, hit in scored]
