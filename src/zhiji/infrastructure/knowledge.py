"""学科知识库：SQLite 存储 + 混合检索（FTS trigram + 向量 + RRF）。

`KnowledgePort` 的 SQLite 实现。纯算法（切块、RRF、同义扩写）在领域层
（`domain/retrieval.py`、`domain/synonyms.py`），查询语法等存储细节留在这里。

检索是**四路召回 + RRF 融合**：原查询 FTS、同义词扩写 FTS、短词 LIKE
（trigram 索引不到的两字中文词）、向量。扩写路按低权重计入——它是推断出来的
召回，不该与字面命中平起平坐。
"""

from __future__ import annotations

import re
import sqlite3
import time
from array import array
from pathlib import Path

from ..domain.models import Chunk, SearchHit
from ..domain.retrieval import chunk_markdown, chunk_pages, rrf_fuse
from ..domain.synonyms import expand_terms
from .embeddings import cosine

try:  # 词级分词（可选依赖）：查询切词比滑窗 3-gram 噪声小
    import jieba
except ImportError:  # pragma: no cover
    jieba = None

_HAS_WORD_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TWO_CJK_RE = re.compile(r"^[\u4e00-\u9fff]{2}$")
_TOKEN_SPLIT_RE = re.compile(r"[\s,，。！？!?、；;：:（）()\[\]「」《》\"'“”‘’]+")

# 疑问/指代/虚词：查询里的高频噪声。两字词要进 LIKE 路前先剔掉，否则
# 「矩阵的秩怎么求」会变成"矩阵 AND 的 AND 秩 AND 怎么 AND 求"，把召回掐死。
_STOPWORDS = frozenset(
    {
        "什么",
        "怎么",
        "怎样",
        "如何",
        "为何",
        "哪些",
        "哪个",
        "哪里",
        "是否",
        "能否",
        "可以",
        "请问",
        "帮我",
        "告诉",
        "一下",
        "一些",
        "有没有",
        "我们",
        "我的",
        "你的",
        "他的",
        "这个",
        "那个",
        "这种",
        "那种",
        "是指",
        "指的",
        "内容",
        "东西",
        "时候",
    }
)

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


def _dedupe(terms: list[str]) -> list[str]:
    unique: list[str] = []
    for term in terms:
        if term and term not in unique:
            unique.append(term)
    return unique


def _phrase(term: str) -> str:
    """FTS5 短语字面量：双引号包裹，内部双引号翻倍转义。"""

    return '"' + term.replace('"', '""') + '"'


def _query_terms(query: str) -> list[str]:
    """查询 → FTS 检索词。

    优先 jieba **词级**：≥3 字的词直接做短语——比滑窗 3-gram 噪声小
    （3-gram 会切出"态规""划适"这类跨词垃圾）。两字词进不了 trigram 索引，
    由 `short_cjk_terms` + `_search_terms_like` 兜底。jieba 不可用或切不出
    ≥3 字词时，回落旧的 3-gram 策略。
    """

    terms: list[str] = []
    if jieba is not None:
        for word in jieba.cut_for_search(query or ""):
            word = word.strip()
            if len(word) >= 3 and _HAS_WORD_RE.search(word) and word not in terms:
                terms.append(word)
    if not terms:
        for token in _TOKEN_SPLIT_RE.split(query or ""):
            token = token.strip()
            if not token:
                continue
            if _CJK_RE.search(token) and len(token) > 3:
                terms.extend(token[i : i + 3] for i in range(len(token) - 2))
            else:
                terms.append(token)
    return _dedupe(terms)


def build_match_query(query: str) -> str:
    """把自然语言查询转成 FTS5 的 OR 查询串。返回空串表示无法构造查询（交由 LIKE 兜底）。"""

    return " OR ".join(_phrase(term) for term in _query_terms(query))


