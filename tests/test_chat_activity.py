"""提问频率热力图数据（/api/chat/activity）的回归测试。

统计口径锁死：只数 role='user' 的消息，经会话归属校验；
返回恒为 days 个条目、从旧到新、缺日补零。
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "activity.db"))
    return TestClient(create_app(settings))


def test_ask_activity_counts_user_messages_per_day(tmp_path) -> None:
    with _client(tmp_path) as client:
        chat = client.app.state.chat  # type: ignore[attr-defined]
        session_id = chat.create_session(
            user_id="local", project_id=1, thread_id="web-test"
        )
        chat.append_message(session_id, role="user", content="第一问")
        chat.append_message(session_id, role="assistant", content="第一答")
        chat.append_message(session_id, role="user", content="第二问")

        days = chat.ask_activity("local", days=7)
        assert len(days) == 7
        assert days[-1] == {"date": time.strftime("%Y-%m-%d"), "questions": 2}
        assert all(item["questions"] == 0 for item in days[:-1])


def test_ask_activity_excludes_other_users(tmp_path) -> None:
    with _client(tmp_path) as client:
        chat = client.app.state.chat  # type: ignore[attr-defined]
        mine = chat.create_session(user_id="local", project_id=1, thread_id="web-a")
        theirs = chat.create_session(user_id="alice", project_id=1, thread_id="web-b")
        chat.append_message(mine, role="user", content="我的提问")
        chat.append_message(theirs, role="user", content="别人的提问")

        total = sum(item["questions"] for item in chat.ask_activity("local", days=7))
        assert total == 1


def test_ask_activity_endpoint_shape(tmp_path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/chat/activity", params={"days": 14}).json()
        assert len(body["days"]) == 14
        assert set(body["days"][0]) == {"date", "questions"}
        # 越界由 Query 校验拦截
        assert client.get("/api/chat/activity", params={"days": 3}).status_code == 422
