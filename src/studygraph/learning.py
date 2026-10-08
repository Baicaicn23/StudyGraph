"""学习闭环：错题 / 出题 / 间隔重复 / 掌握度 / 长期记忆 / 今日复习。

数据都落 SQLite（与会话检查点、知识库共用同一个库文件）。核心设计：

- **错题（feedback）** 带学科标签；出题时按学科挂题。
- **练习题** 有 `due_at`：新题立即到期，答完按自评推迟。这就是**间隔重复**。
- **掌握度** 按学科维护（0~100），随答题自评增减。
- **一条误区只出一道题**：`(user_id, source_feedback_id)` 上建**部分唯一索引**。
- **长期记忆** 从对话里抽取事实，注入提示词时标注"数据而非指令"。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from .generator import (
    build_excerpt_instruction,
    build_mistake_instruction,
    template_excerpt_question,
    template_mistake_question,
    write_question,
)
from .memory import extract_facts

# 自评 -> (掌握度增减, 下次复习间隔秒数)。Again 立刻再来，Easy 拉长到一周。
_RATING: dict[str, tuple[int, int]] = {
    "again": (-10, 0),
    "hard": (-3, 24 * 60 * 60),
    "good": (5, 3 * 24 * 60 * 60),
    "easy": (10, 7 * 24 * 60 * 60),
}

_SOURCES = ("knowledge_base", "mistakes")

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


class LearningError(ValueError):
    pass


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


class LearningService:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
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

    # -- 出题 -----------------------------------------------------------------

    async def generate(
        self,
        *,
        user_id: str,
        source: str = "knowledge_base",
        library: str = "",
        count: int = 3,
        model: Any | None = None,
    ) -> list[dict[str, Any]]:
        if count < 1 or count > 10:
            raise LearningError("每次可生成 1 到 10 道练习题")
        if source not in _SOURCES:
            raise LearningError(f"不支持的出题来源：{source}")
        if source == "mistakes":
            return await self._generate_from_mistakes(
                user_id=user_id, library=library, count=count, model=model
            )
        return await self._generate_from_library(
            user_id=user_id, library=library, count=count, model=model
        )

    async def _generate_from_library(
        self, *, user_id: str, library: str, count: int, model: Any | None
    ) -> list[dict[str, Any]]:
        if not library.strip():
            raise LearningError("请先选择知识库")
        rows = self._unused_chunks(user_id, library, count)
        if not rows:
            raise LearningError("这个知识库里暂时没有可用于出题的新片段")
        created: list[dict[str, Any]] = []
        for row in rows:
            excerpt = str(row["content"])
            written = await write_question(
                model,
                build_excerpt_instruction(excerpt),
                fallback=template_excerpt_question(excerpt),
            )
            created.append(
                self._insert_question(
                    user_id=user_id,
                    library=library,
                    prompt=written.prompt,
                    source="knowledge_base",
                    source_chunk_id=int(row["id"]),
                    source_feedback_id=None,
                    generator=written.generator,
                )
            )
        return created

    async def _generate_from_mistakes(
        self, *, user_id: str, library: str, count: int, model: Any | None
    ) -> list[dict[str, Any]]:
        rows = self._unused_mistakes(user_id, library, count)
        if not rows:
            raise LearningError("还没有可用于出题的新错题：先记录一条误区")
        created: list[dict[str, Any]] = []
        for row in rows:
            question = str(row["question"])
            note = str(row["note"])
            written = await write_question(
                model,
                build_mistake_instruction(
                    subject=str(row["library"]), question=question, note=note
                ),
                fallback=template_mistake_question(question=question, note=note),
            )
            created.append(
                self._insert_question(
                    user_id=user_id,
                    library=str(row["library"]),
                    prompt=written.prompt,
                    source="mistake",
                    source_chunk_id=None,
                    source_feedback_id=int(row["id"]),
                    generator=written.generator,
                )
            )
        return created

    def _unused_chunks(self, user_id: str, library: str, limit: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT c.id, c.content FROM chunks c
                WHERE c.library = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM practice_questions q
                      WHERE q.user_id = ? AND q.source_chunk_id = c.id
                  )
                ORDER BY c.id LIMIT ?
                """,
                (library, user_id, limit),
            ).fetchall()

    def _unused_mistakes(
        self, user_id: str, library: str, limit: int
    ) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
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

    def _insert_question(
        self,
        *,
        user_id: str,
        library: str,
        prompt: str,
        source: str,
        source_chunk_id: int | None,
        source_feedback_id: int | None,
        generator: str,
    ) -> dict[str, Any]:
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
            question_id = int(cursor.lastrowid)
        return {
            "id": question_id,
            "library": library,
            "prompt": prompt,
            "source": source,
            "generator": generator,
            "due_at": now,
        }

    # -- 练习与间隔重复 -------------------------------------------------------

    def due_questions(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, library, prompt, source, due_at, answered_count, last_rating "
                "FROM practice_questions WHERE user_id = ? AND due_at <= ? "
                "ORDER BY due_at, id LIMIT ?",
                (user_id, time.time(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def answer(
        self, *, user_id: str, question_id: int, rating: str
    ) -> dict[str, Any]:
        if rating not in _RATING:
            raise LearningError("评分必须是 again / hard / good / easy 之一")
        delta, interval = _RATING[rating]
        now = time.time()
        due_at = now + interval if interval > 0 else now
        with self._connect() as connection:
            row = connection.execute(
                "SELECT library FROM practice_questions WHERE id = ? AND user_id = ?",
                (question_id, user_id),
            ).fetchone()
            if row is None:
                raise LearningError("找不到这道题")
            library = str(row["library"])
            connection.execute(
                "UPDATE practice_questions SET due_at = ?, answered_count = answered_count + 1, "
                "last_rating = ? WHERE id = ?",
                (due_at, rating, question_id),
            )
            connection.execute(
                "INSERT INTO practice_attempts(question_id, rating, created_at) VALUES (?, ?, ?)",
                (question_id, rating, now),
            )
            current = connection.execute(
                "SELECT mastery FROM practice_progress WHERE user_id = ? AND library = ?",
                (user_id, library),
            ).fetchone()
            mastery = _clamp((int(current["mastery"]) if current else 0) + delta)
            connection.execute(
                "INSERT INTO practice_progress(user_id, library, mastery, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(user_id, library) DO UPDATE SET "
                "mastery = excluded.mastery, updated_at = excluded.updated_at",
                (user_id, library, mastery, now),
            )
        return {
            "question_id": question_id,
            "library": library,
            "rating": rating,
            "mastery": mastery,
            "due_at": due_at,
            "due_in_days": round(interval / 86400, 2),
        }

    def progress(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT library, mastery, updated_at FROM practice_progress "
                "WHERE user_id = ? ORDER BY mastery",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- 长期记忆 -------------------------------------------------------------

    def remember(self, user_id: str, text: str) -> list[str]:
        facts = extract_facts(text)
        if not facts:
            return []
        now = time.time()
        with self._connect() as connection:
            for fact in facts:
                connection.execute(
                    "INSERT OR IGNORE INTO memories(user_id, content, created_at) "
                    "VALUES (?, ?, ?)",
                    (user_id, fact, now),
                )
        return facts

    def memories(self, user_id: str, *, limit: int = 10) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT content FROM memories WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [str(row["content"]) for row in rows]

    # -- 今日复习（规划）------------------------------------------------------

    def plan(self, user_id: str) -> dict[str, Any]:
        now = time.time()
        due = self.due_questions(user_id, limit=20)
        weak = [item for item in self.progress(user_id) if int(item["mastery"]) < 60]
        with self._connect() as connection:
            recent = connection.execute(
                "SELECT COUNT(*) AS count FROM feedback WHERE user_id = ? AND created_at >= ?",
                (user_id, now - 7 * 86400),
            ).fetchone()
        recent_mistakes = int(recent["count"]) if recent else 0

        suggestions: list[str] = []
        if due:
            suggestions.append(f"先做 {len(due)} 道到期练习题")
        for item in weak:
            suggestions.append(
                f"复习「{item['library']}」（掌握度 {item['mastery']}%）"
            )
        if recent_mistakes:
            suggestions.append(f"回看最近记录的 {recent_mistakes} 条误区")
        if not suggestions:
            suggestions.append("暂时没有到期任务，可以上传新资料或记录一条误区")

        return {
            "due_questions": due,
            "weak_libraries": weak,
            "recent_mistakes": recent_mistakes,
            "suggestions": suggestions,
        }
