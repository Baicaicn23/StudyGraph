"""应用级设置的 SQLite 仓储：当前模型选择、思考强度、自定义模型。

与业务数据分离的轻量 KV + 一张自定义模型表。单用户本地应用，自定义模型的
API Key 明文存本地库（`data/zhiji.db`，gitignore），不回显到任何列表接口。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS custom_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT NOT NULL,
    model_id TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class SqliteAppSettingsRepository:
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

    # -- KV -------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO app_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # -- 自定义模型 ------------------------------------------------------------

    def add_custom_model(
        self, *, name: str, base_url: str, api_key: str, model_id: str
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO custom_models(name, base_url, api_key, model_id, "
                "created_at) VALUES (?, ?, ?, ?, ?)",
                (name, base_url, api_key, model_id, time.time()),
            )
            return int(cursor.lastrowid)

    def list_custom_models(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, base_url, model_id, created_at FROM custom_models "
                "ORDER BY created_at DESC"
            ).fetchall()
        # api_key 刻意不返回——密钥只写不读，列表接口永不回显
        return [dict(row) for row in rows]

    def get_custom_model(self, model_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, base_url, api_key, model_id FROM custom_models "
                "WHERE id = ?",
                (model_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_custom_model(self, model_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM custom_models WHERE id = ?", (model_id,)
            )
            return cursor.rowcount > 0
