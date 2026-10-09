"""聊天附件：上传抽取、归属校验、随消息发送并落库。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "attach.db"))
    return TestClient(create_app(settings))


def test_attachment_upload_txt_and_send_with_message(tmp_path) -> None:
    with _client(tmp_path) as client:
        uploaded = client.post(
            "/api/chat/attachments",
            files={"file": ("导数讲义.txt", "导数是瞬时变化率".encode(), "text/plain")},
        )
        assert uploaded.status_code == 200
        body = uploaded.json()
        assert body["filename"] == "导数讲义.txt"
        assert body["kind"] == "file"
        assert body["chars"] > 0
        attachment_id = body["id"]

        # 带附件发消息：正常流式返回（Mock 图），消息落库时记录附件名
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "帮我讲讲附件里的内容",
                "thread_id": "attach-1",
                "attachment_ids": [attachment_id],
            },
        ) as response:
            assert response.status_code == 200
            for _ in response.iter_text():
                pass

        session_id = client.get("/api/chats").json()["chats"][0]["id"]
        messages = client.get(f"/api/chats/{session_id}/messages").json()["messages"]
        user_messages = [m for m in messages if m["role"] == "user"]
        assert user_messages[0]["content"] == "帮我讲讲附件里的内容"
        assert user_messages[0]["attachments"] == ["导数讲义.txt"]


def test_attachment_ownership_and_missing_session(tmp_path) -> None:
    with _client(tmp_path) as client:
        uploaded = client.post(
            "/api/chat/attachments",
            files={"file": ("a.txt", b"hello", "text/plain")},
            data={"user_id": "alice"},
        )
        attachment_id = uploaded.json()["id"]

        # 别人的会话不存在 / 附件归属他人时查不到 → 发送时被忽略（不 500）
        foreign = client.post(
            "/api/chat/attachments",
            files={"file": ("b.txt", b"world", "text/plain")},
            data={"user_id": "bob", "session_id": "99999"},
        )
        assert foreign.status_code == 404

        messages = client.get(
            f"/api/chats/{attachment_id}/messages", params={"user_id": "alice"}
        )
        # 附件 id 不是会话 id：越权读取返回空列表（不报错）
        assert messages.json()["messages"] == []


def test_attachment_unsupported_type_rejected(tmp_path) -> None:
    with _client(tmp_path) as client:
        rejected = client.post(
            "/api/chat/attachments",
            files={"file": ("virus.exe", b"MZ...", "application/octet-stream")},
        )
        assert rejected.status_code == 400
        assert "TXT" in rejected.json()["detail"] or "支持" in rejected.json()["detail"]


def test_empty_text_file_rejected(tmp_path) -> None:
    with _client(tmp_path) as client:
        rejected = client.post(
            "/api/chat/attachments",
            files={"file": ("empty.txt", b"   \n  ", "text/plain")},
        )
        assert rejected.status_code == 400
        assert "没有可提取" in rejected.json()["detail"]


def test_image_rejected_on_mock_model(tmp_path) -> None:
    """Mock 模型不能识图，应立刻 400 并提示配置真实模型。"""

    with _client(tmp_path) as client:
        rejected = client.post(
            "/api/chat/attachments",
            files={"file": ("shot.png", b"\x89PNG fake", "image/png")},
        )
        assert rejected.status_code == 400
        assert "Mock" in rejected.json()["detail"]
