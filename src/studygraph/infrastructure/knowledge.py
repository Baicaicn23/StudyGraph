"""学科知识库：SQLite 存储 + 混合检索（FTS trigram + 向量 + RRF）。

`KnowledgePort` 的 SQLite 实现。纯算法（切块、RRF）在领域层
（`domain/retrieval.py`），查询语法等存储细节留在这里。
"""

from __future__ import annotations

import re
import sqlite3
import time
from array import array
from pathlib import Path

from ..domain.models import Chunk, SearchHit
from ..domain.retrieval import chunk_text, rrf_fuse
from .embeddings import cosine

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


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_match_query(query: str) -> str:
    """把自然语言查询转成 FTS5 的 OR 查询串（中文拆 3-gram 词项）。

    整句当短语要求查询是资料的连续子串，几乎永不命中；拆成 3-gram 做 OR 才能
    命中。返回空串表示无法构造查询（交由 LIKE 兜底）。
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


def _to_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _from_blob(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return values.tolist()


class KnowledgeStore:
    """`KnowledgePort` 的 SQLite 实现。"""

    def __init__(
        self,
        db_path: str | Path,
        embedder=None,
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
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
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
        vectors = self.embedder.embed(chunks) if self.embedder and chunks else []
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

    def get_document(self, document_id: int) -> dict[str, object] | None:
        """取单份资料的完整内容（正文渲染用）。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, library, title, content, created_at "
                "FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "library": str(row["library"]),
            "title": str(row["title"]),
            "content": str(row["content"]),
            "created_at": float(row["created_at"]),
        }

    def list_documents(self, library: str) -> list[dict[str, object]]:
        """列出某学科库下的资料（标题 + 时间 + 字数），供资料列表页使用。"""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, LENGTH(content) AS chars
                FROM documents WHERE library = ?
                ORDER BY created_at DESC, id DESC
                """,
                (library,),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "title": str(row["title"]),
                "created_at": float(row["created_at"]),
                "chars": int(row["chars"]),
            }
            for row in rows
        ]

    def list_chunks(self, *, library: str | None = None) -> list[Chunk]:
        sql = "SELECT id, library, title, content FROM chunks"
        params: list[object] = []
        if library is not None:
            sql += " WHERE library = ?"
            params.append(library)
        sql += " ORDER BY id"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [
            Chunk(
                id=int(row["id"]),
                library=str(row["library"]),
                title=str(row["title"]),
                content=str(row["content"]),
            )
            for row in rows
        ]

    def search(
        self, query: str, *, libraries: list[str] | None = None, limit: int = 4
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
                "SELECT chunk_id, library, vector FROM chunk_vectors WHERE dim=?" + clause,
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
                f"SELECT id, title, content FROM chunks WHERE id IN ({placeholders})", ids
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
