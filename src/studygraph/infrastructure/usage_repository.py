"""token 用量记账的 SQLite 实现（`UsageRepositoryPort`）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_user_time ON llm_usage(user_id, created_at DESC);
"""


class SqliteUsageRepository:
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

    def record(
        self,
        *,
        user_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        created_at: float,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO llm_usage(user_id, model, input_tokens, output_tokens, "
                "total_tokens, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, model, input_tokens, output_tokens, total_tokens, created_at),
            )

    def total_since(self, *, user_id: str, since: float) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) AS total FROM llm_usage "
                "WHERE user_id = ? AND created_at >= ?",
                (user_id, since),
            ).fetchone()
        return int(row["total"]) if row else 0

    def summary(self, *, user_id: str, since: float) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT model, SUM(input_tokens) AS input_tokens, "
                "SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens, "
                "COUNT(*) AS calls FROM llm_usage WHERE user_id = ? AND created_at >= ? "
                "GROUP BY model ORDER BY total_tokens DESC",
                (user_id, since),
            ).fetchall()
        return [dict(row) for row in rows]
