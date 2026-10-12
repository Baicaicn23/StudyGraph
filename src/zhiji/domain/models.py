"""领域模型：跨层传递的纯数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    """一次检索命中的片段，带出处。"""

    chunk_id: int
    library: str
    title: str
    content: str
    score: float


@dataclass(frozen=True)
class Chunk:
    """知识库里的一个文本片段。"""

    id: int
    library: str
    title: str
    content: str
