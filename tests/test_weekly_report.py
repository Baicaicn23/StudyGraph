"""学习周报（weekly_report）的回归测试：确定性聚合，零模型调用。

锁死的规则：
- 提问按"会话归属用户"统计（chat_messages ⋈ chat_sessions），按天给 7 根柱；
- 作答数 + 自评良好率（good/easy）；误区 = feedback 新增；
- 掌握度 delta = 现值 − 上周快照；本周快照首次请求时自动落一份；
- 日程完成度只数已排期（date 非空）的任务。
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from zhiji.infrastructure.learning_repository import SqliteLearningRepository
from zhiji.infrastructure.schedule_repository import SqliteScheduleRepository


def _seed(db: Path) -> str:
    """灌入两周的确定性数据，返回上周周一的日期串。"""

    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    last_monday = monday - timedelta(days=7)
    three_days_ago = monday + timedelta(days=3, hours=10)
    week_since, last_since = monday.timestamp(), last_monday.timestamp()

    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            project_id INTEGER,
            thread_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '新对话',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments TEXT NOT NULL DEFAULT '',
            steps TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO chat_sessions (user_id, created_at, updated_at) VALUES (?, ?, ?)",
        ("u1", time.time(), time.time()),
    )
    messages = [
        ("user", now.timestamp()),                # 本周
        ("user", now.timestamp() - 60),           # 本周
        ("user", three_days_ago.timestamp()),     # 本周
        ("assistant", now.timestamp()),           # 非提问，不计
        ("user", last_since + 3600),              # 上周
        ("user", last_since + 7200),              # 上周
        ("user", week_since - 10),                # 上周最后一刻
    ]
    for role, created in messages:
        connection.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) "
            "VALUES (1, ?, 'x', ?)",
            (role, created),
        )

    connection.executescript(
        """
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
        CREATE TABLE IF NOT EXISTS practice_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            rating TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            library TEXT NOT NULL DEFAULT '',
            question TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS practice_progress (
            user_id TEXT NOT NULL,
            library TEXT NOT NULL,
            mastery INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL,
            PRIMARY KEY (user_id, library)
        );
        """
    )
    connection.execute(
        "INSERT INTO practice_questions (user_id, library, prompt, source, "
        "created_at, due_at) VALUES ('u1', '高等数学', '题', 'template', ?, ?)",
        (time.time(), time.time()),
    )
    for rating, created in [
        ("good", now.timestamp()),
        ("easy", now.timestamp() - 120),
        ("hard", three_days_ago.timestamp()),
        ("again", three_days_ago.timestamp()),
        ("good", last_since + 3600),
        ("good", last_since + 7200),
    ]:
        connection.execute(
            "INSERT INTO practice_attempts (question_id, rating, created_at) "
            "VALUES (1, ?, ?)",
            (rating, created),
        )
    for created in [now.timestamp(), three_days_ago.timestamp()]:
        connection.execute(
            "INSERT INTO feedback (user_id, question, created_at) "
            "VALUES ('u1', '误区', ?)",
            (created,),
        )
    connection.execute(
        "INSERT INTO feedback (user_id, question, created_at) VALUES ('u1', '旧误区', ?)",
        (last_since + 3600,),
    )
    connection.execute(
        "INSERT INTO practice_progress (user_id, library, mastery, updated_at) "
        "VALUES ('u1', '高等数学', 82, ?)",
        (time.time(),),
    )
    connection.commit()
    connection.close()
    return last_monday.strftime("%Y-%m-%d")


def test_weekly_report_counts_and_snapshot(tmp_path: Path) -> None:
    db = tmp_path / "week.db"
    last_week_str = _seed(db)
    repo = SqliteLearningRepository(db)

    report = repo.weekly_report("u1")

    assert report["questions"]["total"] == 3
    assert report["questions"]["last_week"] == 3
    assert sum(report["questions"]["daily"]) == 3

    assert report["attempts"]["total"] == 4
    assert report["attempts"]["good_rate"] == 0.5
    assert report["attempts"]["last_week"] == 2

    assert report["mistakes"] == {"total": 2, "last_week": 1}

    # 首次请求：本周快照落库（值=现值 82），delta 因无上周快照为 None
    assert report["mastery"] == [
        {"library": "高等数学", "mastery": 82, "delta": None}
    ]

    # 上周快照补上后，delta = 现值 − 上周快照
    connection = sqlite3.connect(db)
    connection.execute(
        "INSERT INTO mastery_snapshots (user_id, library, week_start, mastery) "
        "VALUES ('u1', '高等数学', ?, 80)",
        (last_week_str,),
    )
    connection.commit()
    connection.close()
    report = repo.weekly_report("u1")
    assert report["mastery"] == [{"library": "高等数学", "mastery": 82, "delta": 2}]


def test_schedule_week_stats_counts_only_scheduled(tmp_path: Path) -> None:
    db = tmp_path / "week.db"
    repo = SqliteScheduleRepository(db)
    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start, end = monday.strftime("%Y-%m-%d"), (
        monday + timedelta(days=6)
    ).strftime("%Y-%m-%d")

    for date, done in [(start, 1), (end, 0), (None, 0)]:
        connection = sqlite3.connect(db)
        connection.execute(
            "INSERT INTO schedule_tasks (user_id, title, date, start_minutes, "
            "duration_minutes, done, created_at, updated_at) "
            "VALUES ('u1', '任务', ?, 600, 30, ?, ?, ?)",
            (date, done, time.time(), time.time()),
        )
        connection.commit()
        connection.close()

    assert repo.week_stats("u1", start_date=start, end_date=end) == {
        "total": 2,
        "done": 1,
    }
