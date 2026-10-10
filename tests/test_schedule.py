"""日程（时间轴 + 收件箱）的回归测试。

锁死的规则：
- date 为空 = 收件箱；给了 date 不给时间 = 自动落进最早空档；
- 一键安排 = 当日最早放得下的空档，今天从当前时刻之后算（确定性，可复现）；
- 任务按开始时间升序；周条按周日开头的 7 天返回计数；
- 归属校验：别人的任务读不到也改不了。
"""

from __future__ import annotations

import datetime

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "schedule.db"))
    return TestClient(create_app(settings))


def _tomorrow() -> str:
    return (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def test_create_inbox_task_then_arrange(tmp_path) -> None:
    with _client(tmp_path) as client:
        # 进收件箱（不给日期）
        created = client.post(
            "/api/schedule/tasks",
            json={"title": "复习线性代数特征值", "note": "教材 P120", "duration_minutes": 45},
        ).json()["task"]
        assert created["date"] is None
        assert created["start_minutes"] is None

        inbox = client.get("/api/schedule/inbox").json()["tasks"]
        assert [item["id"] for item in inbox] == [created["id"]]

        # 一键安排到明天 → 落到 06:00（最早空档，明天没有 respect_now）
        arranged = client.post(
            f"/api/schedule/tasks/{created['id']}/arrange",
            params={"date": _tomorrow()},
        ).json()["task"]
        assert arranged["date"] == _tomorrow()
        assert arranged["start_minutes"] == 6 * 60
        assert arranged["duration_minutes"] == 45

        # 收件箱清空，时间轴上出现
        assert client.get("/api/schedule/inbox").json()["tasks"] == []
        day = client.get("/api/schedule", params={"date": _tomorrow()}).json()
        assert [item["id"] for item in day["tasks"]] == [created["id"]]


def test_arrange_fills_first_free_slot(tmp_path) -> None:
    with _client(tmp_path) as client:
        target = _tomorrow()
        first = client.post(
            "/api/schedule/tasks",
            json={"title": "背单词", "date": target, "start_minutes": 360, "duration_minutes": 30},
        ).json()["task"]
        assert first["start_minutes"] == 360

        # 第二件事不给时间 → 接在第一个任务之后（06:30）
        second = client.post(
            "/api/schedule/tasks",
            json={"title": "写作业", "date": target, "duration_minutes": 45},
        ).json()["task"]
        assert second["start_minutes"] == 390

        # 往 06:00 与 06:30 之间塞一个 20 分钟的任务：没有空档 → 排到 07:15
        third = client.post(
            "/api/schedule/tasks",
            json={"title": "复习错题", "date": target, "duration_minutes": 20},
        ).json()["task"]
        assert third["start_minutes"] == 390 + 45

        day = client.get("/api/schedule", params={"date": target}).json()
        assert [item["start_minutes"] for item in day["tasks"]] == [360, 390, 435]


def test_day_list_is_ordered_and_counts_inbox(tmp_path) -> None:
    with _client(tmp_path) as client:
        target = _tomorrow()
        client.post(
            "/api/schedule/tasks",
            json={"title": "晚任务", "date": target, "start_minutes": 1200},
        )
        client.post(
            "/api/schedule/tasks",
            json={"title": "早任务", "date": target, "start_minutes": 400},
        )
        client.post("/api/schedule/tasks", json={"title": "收件箱里的"})

        day = client.get("/api/schedule", params={"date": target}).json()
        assert [item["title"] for item in day["tasks"]] == ["早任务", "晚任务"]
        assert day["inbox_count"] == 1


def test_toggle_done_and_unarrange(tmp_path) -> None:
    with _client(tmp_path) as client:
        target = _tomorrow()
        task = client.post(
            "/api/schedule/tasks",
            json={"title": "实验报告", "date": target, "start_minutes": 600},
        ).json()["task"]

        done = client.put(
            f"/api/schedule/tasks/{task['id']}", json={"done": True}
        ).json()["task"]
        assert done["done"] is True

        # 退回收件箱：日期与开始时间清空，时长保留
        back = client.post(f"/api/schedule/tasks/{task['id']}/unarrange").json()["task"]
        assert back["date"] is None and back["start_minutes"] is None
        assert back["duration_minutes"] == 30


def test_week_returns_seven_days_sunday_first(tmp_path) -> None:
    with _client(tmp_path) as client:
        today = datetime.date.today()
        # 本周内的某天放两个任务（其中一天完成）
        monday = today - datetime.timedelta(days=(today.weekday()) % 7)
        target = monday.strftime("%Y-%m-%d")
        first = client.post(
            "/api/schedule/tasks",
            json={"title": "A", "date": target, "start_minutes": 500},
        ).json()["task"]
        client.post(
            "/api/schedule/tasks", json={"title": "B", "date": target, "start_minutes": 600}
        )
        client.put(f"/api/schedule/tasks/{first['id']}", json={"done": True})

        week = client.get(
            "/api/schedule/week", params={"date": today.strftime("%Y-%m-%d")}
        ).json()
        assert len(week["days"]) == 7
        # 周日开头：第一天是周日
        assert datetime.datetime.strptime(
            week["days"][0]["date"], "%Y-%m-%d"
        ).weekday() == 6
        entry = next(item for item in week["days"] if item["date"] == target)
        assert entry["total"] == 2 and entry["done"] == 1


def test_ownership_and_validation(tmp_path) -> None:
    with _client(tmp_path) as client:
        created = client.post(
            "/api/schedule/tasks", json={"title": "我的任务"}
        ).json()["task"]
        # 别人的 user_id 读不到、改不了
        assert (
            client.put(
                f"/api/schedule/tasks/{created['id']}",
                json={"user_id": "alice", "title": "越权"},
            ).status_code
            == 400
        )
        assert (
            client.delete(
                f"/api/schedule/tasks/{created['id']}", params={"user_id": "alice"}
            ).status_code
            == 404
        )
        # 非法日期 / 空标题 / 越界时长
        assert (
            client.post(
                "/api/schedule/tasks", json={"title": "x", "date": "2026-13-99"}
            ).status_code
            == 400
        )
        assert client.post("/api/schedule/tasks", json={"title": ""}).status_code == 422
        assert (
            client.post(
                "/api/schedule/tasks", json={"title": "x", "duration_minutes": 1}
            ).status_code
            == 422
        )
