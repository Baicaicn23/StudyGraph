"""增删改查补齐的回归测试：知识库编辑/删除、错题/练习题/记忆删除。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from studygraph.config import Settings
from studygraph.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "crud.db"))
    return TestClient(create_app(settings))


# -- 知识库：编辑 / 删除 --------------------------------------------------------

def test_document_update_reindexes_content(tmp_path) -> None:
    with _client(tmp_path) as client:
        created = client.post(
            "/api/knowledge/notes",
            json={
                "library": "高等数学",
                "title": "导数讲义",
                "content": "导数是瞬时变化率，反映切线斜率。",
            },
        ).json()
        doc_id = created["id"]

        # 改写正文：旧关键词检索不到，新关键词能检索到
        updated = client.put(
            "/api/knowledge/document",
            json={
                "id": doc_id,
                "title": "导数与微分",
                "content": "微分是线性主部，泰勒展开是近似工具。",
            },
        )
        assert updated.status_code == 200

        body = client.get("/api/knowledge/document", params={"id": doc_id}).json()[
            "document"
        ]
        assert body["title"] == "导数与微分"
        assert "瞬时变化率" not in body["content"]

        docs = client.get(
            "/api/knowledge/documents", params={"library": "高等数学"}
        ).json()["documents"]
        assert docs[0]["title"] == "导数与微分"


def test_document_delete_and_missing_404(tmp_path) -> None:
    with _client(tmp_path) as client:
        created = client.post(
            "/api/knowledge/notes",
            json={"library": "线性代数", "title": "特征值", "content": "特征值描述缩放倍数。"},
        ).json()

        deleted = client.delete("/api/knowledge/document", params={"id": created["id"]})
        assert deleted.status_code == 200

        assert (
            client.get("/api/knowledge/document", params={"id": created["id"]}).status_code
            == 404
        )
        again = client.delete("/api/knowledge/document", params={"id": created["id"]})
        assert again.status_code == 404


def test_library_delete_removes_everything(tmp_path) -> None:
    with _client(tmp_path) as client:
        client.post(
            "/api/knowledge/notes",
            json={"library": "临时库", "title": "草稿", "content": "会被一起删掉的内容。"},
        )
        client.post(
            "/api/knowledge/notes",
            json={"library": "保留库", "title": "重要笔记", "content": "不受影响的内容。"},
        )

        deleted = client.delete("/api/knowledge/library", params={"name": "临时库"})
        assert deleted.status_code == 200

        names = [lib["name"] for lib in client.get("/api/knowledge/libraries").json()["libraries"]]
        assert "临时库" not in names
        assert "保留库" in names

        missing = client.delete("/api/knowledge/library", params={"name": "临时库"})
        assert missing.status_code == 404


# -- 错题 / 练习题 / 记忆：删除 ---------------------------------------------------

def test_feedback_delete_with_ownership(tmp_path) -> None:
    with _client(tmp_path) as client:
        feedback_id = client.post(
            "/api/feedback",
            json={"user_id": "alice", "library": "高数", "question": "q", "note": "n"},
        ).json()["id"]

        # 别人删不了
        foreign = client.delete(f"/api/feedback/{feedback_id}", params={"user_id": "bob"})
        assert foreign.status_code == 404

        ok = client.delete(f"/api/feedback/{feedback_id}", params={"user_id": "alice"})
        assert ok.status_code == 200
        assert client.get("/api/feedback", params={"user_id": "alice"}).json()["feedback"] == []


def test_practice_question_delete(tmp_path) -> None:
    with _client(tmp_path) as client:
        client.post(
            "/api/feedback",
            json={"library": "线性代数", "question": "什么是特征值？", "note": "概念混淆"},
        )
        generated = client.post(
            "/api/practice/generate", json={"source": "mistakes", "count": 1}
        ).json()["questions"]
        question_id = generated[0]["id"]

        deleted = client.delete(f"/api/practice/{question_id}")
        assert deleted.status_code == 200
        due = client.get("/api/practice/due").json()["questions"]
        assert all(q["id"] != question_id for q in due)

        missing = client.delete(f"/api/practice/{question_id}")
        assert missing.status_code == 404


def test_memory_delete(tmp_path) -> None:
    with _client(tmp_path) as client:
        _read_stream(client, "记住：我在准备月底的微积分测验")
        memories = client.get("/api/memories").json()["memories"]
        assert memories, "应先产生至少一条记忆"
        memory_id = memories[0]["id"]

        deleted = client.delete(f"/api/memories/{memory_id}")
        assert deleted.status_code == 200
        remaining = client.get("/api/memories").json()["memories"]
        assert all(item["id"] != memory_id for item in remaining)


def _read_stream(client: TestClient, message: str) -> None:
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": message, "thread_id": f"crud-{abs(hash(message)) % 99999}"},
    ) as response:
        assert response.status_code == 200
        for _ in response.iter_text():
            pass
