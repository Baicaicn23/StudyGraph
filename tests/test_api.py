from __future__ import annotations

import json

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


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


def test_documents_listing_returns_library_materials(tmp_path) -> None:
    with _client(tmp_path) as client:
        client.post(
            "/api/knowledge/documents",
            json={
                "library": "高等数学",
                "title": "导数讲义",
                "content": "导数是瞬时变化率。",
            },
        )
        client.post(
            "/api/knowledge/documents",
            json={
                "library": "高等数学",
                "title": "定积分讲义",
                "content": "定积分求区间上的累积量，结果是数值。",
            },
        )
        body = client.get(
            "/api/knowledge/documents", params={"library": "高等数学"}
        ).json()["documents"]
        empty = client.get(
            "/api/knowledge/documents", params={"library": "线性代数"}
        ).json()["documents"]

    titles = [item["title"] for item in body]
    assert titles == ["定积分讲义", "导数讲义"]  # 新的在前
    assert all(item["chars"] > 0 for item in body)
    assert empty == []


def test_document_detail_returns_full_content(tmp_path) -> None:
    with _client(tmp_path) as client:
        created = client.post(
            "/api/knowledge/documents",
            json={
                "library": "高等数学",
                "title": "导数讲义",
                "content": "导数是瞬时变化率，反映切线斜率。",
            },
        ).json()
        body = client.get(
            "/api/knowledge/document", params={"id": created["id"]}
        ).json()["document"]
        missing = client.get("/api/knowledge/document", params={"id": 99999})

    assert body["title"] == "导数讲义"
    assert body["library"] == "高等数学"
    assert "瞬时变化率" in body["content"]
    assert missing.status_code == 404


def test_upload_image_rejected_in_mock_mode(tmp_path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/api/knowledge/upload",
            data={"library": "高等数学"},
            files={"file": ("板书.png", b"\x89PNG-not-really", "image/png")},
        )

    assert response.status_code == 400
    assert "视觉模型" in response.json()["detail"]


def test_upload_image_transcribes_to_markdown(tmp_path, monkeypatch) -> None:
    from langchain_core.messages import AIMessage

    from studygraph.config import Settings as _Settings
    from studygraph.interfaces.api import create_app as _create_app

    settings = _Settings(database_path=str(tmp_path / "vision.db"))
    app = _create_app(settings)

    class _FakeVisionModel:
        _llm_type = "fake-vision"

        async def ainvoke(self, messages):
            # 校验消息结构：文本提示 + base64 图片数据 URI
            blocks = messages[0].content
            assert blocks[0]["type"] == "text"
            image_block = blocks[1]
            assert image_block["type"] == "image_url"
            url = image_block["image_url"]["url"]
            assert url.startswith("data:image/png;base64,")
            return AIMessage(content="# 敛散性\n\n## 定义\n- 单调有界必收敛")

    with TestClient(app) as client:
        monkeypatch.setattr(app.state, "model", _FakeVisionModel())
        response = client.post(
            "/api/knowledge/upload",
            data={"library": "高等数学"},
            files={"file": ("板书.png", b"\x89PNG-fake-bytes", "image/png")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["chars"] > 0

        doc = client.get(
            "/api/knowledge/document", params={"id": body["id"]}
        ).json()["document"]
        assert "敛散性" in doc["content"]
        assert "单调有界必收敛" in doc["content"]


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


def test_activity_endpoint_buckets_today(tmp_path) -> None:
    with _client(tmp_path) as client:
        # 今天记一条误区 → 自评一次（产生练习作答）
        client.post(
            "/api/feedback",
            json={"library": "线性代数", "question": "什么是特征值？", "note": "概念混淆"},
        )
        generated = client.post(
            "/api/practice/generate", json={"source": "mistakes", "count": 1}
        ).json()["questions"]
        client.post(
            "/api/practice/answer",
            json={"question_id": generated[0]["id"], "rating": "good"},
        )
        body = client.get("/api/study/activity", params={"days": 7}).json()["days"]

    assert len(body) == 7
    assert [item["date"] for item in body] == sorted(item["date"] for item in body)
    today = body[-1]
    assert today["mistakes"] >= 1
    assert today["exercises"] >= 1


def test_usage_includes_budget_and_daily_series(tmp_path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/usage", params={"days": 1}).json()

    assert body["daily_token_budget"] == 0  # 默认未设预算
    assert len(body["by_day"]) == 7
    assert all("total_tokens" in item for item in body["by_day"])


def test_chat_turn_records_long_term_memory(tmp_path) -> None:
    with _client(tmp_path) as client:
        _read_events(
            client,
            "/api/chat/stream",
            {"message": "记住：我在准备月底的微积分测验", "thread_id": "m1"},
        )
        memories = client.get("/api/memories").json()["memories"]
    assert any(
        "我在准备月底的微积分测验" in item["content"] for item in memories
    )


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
