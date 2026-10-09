"""聊天会话持久化——项目分组 + 自动保存的消息记录。

WorkBuddy 式会话模型：
- `projects`：项目（空间），会话按项目分组，项目删除后会话回到未分组；
- `chat_sessions`：一次对话（自动保存、自动起标题）；
- `chat_messages`：对话的逐条消息（便于列表回放，检查点里的历史只服务图状态）。

与 `SqliteLearningRepository` 共用同一个 SQLite 文件，但职责独立。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    UNIQUE (user_id, name)
);
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    project_id INTEGER,
    thread_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '新对话',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON chat_sessions(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session
    ON chat_messages(session_id, id);
CREATE TABLE IF NOT EXISTS chat_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id INTEGER,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'file',
    content TEXT NOT NULL DEFAULT '',
    storage_path TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_user
    ON chat_attachments(user_id, id);
"""


class SqliteChatRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(_SCHEMA)
            self._migrate(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        """旧库平滑迁移：CREATE TABLE IF NOT EXISTS 不会改老表，缺哪列补哪列。"""

        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chat_sessions)").fetchall()
        }
        if "thread_id" not in existing:
            connection.execute(
                "ALTER TABLE chat_sessions ADD COLUMN thread_id TEXT NOT NULL DEFAULT ''"
            )

        project_cols = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "is_default" not in project_cols:
            connection.execute(
                "ALTER TABLE projects ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0"
            )

        message_cols = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chat_messages)").fetchall()
        }
        if "attachments" not in message_cols:
            connection.execute(
                "ALTER TABLE chat_messages ADD COLUMN attachments TEXT NOT NULL DEFAULT ''"
            )

        attachment_cols = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(chat_attachments)"
            ).fetchall()
        }
        if "storage_path" not in attachment_cols:
            connection.execute(
                "ALTER TABLE chat_attachments "
                "ADD COLUMN storage_path TEXT NOT NULL DEFAULT ''"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    # -- 项目 -----------------------------------------------------------------

    def create_project(self, *, user_id: str, name: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO projects (user_id, name, created_at) VALUES (?, ?, ?)",
                (user_id, name.strip(), time.time()),
            )
            return int(cursor.lastrowid)

    DEFAULT_SPACE_NAME = "默认对话空间"

    def ensure_default_project(self, user_id: str) -> int:
        """保证用户有且只有一个「默认对话空间」，并把无主会话归入其中。

        - 已有 is_default=1 的项目 → 直接返回；
        - 没有但建过同名项目 → 收编为默认空间；
        - 都没有 → 新建。最后把 project_id 为空的会话全部归入。
        """

        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM projects WHERE user_id = ? AND is_default = 1",
                (user_id,),
            ).fetchone()
            if row is None:
                existing = connection.execute(
                    "SELECT id FROM projects WHERE user_id = ? AND name = ?",
                    (user_id, self.DEFAULT_SPACE_NAME),
                ).fetchone()
                if existing is not None:
                    connection.execute(
                        "UPDATE projects SET is_default = 1 WHERE id = ?",
                        (existing["id"],),
                    )
                    default_id = int(existing["id"])
                else:
                    cursor = connection.execute(
                        "INSERT INTO projects (user_id, name, is_default, created_at) "
                        "VALUES (?, ?, 1, ?)",
                        (user_id, self.DEFAULT_SPACE_NAME, time.time()),
                    )
                    default_id = int(cursor.lastrowid)
            else:
                default_id = int(row["id"])
            connection.execute(
                "UPDATE chat_sessions SET project_id = ? "
                "WHERE user_id = ? AND project_id IS NULL",
                (default_id, user_id),
            )
        return default_id

    def get_project(self, user_id: str, project_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, user_id, name, is_default, created_at "
                "FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, is_default, created_at FROM projects "
                "WHERE user_id = ? ORDER BY is_default DESC, created_at, id",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def rename_project(self, user_id: str, project_id: int, name: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET name = ? WHERE id = ? AND user_id = ?",
                (name.strip(), project_id, user_id),
            )
            return cursor.rowcount > 0

    def delete_project(self, user_id: str, project_id: int) -> bool:
        """删除项目：会话归入默认空间（绝不丢聊天记录）；默认空间本身不可删。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT is_default FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
            if row is None or row["is_default"]:
                return False
            default_row = connection.execute(
                "SELECT id FROM projects WHERE user_id = ? AND is_default = 1",
                (user_id,),
            ).fetchone()
            default_id = int(default_row["id"]) if default_row else None
            cursor = connection.execute(
                "DELETE FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            )
            if cursor.rowcount:
                # 会话挪进默认空间；万一默认空间缺失（理论不可能）才退回未分组
                connection.execute(
                    "UPDATE chat_sessions SET project_id = ? "
                    "WHERE project_id = ? AND user_id = ?",
                    (default_id, project_id, user_id),
                )
            return cursor.rowcount > 0

    # -- 会话 -----------------------------------------------------------------

    def create_session(
        self,
        *,
        user_id: str,
        project_id: int | None = None,
        thread_id: str = "",
        title: str = "新对话",
    ) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO chat_sessions (user_id, project_id, thread_id, title, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, project_id, thread_id, title, now, now),
            )
            return int(cursor.lastrowid)

    def get_session(self, user_id: str, session_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, user_id, project_id, thread_id, title, created_at, "
                "updated_at FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(
        self, user_id: str, *, project_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT id, project_id, thread_id, title, created_at, updated_at "
            "FROM chat_sessions WHERE user_id = ?"
        )
        params: list[Any] = [user_id]
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_session(
        self,
        user_id: str,
        session_id: int,
        *,
        title: str | None = None,
        project_id: int | None = None,
        touch: bool = False,
    ) -> bool:
        sets: list[str] = []
        params: list[Any] = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if project_id is not None:
            sets.append("project_id = ?")
            params.append(project_id)
        if touch:
            sets.append("updated_at = ?")
            params.append(time.time())
        if not sets:
            return False
        params.extend([session_id, user_id])
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE chat_sessions SET {', '.join(sets)} "
                "WHERE id = ? AND user_id = ?",
                params,
            )
            return cursor.rowcount > 0

    def delete_session(self, user_id: str, session_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
            if cursor.rowcount:
                connection.execute(
                    "DELETE FROM chat_messages WHERE session_id = ?",
                    (session_id,),
                )
                connection.execute(
                    "DELETE FROM chat_attachments WHERE session_id = ?",
                    (session_id,),
                )
            return cursor.rowcount > 0

    # -- 消息 -----------------------------------------------------------------

    def append_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        attachments: str = "",
    ) -> int:
        """落一条消息；attachments 是附件文件名的 JSON 数组字符串。"""

        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO chat_messages (session_id, role, content, attachments, "
                "created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, attachments, time.time()),
            )
            return int(cursor.lastrowid)

    def list_messages(
        self, user_id: str, session_id: int, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        """回放某个会话的消息（校验会话归属，防止越权读取）。"""

        with self._connect() as connection:
            owner = connection.execute(
                "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if owner is None:
                return []
            rows = connection.execute(
                "SELECT id, role, content, attachments, created_at "
                "FROM chat_messages WHERE session_id = ? ORDER BY id LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- 聊天附件 ---------------------------------------------------------------

    def add_attachment(
        self,
        *,
        user_id: str,
        session_id: int | None,
        filename: str,
        kind: str,
        content: str,
        storage_path: str = "",
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO chat_attachments (user_id, session_id, filename, kind, "
                "content, storage_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    session_id,
                    filename,
                    kind,
                    content,
                    storage_path,
                    time.time(),
                ),
            )
            return int(cursor.lastrowid)

    def get_attachment(self, user_id: str, attachment_id: int) -> dict[str, Any] | None:
        """取单个附件（含落盘路径），校验归属。"""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, filename, kind, storage_path FROM chat_attachments "
                "WHERE id = ? AND user_id = ?",
                (attachment_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def set_attachment_path(
        self, user_id: str, attachment_id: int, storage_path: str
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE chat_attachments SET storage_path = ? "
                "WHERE id = ? AND user_id = ?",
                (storage_path, attachment_id, user_id),
            )
            return cursor.rowcount > 0

    def get_attachments(
        self, user_id: str, attachment_ids: list[int]
    ) -> list[dict[str, Any]]:
        """按 id 批量取附件（校验归属，别人传你的附件 id 直接查不到）。"""

        if not attachment_ids:
            return []
        placeholders = ",".join("?" for _ in attachment_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT id, filename, kind, content FROM chat_attachments "
                f"WHERE user_id = ? AND id IN ({placeholders})",
                (user_id, *attachment_ids),
            ).fetchall()
        # 按调用方给的顺序返回
        order = {attachment_id: index for index, attachment_id in enumerate(attachment_ids)}
        return sorted((dict(row) for row in rows), key=lambda row: order[row["id"]])
