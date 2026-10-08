from __future__ import annotations

import json

from fastapi.testclient import TestClient

from studygraph.api import create_app
from studygraph.config import Settings


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "api.db"))
    return TestClient(create_app(settings))


def _read_events(client: TestClient, path: str, payload: dict) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    buffer = ""
    with client.stream("POST", path, json=payload) as response:
        assert response.status_code == 200
        for piece in response.iter_text():
            buffer += piece
            while "\n\n" in buffer:
                raw, buffer = buffer.split("\n\n", 1)
                event = data = None
                for line in raw.splitlines():
                    if line.startswith("event: "):
                        event = line[len("event: ") :]
                    elif line.startswith("data: "):
                        data = json.loads(line[len("data: ") :])
                if event:
                    events.append((event, data or {}))
    return events


def test_health_reports_mock_provider(tmp_path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/health").json()
    assert body == {"status": "ok", "provider": "mock"}


def test_notes_endpoint_feeds_the_library(tmp_path) -> None:
    with _client(tmp_path) as client:
        client.post(
            "/api/knowledge/notes",
            json={"library": "线性代数", "title": "特征值", "content": "特征值描述缩放倍数。"},
        )
        libraries = client.get("/api/knowledge/libraries").json()["libraries"]
    assert any(item["name"] == "线性代数" for item in libraries)


def test_documents_endpoint_uploads_material(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/api/knowledge/documents",
            json={
                "library": "高等数学",
                "title": "导数讲义",
                "content": "导数是瞬时变化率，反映曲线在该点的切线斜率。",
            },
        )
        assert response.status_code == 200
        libraries = client.get("/api/knowledge/libraries").json()["libraries"]
    assert any(item["name"] == "高等数学" for item in libraries)


def test_chat_stream_runs_tools_and_streams(tmp_path) -> None:
    with _client(tmp_path) as client:
        events = _read_events(
            client, "/api/chat/stream", {"message": "帮我算一下 7 * 9", "thread_id": "t"}
        )

    names = [name for name, _ in events]
    assert "done" in names
    text = "".join(data["content"] for name, data in events if name == "token")
    assert "63" in text


def test_hitl_interrupt_then_resume_persists(tmp_path) -> None:
    with _client(tmp_path) as client:
        events = _read_events(
            client,
            "/api/chat/stream",
            {"message": "记住：我在准备月底的微积分测验", "thread_id": "h1"},
        )
        interrupts = [data for name, data in events if name == "interrupt"]
        assert interrupts, "应产生 HITL 中断"
        assert interrupts[0]["action"] == "save_note"

        # 确认之前不落库
        libraries = client.get("/api/knowledge/libraries").json()["libraries"]
        assert libraries == []

        resumed = _read_events(
            client, "/api/chat/resume", {"thread_id": "h1", "approved": True}
        )
        assert "done" in [name for name, _ in resumed]

        libraries = client.get("/api/knowledge/libraries").json()["libraries"]
    assert any(item["name"] == "日常沉淀" for item in libraries)


def test_hitl_rejection_does_not_persist(tmp_path) -> None:
    with _client(tmp_path) as client:
        _read_events(
            client,
            "/api/chat/stream",
            {"message": "帮我记下：明天要交作业", "thread_id": "h2"},
        )
        _read_events(
            client, "/api/chat/resume", {"thread_id": "h2", "approved": False}
        )
        libraries = client.get("/api/knowledge/libraries").json()["libraries"]
    assert libraries == []


def test_learning_loop_endpoints(tmp_path) -> None:
    with _client(tmp_path) as client:
        # 记录一条误区
        feedback = client.post(
            "/api/feedback",
            json={
                "library": "线性代数",
                "question": "什么是特征值？",
                "note": "我把特征向量和基向量搞混了",
            },
        )
        assert feedback.status_code == 200

        # 从错题出题（Mock 模型 → 模板题）
        generated = client.post(
            "/api/practice/generate", json={"source": "mistakes", "count": 3}
        ).json()["questions"]
        assert len(generated) == 1
        assert generated[0]["source"] == "mistake"

        # 新题立即到期
        due = client.get("/api/practice/due").json()["questions"]
        assert any(q["id"] == generated[0]["id"] for q in due)

        # 作答 good → 掌握度 +5
        result = client.post(
            "/api/practice/answer",
            json={"question_id": generated[0]["id"], "rating": "good"},
        ).json()
        assert result["mastery"] == 5

        # 复习计划有建议
        plan = client.get("/api/study/plan").json()
        assert plan["suggestions"]


def test_chat_turn_records_long_term_memory(tmp_path) -> None:
    with _client(tmp_path) as client:
        _read_events(
            client,
            "/api/chat/stream",
            {"message": "记住：我在准备月底的微积分测验", "thread_id": "m1"},
        )
        memories = client.get("/api/memories").json()["memories"]
    assert "我在准备月底的微积分测验" in memories


def test_upload_endpoint_ingests_a_text_file(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/api/knowledge/upload",
            data={"library": "高等数学"},
            files={
                "file": (
                    "导数笔记.md",
                    "导数是瞬时变化率，反映切线斜率。".encode(),
                    "text/markdown",
                )
            },
        )
        assert response.status_code == 200
        assert response.json()["chars"] > 0
        libraries = client.get("/api/knowledge/libraries").json()["libraries"]
    assert any(item["name"] == "高等数学" for item in libraries)


def test_upload_endpoint_rejects_unsupported_file(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/api/knowledge/upload",
            data={"library": "高等数学"},
            files={"file": ("图片.png", b"\x89PNG", "image/png")},
        )
    assert response.status_code == 400
