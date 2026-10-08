"""学科知识库：文档/笔记的存储与混合检索（FTS + 向量 + RRF）。

设计要点：
- **存储**用 SQLite；全文检索用 **FTS5 trigram**——中文按 3-gram 切分，普通
  `unicode61` 分词器不切中文（整段当一个 token），中文查询会零命中。
- **中文长查询**拆成 3-gram 词项做 OR（整句当短语几乎不可能命中）；更短的
  查询走 `LIKE` 兜底。
- **向量检索**：每个片段算一个 Embedding，查询时算**余弦相似度**取 top-k。
- **RRF 融合**：把 FTS（关键词）与向量（语义）两路排名用 Reciprocal Rank
  Fusion 融合，取长补短。
- 结果带**出处**（哪个库、哪份资料），供回答引用。
"""

from __future__ import annotations

import re
import sqlite3
import time
from array import array
from dataclasses import dataclass, replace
from pathlib import Path

from .embeddings import BaseEmbedding, cosine

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TOKEN_SPLIT_RE = re.compile(r"[\s,，。！？!?、；;：:（）()\[\]「」《》\"'“”‘’]+")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS libraries (
    name TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_library ON documents(library);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library TEXT NOT NULL,
    title TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    content TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_library ON chunks(library);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    chunk_id UNINDEXED,
    library UNINDEXED,
    title UNINDEXED,
    tokenize='trigram'
);
CREATE TABLE IF NOT EXISTS chunk_vectors (
    chunk_id INTEGER PRIMARY KEY,
    library TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL
);
"""


@dataclass(frozen=True)
class SearchHit:
    chunk_id: int
    library: str
    title: str
    content: str
    score: float


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


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_match_query(query: str) -> str:
    """把自然语言查询转成 FTS5 的 OR 查询串。

    trigram 分词器按 3 字滑窗建索引，所以中文查询要拆成 3-gram 词项做 OR，
    而不是把整句当成一个短语——整句短语要求查询是资料的连续子串，几乎永不命中。
    纯英文/数字词整词保留。返回空串表示无法构造查询（交由 LIKE 兜底）。
    """

    terms: list[str] = []
    for token in _TOKEN_SPLIT_RE.split(query or ""):
        token = token.strip()
        if not token:
            continue
        if _CJK_RE.search(token) and len(token) > 3:
            terms.extend(token[i : i + 3] for i in range(len(token) - 2))
        else:
            terms.append(token)

    unique: list[str] = []
    for term in terms:
        if term not in unique:
            unique.append(term)
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in unique)


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


def _to_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _from_blob(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return values.tolist()


class KnowledgeStore:
    def __init__(
        self,
        db_path: str | Path,
        embedder: BaseEmbedding | None = None,
        *,
        recall_depth: int = 8,
        rrf_k: int = 60,
    ) -> None:
        self.db_path = str(db_path)
        self.embedder = embedder
        self.recall_depth = recall_depth
        self.rrf_k = rrf_k
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    # -- 写入 -----------------------------------------------------------------

    def ensure_library(self, name: str) -> None:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValueError("知识库名称不能为空")
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO libraries(name, created_at) VALUES (?, ?)",
                (cleaned, time.time()),
            )

    def add_document(self, library: str, title: str, content: str) -> int:
        self.ensure_library(library)
        now = time.time()
        chunks = chunk_text(content)
        vectors = (
            self.embedder.embed(chunks) if self.embedder and chunks else []
        )
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO documents(library, title, content, created_at) VALUES (?, ?, ?, ?)",
                (library, title, content, now),
            )
            document_id = int(cursor.lastrowid)
            for index, chunk in enumerate(chunks):
                chunk_cursor = connection.execute(
                    "INSERT INTO chunks(library, title, document_id, content) VALUES (?, ?, ?, ?)",
                    (library, title, document_id, chunk),
                )
                chunk_id = int(chunk_cursor.lastrowid)
                connection.execute(
                    "INSERT INTO chunks_fts(content, chunk_id, library, title) VALUES (?, ?, ?, ?)",
                    (chunk, chunk_id, library, title),
                )
                if index < len(vectors) and vectors[index]:
                    vector = vectors[index]
                    connection.execute(
                        "INSERT OR REPLACE INTO chunk_vectors(chunk_id, library, dim, vector) "
                        "VALUES (?, ?, ?, ?)",
                        (chunk_id, library, len(vector), _to_blob(vector)),
                    )
        return document_id

    def add_note(self, library: str, title: str, content: str) -> int:
        return self.add_document(library, title, content)

    # -- 查询 -----------------------------------------------------------------

    def list_libraries(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT l.name AS name, COUNT(d.id) AS document_count
                FROM libraries l
                LEFT JOIN documents d ON d.library = l.name
                GROUP BY l.name
                ORDER BY l.created_at
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def search(
        self,
        query: str,
        *,
        libraries: list[str] | None = None,
        limit: int = 4,
    ) -> list[SearchHit]:
        cleaned = (query or "").strip()
        if not cleaned:
            return []
        fts = self._search_match(cleaned, libraries, self.recall_depth)
        vectors = self._search_vectors(cleaned, libraries, self.recall_depth)
        fused = rrf_fuse([fts, vectors], k=self.rrf_k)[:limit]
        if not fused:
            fused = self._search_like(cleaned, libraries, limit)
        return fused

    def _library_filter(self, libraries: list[str] | None) -> tuple[str, list[object]]:
        if not libraries:
            return "", []
        placeholders = ", ".join("?" for _ in libraries)
        return f" AND library IN ({placeholders})", list(libraries)

    def _search_match(
        self, query: str, libraries: list[str] | None, limit: int
    ) -> list[SearchHit]:
        match = build_match_query(query)
        if not match:
            return []
        clause, params = self._library_filter(libraries)
        sql = (
            "SELECT chunk_id, library, title, content, bm25(chunks_fts) AS rank "
            "FROM chunks_fts WHERE chunks_fts MATCH ?" + clause + " ORDER BY rank LIMIT ?"
        )
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, [match, *params, limit]).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            SearchHit(
                chunk_id=int(row["chunk_id"]),
                library=str(row["library"]),
                title=str(row["title"]),
                content=str(row["content"]),
                score=-float(row["rank"]),
            )
            for row in rows
        ]

    def _search_like(
        self, query: str, libraries: list[str] | None, limit: int
    ) -> list[SearchHit]:
        clause, params = self._library_filter(libraries)
        sql = (
            "SELECT chunk_id, library, title, content FROM chunks_fts "
            "WHERE content LIKE ? ESCAPE '\\'" + clause + " LIMIT ?"
        )
        pattern = f"%{_escape_like(query)}%"
        with self._connect() as connection:
            rows = connection.execute(sql, [pattern, *params, limit]).fetchall()
        return [
            SearchHit(
                chunk_id=int(row["chunk_id"]),
                library=str(row["library"]),
                title=str(row["title"]),
                content=str(row["content"]),
                score=1.0,
            )
            for row in rows
        ]

    def _search_vectors(
        self, query: str, libraries: list[str] | None, limit: int
    ) -> list[SearchHit]:
        if self.embedder is None:
            return []
        query_vector = self.embedder.embed([query])[0]
        if not query_vector:
            return []
        clause, params = self._library_filter(libraries)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT chunk_id, library, vector FROM chunk_vectors WHERE dim=?"
                + clause,
                [len(query_vector), *params],
            ).fetchall()

        scored: list[tuple[float, int, str]] = []
        for row in rows:
            similarity = cosine(query_vector, _from_blob(row["vector"]))
            if similarity > 0:
                scored.append((similarity, int(row["chunk_id"]), str(row["library"])))
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:limit]
        if not top:
            return []

        ids = [chunk_id for _score, chunk_id, _library in top]
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            detail_rows = connection.execute(
                f"SELECT id, title, content FROM chunks WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        details = {
            int(row["id"]): (str(row["title"]), str(row["content"]))
            for row in detail_rows
        }
        hits: list[SearchHit] = []
        for similarity, chunk_id, library in top:
            title, content = details.get(chunk_id, ("", ""))
            hits.append(
                SearchHit(
                    chunk_id=chunk_id,
                    library=library,
                    title=title,
                    content=content,
                    score=similarity,
                )
            )
        return hits