def short_cjk_terms(query: str, *, limit: int = 4) -> list[str]:
    """取出查询里的**两字中文词**（trigram 索引不到，须走 LIKE 路）。

    这是原有链路的真实空洞：`build_match_query` 只收 ≥3 字词，于是
    「矩阵的秩怎么求」里的「矩阵」「秩」被静默丢弃、「导数的几何意义」只剩
    "数的几何"。「矩阵」「秩」「导数」「队列」这类两字词恰恰是学科资料里
    信息量最高的术语。jieba 不可用时按 2 字滑窗兜底。
    """

    raw: list[str] = []
    if jieba is not None:
        raw = [word.strip() for word in jieba.cut_for_search(query or "")]
    if not raw:
        raw = _TOKEN_SPLIT_RE.split(query or "")
    found: list[str] = []
    for word in raw:
        if (
            _TWO_CJK_RE.match(word)
            and word not in _STOPWORDS
            and word not in found
        ):
            found.append(word)
    return found[:limit]


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
        synonym_groups: tuple[tuple[str, ...], ...] | None = None,
        expansion_weight: float = 0.5,
    ) -> None:
        self.db_path = str(db_path)
        self.embedder = embedder
        self.recall_depth = recall_depth
        self.rrf_k = rrf_k
        # None → 内置同义词组；传 () 可彻底关闭扩写
        self.synonym_groups = synonym_groups
        self.expansion_weight = expansion_weight
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.files_root = Path(self.db_path).parent / "knowledge_files"
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
            # 原样文件存储（PDF/Word 等二进制资料直接落盘，不解析）：
            # 旧库平滑迁移——缺哪列补哪列
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "kind" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN kind TEXT NOT NULL DEFAULT 'text'"
                )
            if "file_path" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN file_path TEXT"
                )
            if "file_size" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN file_size INTEGER"
                )
        self.files_root.mkdir(parents=True, exist_ok=True)

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
            self._index_chunks(
                connection,
                library=library,
                title=title,
                document_id=document_id,
                content=content,
            )
        return document_id

    def save_file_document(
        self,
        library: str,
        title: str,
        filename: str,
        data: bytes,
    ) -> int:
        """原样保存二进制资料（PDF/Word 等）：文件落盘 + 建一条 kind=file 的文档。

        不做任何解析/切块/向量化——需要参与检索问答时由用户手动触发解析。
        """

        self.ensure_library(library)
        now = time.time()
        safe = re.sub(r'[:/\\*?"<>|]+', "_", filename.strip() or "未命名").strip(".") or "未命名"
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO documents(library, title, content, kind, created_at) "
                "VALUES (?, ?, '', 'file', ?)",
                (library, title, now),
            )
            document_id = int(cursor.lastrowid)
        rel_name = f"{document_id}__{safe}"
        target = self.files_root / rel_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET file_path = ?, file_size = ? WHERE id = ?",
                (rel_name, len(data), document_id),
            )
        return document_id

    def get_document_file(
        self, document_id: int
    ) -> dict[str, str] | None:
        """取原样文件的落盘路径与文件名（下载/内联预览用）。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, title, file_path FROM documents "
                "WHERE id = ? AND kind = 'file' AND file_path IS NOT NULL",
                (document_id,),
            ).fetchone()
        if row is None or not row["file_path"]:
            return None
        return {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "path": str(self.files_root / row["file_path"]),
            "stored_name": str(row["file_path"]),
        }

    def attach_text_content(
        self,
        document_id: int,
        content: str,
        *,
        pages: list[tuple[str | None, str]] | None = None,
    ) -> int:
        """给 kind=file 的文档补上文本内容并建立检索索引（懒解析用）。

        同时把 kind 升级为 'file_text'——原件保留，文本视图与检索从此可用。
        ``pages`` 是按页拆分的 (页码标签, 页文本) 列表；给了就按页切块、块带
        页码出处，否则整篇盲切。返回建立的切块数。
        """

        with self._connect() as connection:
            row = connection.execute(
                "SELECT library, title FROM documents WHERE id = ? AND kind = 'file'",
                (document_id,),
            ).fetchone()
            if row is None:
                raise ValueError("文档不存在或不是原样文件")
            self._drop_document_index(connection, document_id=document_id)
            connection.execute(
                "UPDATE documents SET content = ?, kind = 'file_text' WHERE id = ?",
                (content, document_id),
            )
            indexed = self._index_chunks(
                connection,
                library=str(row["library"]),
                title=str(row["title"]),
                document_id=document_id,
                content=content,
                pages=pages,
            )
        return indexed

    def add_note(self, library: str, title: str, content: str) -> int:
        return self.add_document(library, title, content)

    # -- 更新 / 删除 ----------------------------------------------------------

    def _index_chunks(
        self,
        connection: sqlite3.Connection,
        *,
        library: str,
        title: str,
        document_id: int,
        content: str,
        pages: list[tuple[str | None, str]] | None = None,
    ) -> None:
        """切块 + 向量化 + 写入 chunks / FTS / 向量表（新增与改写共用）。

        ``pages`` 给了就走按页切块（块带页码出处），否则整篇盲切。
        """

        chunks = chunk_pages(pages) if pages else chunk_markdown(content)
        vectors: list[list[float]] = []
        if self.embedder and chunks:
            # 向量服务故障不能拦 FTS 路——入库与检索照常，只是少了语义这一路
            try:
                vectors = self.embedder.embed(chunks)
            except Exception:  # noqa: BLE001 — 降级为纯关键词检索
                vectors = []
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

    @staticmethod
    def _drop_document_index(
        connection: sqlite3.Connection, *, document_id: int
    ) -> None:
        """清掉一份资料的全部检索索引（chunks / FTS / 向量）。"""

        chunk_ids = [
            int(row["id"])
            for row in connection.execute(
                "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
            ).fetchall()
        ]
        if not chunk_ids:
            return
        placeholders = ", ".join("?" for _ in chunk_ids)
        connection.execute(
            f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})", chunk_ids
        )
        connection.execute(
            f"DELETE FROM chunk_vectors WHERE chunk_id IN ({placeholders})", chunk_ids
        )
        connection.execute(
            f"DELETE FROM chunks WHERE id IN ({placeholders})", chunk_ids
        )

    def update_document(
        self, document_id: int, *, title: str, content: str
    ) -> bool:
        """改写资料：标题/正文更新并重建检索索引；不存在返回 False。"""

        title = (title or "").strip()
        content = content or ""
        if not title:
            raise ValueError("标题不能为空")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT library FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row is None:
                return False
            library = str(row["library"])
            self._drop_document_index(connection, document_id=document_id)
            connection.execute(
                "UPDATE documents SET title = ?, content = ? WHERE id = ?",
                (title, content, document_id),
            )
            self._index_chunks(
                connection,
                library=library,
                title=title,
                document_id=document_id,
                content=content,
            )
        return True

    def delete_document(self, document_id: int) -> bool:
        """删除一份资料及其全部检索索引；不存在返回 False。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row is None:
                return False
            self._drop_document_index(connection, document_id=document_id)
            connection.execute(
                "DELETE FROM documents WHERE id = ?", (document_id,)
            )
        return True

    def delete_library(self, name: str) -> bool:
        """删除整个学科库：连库里所有资料与检索索引一起删；不存在返回 False。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT name FROM libraries WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                return False
            doc_ids = [
                int(r["id"])
                for r in connection.execute(
                    "SELECT id FROM documents WHERE library = ?", (name,)
                ).fetchall()
            ]
            for document_id in doc_ids:
                self._drop_document_index(connection, document_id=document_id)
            connection.execute("DELETE FROM documents WHERE library = ?", (name,))
            connection.execute("DELETE FROM chunks WHERE library = ?", (name,))
            connection.execute("DELETE FROM chunks_fts WHERE library = ?", (name,))
            connection.execute(
                "DELETE FROM chunk_vectors WHERE library = ?", (name,)
            )
            connection.execute("DELETE FROM libraries WHERE name = ?", (name,))
        return True

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
                "SELECT id, library, title, content, created_at, kind, "
                "file_path, file_size FROM documents WHERE id = ?",
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
            "kind": str(row["kind"] or "text"),
            "file_path": row["file_path"],
            "file_size": row["file_size"],
        }

    def list_documents(self, library: str) -> list[dict[str, object]]:
        """列出某学科库下的资料（标题 + 时间 + 字数），供资料列表页使用。"""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, kind, file_size,
                LENGTH(content) AS chars
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
                "kind": str(row["kind"] or "text"),
                "file_size": row["file_size"],
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

        # 同义/中英扩写：≥3 字词可进 trigram FTS，<3 字词（如「队列」）只能走 LIKE
        expansion = expand_terms(cleaned, self.synonym_groups)
        expansion_long = [term for term in expansion if len(term) >= 3]
        lexical = _dedupe(
            [*[term for term in expansion if len(term) < 3], *short_cjk_terms(cleaned)]
        )[:4]

        rankings = [
            self._search_match(cleaned, libraries, self.recall_depth),
            self._search_match(
                cleaned, libraries, self.recall_depth, extra_terms=expansion_long
            ),
            self._search_terms_like(lexical, libraries, self.recall_depth),
            self._search_vectors(cleaned, libraries, self.recall_depth),
        ]
        # 权重：原查询字面命中最高，扩写路按推断降权；短词 LIKE 与向量居中
        weights = [1.0, self.expansion_weight, 0.8, 1.0]
        fused = rrf_fuse(rankings, k=self.rrf_k, weights=weights)[:limit]
        if not fused:
            fused = self._search_like(cleaned, libraries, limit)
        return fused

    def _library_filter(self, libraries: list[str] | None) -> tuple[str, list[object]]:
        if not libraries:
            return "", []
        placeholders = ", ".join("?" for _ in libraries)
        return f" AND library IN ({placeholders})", list(libraries)

    def _search_match(
        self,
        query: str,
        libraries: list[str] | None,
        limit: int,
        *,
        extra_terms: list[str] | None = None,
    ) -> list[SearchHit]:
        terms = _dedupe([*_query_terms(query), *(extra_terms or [])])
        if not terms:
            return []
        match = " OR ".join(_phrase(term) for term in terms)
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

    def _search_terms_like(
        self, terms: list[str], libraries: list[str] | None, limit: int
    ) -> list[SearchHit]:
        """短词的 LIKE 召回：逐词匹配，**命中词数越多排名越前**。

        两字中文词（矩阵 / 秩 / 导数 / 队列）进不了 trigram 索引。老链路只在
        FTS + 向量**全空**时才用"整条查询当子串"兜底——「矩阵的秩怎么求」于是
        要求原文出现这七个字，召回窄得离谱。这里改成逐词 LIKE 并按命中覆盖数
        排序：既让「矩阵 + 秩」双命中的片段排前，也允许只命中一个词的片段
        进入后续 RRF 融合（权重低于字面命中路）。
        """

        words = _dedupe([term for term in terms if term])
        if not words:
            return []
        clause, params = self._library_filter(libraries)
        coverage = " + ".join("(content LIKE ? ESCAPE '\\')" for _ in words)
        sql = (
            "SELECT chunk_id, library, title, content, hits FROM ("
            "SELECT chunk_id, library, title, content, "
            f"({coverage}) AS hits FROM chunks_fts WHERE 1=1{clause}"
            ") WHERE hits >= 1 ORDER BY hits DESC LIMIT ?"
        )
        patterns = [f"%{_escape_like(word)}%" for word in words]
        with self._connect() as connection:
            rows = connection.execute(sql, [*patterns, *params, limit]).fetchall()
        return [
            SearchHit(
                chunk_id=int(row["chunk_id"]),
                library=str(row["library"]),
                title=str(row["title"]),
                content=str(row["content"]),
                score=float(row["hits"]),
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
        try:
            query_vector = self.embedder.embed([query])[0]
        except Exception:  # noqa: BLE001 — 查询向量化失败 → 语义路返回空
            return []
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
