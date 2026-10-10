"""考前冲刺计划的回归测试：确定性排期，零模型调用。

排期规则（锁死防回归）：
- 最薄弱的库排最前（掌握度升序；相同则到期题多的优先）
- 每个库第一次被排到时先清它的到期题，之后是巩固出题
- 没有任何学习数据时返回空排期 + 引导提示
- 周期越界（<1 或 >30）返回 400
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "sprint.db"))
    return TestClient(create_app(settings))


def _seed_library_and_question(client: TestClient, library: str, content: str) -> int:
    client.post(
        "/api/knowledge/notes",
        json={"library": library, "title": f"{library}笔记", "content": content},
    )
    created = client.post(
        "/api/practice/generate",
        json={"source": "knowledge_base", "library": library, "count": 1},
    ).json()
    return created["questions"][0]["id"]


def test_sprint_orders_weakest_library_first(tmp_path) -> None:
    with _client(tmp_path) as client:
        # 甲库做对两次（掌握度 +10），乙库不练（掌握度 0）→ 乙库应排在前面
        jia = _seed_library_and_question(client, "甲库", "导数是瞬时变化率。")
        _seed_library_and_question(client, "乙库", "特征值描述线性变换的缩放。")
        for _ in range(2):
            client.post(
                "/api/practice/answer", json={"question_id": jia, "rating": "easy"}
            ).raise_for_status()

        body = client.get("/api/study/sprint", params={"days": 3}).json()
        assert body["hint"] == ""
        assert [day["focus"] for day in body["schedule"]] == ["乙库", "甲库", "乙库"]
        assert body["schedule"][0]["mastery"] == 0
        assert body["schedule"][1]["mastery"] == 20
        # 日期从今天开始、逐天递增
        assert body["schedule"][0]["date"] < body["schedule"][1]["date"]


def test_sprint_clears_due_questions_on_first_pass(tmp_path) -> None:
    with _client(tmp_path) as client:
        first = _seed_library_and_question(client, "高等数学", "导数是瞬时变化率。")
        second = _seed_library_and_question(client, "高等数学", "微分是线性主部。")
        assert first != second

        body = client.get("/api/study/sprint", params={"days": 2}).json()
        assert body["total_due"] == 2
        day_one_tasks = body["schedule"][0]["tasks"]
        assert any("2 道到期练习" in task for task in day_one_tasks)
        # 到期题只在首次清；后续轮次转为巩固出题
        assert body["schedule"][1]["focus"] == "高等数学"
        assert any("出 3 道练习题" in task for task in body["schedule"][1]["tasks"])


def test_sprint_empty_state_has_hint(tmp_path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/study/sprint").json()
        assert body["schedule"] == []
        assert body["total_due"] == 0
        assert "还没有学习数据" in body["hint"]


def test_sprint_rejects_invalid_days(tmp_path) -> None:
    with _client(tmp_path) as client:
        # Query 约束在 FastAPI 校验层拦截
        assert client.get("/api/study/sprint", params={"days": 0}).status_code == 422
        assert client.get("/api/study/sprint", params={"days": 31}).status_code == 422
