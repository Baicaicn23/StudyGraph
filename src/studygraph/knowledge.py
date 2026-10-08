"""学科知识库：文档/笔记的存储与全文检索。

设计取舍：
- **存储**用 SQLite，检索用 **FTS5 trigram 分词**——中文按 3-gram 切分，
  普通 `unicode61` 分词器不切中文（整段当一个 token），中文查询会零命中。
- trigram 要求查询串 ≥3 字符；更短的查询（如两字词）走 `LIKE` 兜底。
- 返回结果带**出处**（哪个库、哪份资料），供回答引用。

向量检索 / RRF 融合是后续里程碑（见 docs/架构设计.md 的路线），
本模块把接口留成 `search(query, libraries, limit)`。
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

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
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    library UNINDEXED,
    title UNINDEXED,
    doc_id UNINDEXED,
    tokenize='trigram'
);
"""


@dataclass(frozen=True)
class SearchHit:
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



class KnowledgeStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
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
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO documents(library, title, content, created_at) VALUES (?, ?, ?, ?)",
                (library, title, content, now),
            )
            document_id = int(cursor.lastrowid)
            for chunk in chunk_text(content):
                connection.execute(
                    "INSERT INTO chunks_fts(content, library, title, doc_id) VALUES (?, ?, ?, ?)",
                    (chunk, library, title, document_id),
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
        hits = self._search_match(cleaned, libraries, limit)
        if not hits:
            hits = self._search_like(cleaned, libraries, limit)
        return hits

    def _library_filter(self, libraries: list[str] | None) -> tuple[str, list[object]]:
        if not libraries:
            return "", []
        placeholders = ", ".join("?" for _ in libraries)
        return f" AND library IN ({placeholders})", list(libraries)

    def _search_match(
        self, query: str, libraries: list[str] | None, limit: int
    ) -> list[SearchHit]:
        clause, params = self._library_filter(libraries)
        match = build_match_query(query)
        if not match:
            return []
        sql = (
            "SELECT library, title, content, bm25(chunks_fts) AS rank "
            "FROM chunks_fts WHERE chunks_fts MATCH ?" + clause + " ORDER BY rank LIMIT ?"
        )
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, [match, *params, limit]).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            SearchHit(
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
            "SELECT library, title, content FROM chunks_fts "
            "WHERE content LIKE ? ESCAPE '\\'" + clause + " LIMIT ?"
        )
        pattern = f"%{_escape_like(query)}%"
        with self._connect() as connection:
            rows = connection.execute(sql, [pattern, *params, limit]).fetchall()
        return [
            SearchHit(
                library=str(row["library"]),
                title=str(row["title"]),
                content=str(row["content"]),
                score=1.0,
            )
            for row in rows
        ]
