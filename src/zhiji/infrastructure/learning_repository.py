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
    kind TEXT NOT NULL DEFAULT '',
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
    last_rating TEXT,
    difficulty TEXT NOT NULL DEFAULT 'basic'
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
    project_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE (user_id, project_id, content)
);
"""


class SqliteLearningRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(_SCHEMA)
            self._migrate(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        """旧库平滑迁移：缺哪列补哪列（CREATE TABLE IF NOT EXISTS 不会改老表）。"""

        existing = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(practice_questions)"
            ).fetchall()
        }
        if "difficulty" not in existing:
            connection.execute(
                "ALTER TABLE practice_questions "
                "ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'basic'"
            )

        memory_cols = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(memories)").fetchall()
        }
        if "project_id" not in memory_cols:
            # 记忆按项目隔离：老数据全部归入默认空间（''），不丢内容。
            connection.execute(
                "ALTER TABLE memories ADD COLUMN project_id TEXT NOT NULL DEFAULT ''"
            )
            # 旧表只有 (user_id, content) 唯一约束；新数据由新 UNIQUE 索引管。
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_project "
                "ON memories(user_id, project_id, content)"
            )

        feedback_cols = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(feedback)").fetchall()
        }
        if "kind" not in feedback_cols:
            # 误区错误类型（概念混淆 / 步骤遗漏 / …）：老数据留空，前端显示"未分类"。
            connection.execute(
                "ALTER TABLE feedback ADD COLUMN kind TEXT NOT NULL DEFAULT ''"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    # -- 错题 -----------------------------------------------------------------

    def add_feedback(
        self, *, user_id: str, library: str, question: str, note: str, kind: str = ""
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO feedback(user_id, library, question, note, kind, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    library.strip(),
                    question.strip(),
                    note.strip(),
                    kind.strip(),
                    time.time(),
                ),
            )
            return int(cursor.lastrowid)

    def list_feedback(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, library, question, note, kind, created_at FROM feedback "
                "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_feedback(self, user_id: str, feedback_id: int) -> bool:
        """删除一条误区（校验归属，防止越权删别人的）。"""

        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM feedback WHERE id = ? AND user_id = ?",
                (feedback_id, user_id),
            )
            return cursor.rowcount > 0

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
        difficulty: str = "basic",
    ) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO practice_questions (
                    user_id, library, prompt, source, source_chunk_id,
                    source_feedback_id, created_at, due_at, difficulty
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    difficulty,
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

    def mistakes_by_ids(
        self, user_id: str, ids: list[int]
    ) -> list[dict[str, Any]]:
        """按 id 取误区（校验归属，按传入顺序返回）。"""

        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT id, library, question, note, kind FROM feedback "
                f"WHERE user_id = ? AND id IN ({placeholders})",
                (user_id, *ids),
            ).fetchall()
        by_id = {int(row["id"]): dict(row) for row in rows}
        return [by_id[item] for item in ids if item in by_id]

    def used_feedback_ids(self, user_id: str) -> set[int]:
        """已经出过题的误区 id（同一误区不重复出题）。"""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT source_feedback_id FROM practice_questions "
                "WHERE user_id = ? AND source_feedback_id IS NOT NULL",
                (user_id,),
            ).fetchall()
        return {int(row["source_feedback_id"]) for row in rows}

    def get_question_library(self, user_id: str, question_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT library FROM practice_questions WHERE id = ? AND user_id = ?",
                (question_id, user_id),
            ).fetchone()
        return str(row["library"]) if row else None

    def delete_question(self, user_id: str, question_id: int) -> bool:
        """删除一道练习题及其作答记录（校验归属）。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM practice_questions WHERE id = ? AND user_id = ?",
                (question_id, user_id),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "DELETE FROM practice_attempts WHERE question_id = ?", (question_id,)
            )
            connection.execute(
                "DELETE FROM practice_questions WHERE id = ?", (question_id,)
            )
            return True

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
                "SELECT id, library, prompt, source, due_at, answered_count, "
                "last_rating, difficulty "
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

    def delete_memory(self, user_id: str, memory_id: int) -> bool:
        """删除一条长期记忆（校验归属）。"""

        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE id = ? AND user_id = ?",
                (memory_id, user_id),
            )
            return cursor.rowcount > 0

    def remember_fact(
        self, user_id: str, content: str, *, created_at: float, project_id: str = ""
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO memories(user_id, content, project_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, content, project_id, created_at),
            )

    def list_memories(
        self, user_id: str, *, project_id: str = "", limit: int = 10
    ) -> list[dict[str, Any]]:
        """取某用户（可再按项目过滤）的记忆，最新在前。

        不带 project_id 的"全部"视图会**按内容去重**：记忆唯一约束是
        `(user_id, project_id, content)`，同一条事实在不同课程空间下会各存一份，
        合并展示时必须去重，否则前端 key 撞车（React 报 Non-unique keys）。
        """

        with self._connect() as connection:
            if project_id:
                rows = connection.execute(
                    "SELECT id, content, created_at FROM memories WHERE user_id = ? "
                    "AND project_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                    (user_id, project_id, limit),
                ).fetchall()
            else:
                # 多取一些，去重后仍能凑满 limit
                rows = connection.execute(
                    "SELECT id, content, created_at FROM memories WHERE user_id = ? "
                    "ORDER BY created_at DESC, id DESC LIMIT ?",
                    (user_id, limit * 3),
                ).fetchall()

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            content = str(row["content"])
            if content in seen:
                continue
            seen.add(content)
            items.append(
                {
                    "id": int(row["id"]),
                    "content": content,
                    "created_at": float(row["created_at"]),
                }
            )
            if len(items) >= limit:
                break
        return items

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
