"""日程（时间轴 + 收件箱）的 SQLite 仓储——`ScheduleRepositoryPort` 的实现。

数据模型只有一张表：
- `date` 非空 = 已排进某天的时间轴（`start_minutes` 为当天分钟数 0–1439）；
- `date` 为空 = 留在**收件箱**（随手记下的想法，尚未安排时间）。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    date TEXT,
    start_minutes INTEGER,
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    done INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schedule_day
    ON schedule_tasks(user_id, date, start_minutes);
"""

_FIELDS = (
    "id, user_id, title, note, date, start_minutes, duration_minutes, "
    "done, created_at, updated_at"
)


def _row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["done"] = bool(item["done"])
    return item


class SqliteScheduleRepository:
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

    # -- 读 -------------------------------------------------------------------

    def get_task(self, user_id: str, task_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_FIELDS} FROM schedule_tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
        return _row(row) if row else None

    def list_day(self, user_id: str, date: str) -> list[dict[str, Any]]:
        """某天的任务，按开始时间升序（同一时刻按创建先后）。"""

        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {_FIELDS} FROM schedule_tasks "
                "WHERE user_id = ? AND date = ? "
                "ORDER BY start_minutes IS NULL, start_minutes, id",
                (user_id, date),
            ).fetchall()
        return [_row(row) for row in rows]

    def list_inbox(self, user_id: str) -> list[dict[str, Any]]:
        """收件箱：未排期的任务（新的在前）。"""

        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {_FIELDS} FROM schedule_tasks "
                "WHERE user_id = ? AND date IS NULL ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
        return [_row(row) for row in rows]

    def count_by_date(
        self, user_id: str, *, start: str, end: str
    ) -> list[dict[str, Any]]:
        """区间内每天的排期数量与完成数（周条密度点用）。"""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT date, COUNT(*) AS total, "
                "SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS done_count "
                "FROM schedule_tasks "
                "WHERE user_id = ? AND date IS NOT NULL AND date >= ? AND date <= ? "
                "GROUP BY date",
                (user_id, start, end),
            ).fetchall()
        return [
            {
                "date": row["date"],
                "total": int(row["total"]),
                "done": int(row["done_count"] or 0),
            }
            for row in rows
        ]

    # -- 写 -------------------------------------------------------------------

    def create_task(
        self,
        *,
        user_id: str,
        title: str,
        note: str = "",
        date: str | None = None,
        start_minutes: int | None = None,
        duration_minutes: int = 30,
    ) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO schedule_tasks(user_id, title, note, date, "
                "start_minutes, duration_minutes, done, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (
                    user_id,
                    title,
                    note,
                    date,
                    start_minutes,
                    duration_minutes,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_task(
        self,
        user_id: str,
        task_id: int,
        *,
        title: str | None = None,
        note: str | None = None,
        date: str | None = None,
        clear_date: bool = False,
        start_minutes: int | None = None,
        duration_minutes: int | None = None,
        done: bool | None = None,
    ) -> bool:
        sets: list[str] = []
        params: list[Any] = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if note is not None:
            sets.append("note = ?")
            params.append(note)
        if clear_date:
            sets.append("date = NULL")
            sets.append("start_minutes = NULL")
        elif date is not None:
            sets.append("date = ?")
            params.append(date)
        if start_minutes is not None:
            sets.append("start_minutes = ?")
            params.append(start_minutes)
        if duration_minutes is not None:
            sets.append("duration_minutes = ?")
            params.append(duration_minutes)
        if done is not None:
            sets.append("done = ?")
            params.append(1 if done else 0)
        if not sets:
            return False
        sets.append("updated_at = ?")
        params.append(time.time())
        params.extend([task_id, user_id])
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE schedule_tasks SET {', '.join(sets)} "
                "WHERE id = ? AND user_id = ?",
                params,
            )
            return cursor.rowcount > 0

    def delete_task(self, user_id: str, task_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM schedule_tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            )
            return cursor.rowcount > 0
