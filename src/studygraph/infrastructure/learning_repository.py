"""学习闭环的 SQLite 仓储——`LearningRepositoryPort` 的实现。

数据都落同一个库文件（与会话检查点、知识库共用）。核心约束：
- 练习题有 `due_at`：新题立即到期，答完按自评推迟（间隔重复）。
- 掌握度按学科维护（0~100）。
- `(user_id, source_feedback_id)` 上建**部分唯一索引**：一条误区只出一道题。
"""

from __future__ import annotations

import datetime
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    library TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS practice_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    library TEXT NOT NULL,
    prompt TEXT NOT NULL,
    source TEXT NOT NULL,
    source_chunk_id INTEGER,
    source_feedback_id INTEGER,
    created_at REAL NOT NULL,
    due_at REAL NOT NULL,
    answered_count INTEGER NOT NULL DEFAULT 0,
    last_rating TEXT
);
CREATE INDEX IF NOT EXISTS idx_pq_due ON practice_questions(user_id, due_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pq_feedback
    ON practice_questions(user_id, source_feedback_id)
    WHERE source_feedback_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS practice_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    rating TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS practice_progress (
    user_id TEXT NOT NULL,
    library TEXT NOT NULL,
    mastery INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (user_id, library)
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (user_id, content)
);
"""


class SqliteLearningRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    # -- 错题 -----------------------------------------------------------------

    def add_feedback(
        self, *, user_id: str, library: str, question: str, note: str
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO feedback(user_id, library, question, note, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, library.strip(), question.strip(), note.strip(), time.time()),
            )
            return int(cursor.lastrowid)

    def list_feedback(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, library, question, note, created_at FROM feedback "
                "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- 练习题 ---------------------------------------------------------------

    def insert_question(
        self,
        *,
        user_id: str,
        library: str,
        prompt: str,
        source: str,
        source_chunk_id: int | None,
        source_feedback_id: int | None,
    ) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO practice_questions (
                    user_id, library, prompt, source, source_chunk_id,
                    source_feedback_id, created_at, due_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    library,
                    prompt,
                    source,
                    source_chunk_id,
                    source_feedback_id,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def used_chunk_ids(self, user_id: str) -> set[int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT source_chunk_id FROM practice_questions "
                "WHERE user_id = ? AND source_chunk_id IS NOT NULL",
                (user_id,),
            ).fetchall()
        return {int(row["source_chunk_id"]) for row in rows}

    def unused_mistakes(
        self, user_id: str, library: str, *, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT f.id, f.library, f.question, f.note FROM feedback f
                WHERE f.user_id = ?
                  AND f.library != ''
                  AND (? = '' OR f.library = ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM practice_questions q
                      WHERE q.user_id = f.user_id AND q.source_feedback_id = f.id
                  )
                ORDER BY f.created_at DESC, f.id DESC LIMIT ?
                """,
                (user_id, library, library, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_question_library(self, user_id: str, question_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT library FROM practice_questions WHERE id = ? AND user_id = ?",
                (question_id, user_id),
            ).fetchone()
        return str(row["library"]) if row else None

    def update_question_review(
        self, question_id: int, *, due_at: float, rating: str
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE practice_questions SET due_at = ?, "
                "answered_count = answered_count + 1, last_rating = ? WHERE id = ?",
                (due_at, rating, question_id),
            )

    def record_attempt(
        self, question_id: int, rating: str, *, created_at: float
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO practice_attempts(question_id, rating, created_at) "
                "VALUES (?, ?, ?)",
                (question_id, rating, created_at),
            )

    def due_questions(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, library, prompt, source, due_at, answered_count, last_rating "
                "FROM practice_questions WHERE user_id = ? AND due_at <= ? "
                "ORDER BY due_at, id LIMIT ?",
                (user_id, time.time(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- 掌握度 ---------------------------------------------------------------

    def get_mastery(self, user_id: str, library: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT mastery FROM practice_progress WHERE user_id = ? AND library = ?",
                (user_id, library),
            ).fetchone()
        return int(row["mastery"]) if row else 0

    def set_mastery(
        self, user_id: str, library: str, mastery: int, *, updated_at: float
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO practice_progress(user_id, library, mastery, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(user_id, library) DO UPDATE SET "
                "mastery = excluded.mastery, updated_at = excluded.updated_at",
                (user_id, library, mastery, updated_at),
            )

    def list_progress(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT library, mastery, updated_at FROM practice_progress "
                "WHERE user_id = ? ORDER BY mastery",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- 记忆 -----------------------------------------------------------------

    def remember_fact(self, user_id: str, content: str, *, created_at: float) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO memories(user_id, content, created_at) "
                "VALUES (?, ?, ?)",
                (user_id, content, created_at),
            )

    def list_memories(self, user_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT content, created_at FROM memories WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [
            {"content": str(row["content"]), "created_at": float(row["created_at"])}
            for row in rows
        ]

    def count_recent_mistakes(self, user_id: str, *, since: float) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM feedback "
                "WHERE user_id = ? AND created_at >= ?",
                (user_id, since),
            ).fetchone()
        return int(row["count"]) if row else 0

    def activity_series(self, user_id: str, *, days: int) -> list[dict[str, Any]]:
        """按本地日期聚合近 N 天的学习活跃度（热力图数据）。

        - exercises：当天完成的练习作答次数（practice_attempts，按题目归属用户）。
        - mistakes：当天新增的误区条数（feedback）。

        返回恒为 ``days`` 个条目、从旧到新，没有数据的天补零——前端不用再对齐日期。
        """

        now = datetime.datetime.now()
        start = (now - datetime.timedelta(days=days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        since = start.timestamp()
        dates = [
            (start + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(days)
        ]
        counts: dict[str, dict[str, int]] = {
            day: {"exercises": 0, "mistakes": 0} for day in dates
        }

        with self._connect() as connection:
            attempt_rows = connection.execute(
                "SELECT a.created_at AS created_at FROM practice_attempts a "
                "JOIN practice_questions q ON q.id = a.question_id "
                "WHERE q.user_id = ? AND a.created_at >= ?",
                (user_id, since),
            ).fetchall()
            feedback_rows = connection.execute(
                "SELECT created_at FROM feedback "
                "WHERE user_id = ? AND created_at >= ?",
                (user_id, since),
            ).fetchall()

        for row in attempt_rows:
            key = datetime.datetime.fromtimestamp(row["created_at"]).strftime(
                "%Y-%m-%d"
            )
            if key in counts:
                counts[key]["exercises"] += 1
        for row in feedback_rows:
            key = datetime.datetime.fromtimestamp(row["created_at"]).strftime(
                "%Y-%m-%d"
            )
            if key in counts:
                counts[key]["mistakes"] += 1

        return [{"date": day, **counts[day]} for day in dates]
