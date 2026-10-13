"""增删改查补齐的回归测试：知识库编辑/删除、错题/练习题/记忆删除。

本文件还覆盖一批**「写完/删完不报错但留下脏数据」**的级联问题（M14.2 审计发现）：
跨用户读消息的 404 一致性、项目重命名撞名 500、删误区/资料后派生题悬挂、
删项目后孤儿记忆、删会话后 LangGraph 检查点线程残留。
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from zhiji.config import Settings
from zhiji.interfaces.api import create_app


def _client(tmp_path) -> TestClient:
    settings = Settings(database_path=str(tmp_path / "crud.db"))
    return TestClient(create_app(settings))


def _scalar(db_path, sql: str, params: list) -> int:
    """直接查库取一个标量（断言"这行到底还在不在"，比看接口返回更硬）。"""

    connection = sqlite3.connect(str(db_path))
    try:
        return int(connection.execute(sql, params).fetchone()[0])
    finally:
        connection.close()


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


def test_feedback_kind_roundtrip_and_validation(tmp_path) -> None:
    """误区错误类型：可选、可回读、非法值拒绝。"""

    with _client(tmp_path) as client:
        created = client.post(
            "/api/feedback",
            json={
                "library": "高等数学-微积分",
                "question": "可去间断点的判定",
                "note": "忽略了「极限值是否等于函数值」",
                "kind": "concept",
            },
        )
        assert created.status_code == 200

        listing = client.get("/api/feedback").json()["feedback"]
        assert listing[0]["kind"] == "concept"

        # 不传类型：合法（留空，前端显示"未分类"）
        client.post(
            "/api/feedback",
            json={"library": "线性代数", "question": "特征值", "note": "搞混了"},
        ).raise_for_status()
        assert client.get("/api/feedback").json()["feedback"][0]["kind"] == ""

        # 非法类型：400
        assert (
            client.post(
                "/api/feedback",
                json={"library": "x", "note": "y", "kind": "not-a-kind"},
            ).status_code
            == 400
        )


def _read_stream(
    client: TestClient,
    message: str,
    *,
    user_id: str = "local",
    project_id: int | None = None,
    thread_id: str | None = None,
) -> None:
    payload: dict = {
        "message": message,
        "user_id": user_id,
        "thread_id": thread_id or f"crud-{abs(hash(message)) % 99999}",
    }
    if project_id is not None:
        payload["project_id"] = project_id
    with client.stream("POST", "/api/chat/stream", json=payload) as response:
        assert response.status_code == 200
        for _ in response.iter_text():
            pass


# -- 项目（课程空间）：重命名约束 -------------------------------------------------

def test_project_rename_to_existing_name_is_409(tmp_path) -> None:
    """重命名撞别的项目名 → 409。

    回归：`rename_project` 曾不处理 `UNIQUE (user_id, name)`，撞名时
    `sqlite3.IntegrityError` 冒到接口层 → 500（创建路径早就 409，重命名却漏了）。
    只在**跨行**撞名时才触发；改成自己当前的名字不算冲突（幂等 200）。
    """

    with _client(tmp_path) as client:
        a = client.post(
            "/api/projects", params={"user_id": "alice"}, data={"name": "高数冲刺"}
        ).json()["id"]
        b = client.post(
            "/api/projects", params={"user_id": "alice"}, data={"name": "线代冲刺"}
        ).json()["id"]

        clash = client.put(
            f"/api/projects/{b}", params={"user_id": "alice"}, data={"name": "高数冲刺"}
        )
        assert clash.status_code == 409

        same = client.put(
            f"/api/projects/{b}", params={"user_id": "alice"}, data={"name": "线代冲刺"}
        )
        assert same.status_code == 200

        blank = client.put(
            f"/api/projects/{b}", params={"user_id": "alice"}, data={"name": "   "}
        )
        assert blank.status_code == 400

        assert a != b


# -- 会话消息：跨用户 404 一致性 -------------------------------------------------

def test_cross_user_session_messages_is_404(tmp_path) -> None:
    """别人（或不存在）的会话读消息 → 404，与删/改一致。

    回归：`list_messages` 对非归属会话返回空列表，接口层照常 200 —— 调用方
    分不清"这个会话没消息"和"这不是你的会话"，与其他会话接口的语义不一致。
    """

    with _client(tmp_path) as client:
        _read_stream(client, "记住：我在复习四级英语", user_id="alice")
        sid = client.get("/api/chats", params={"user_id": "alice"}).json()["chats"][0]["id"]

        assert (
            client.get(
                f"/api/chats/{sid}/messages", params={"user_id": "bob"}
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/chats/{sid}/messages", params={"user_id": "alice"}
            ).status_code
            == 200
        )


# -- 级联删除：不让派生数据变悬挂 -------------------------------------------------

def test_feedback_delete_cascades_derived_question(tmp_path) -> None:
    """删误区要连带删掉由它派生的变式题（否则 source_feedback_id 悬挂）。"""

    db = tmp_path / "crud.db"
    with _client(tmp_path) as client:
        fid = client.post(
            "/api/feedback",
            json={"user_id": "alice", "library": "高数", "question": "求极限", "note": "漏了约分"},
        ).json()["id"]
        questions = client.post(
            "/api/practice/generate",
            json={"user_id": "alice", "source": "mistakes", "mistake_ids": [fid], "count": 1},
        ).json()["questions"]
        assert questions, "应先由误区出题"
        qid = questions[0]["id"]
        assert _scalar(
            db, "SELECT COUNT(*) FROM practice_questions WHERE id = ?", [qid]
        ) == 1

        assert (
            client.delete(f"/api/feedback/{fid}", params={"user_id": "alice"}).status_code
            == 200
        )
        assert _scalar(
            db, "SELECT COUNT(*) FROM practice_questions WHERE id = ?", [qid]
        ) == 0
        assert _scalar(
            db,
            "SELECT COUNT(*) FROM practice_questions WHERE source_feedback_id = ?",
            [fid],
        ) == 0


def test_document_delete_cascades_derived_questions(tmp_path) -> None:
    """删资料要连带删掉由它片段派生的练习题（否则 source_chunk_id 悬挂）。"""

    db = tmp_path / "crud.db"
    with _client(tmp_path) as client:
        doc = client.post(
            "/api/knowledge/documents",
            json={
                "library": "高数",
                "title": "极限四则运算",
                "content": "极限的四则运算：和差积商的极限等于极限的和差积商。",
            },
        ).json()["id"]
        questions = client.post(
            "/api/practice/generate",
            json={"user_id": "alice", "source": "knowledge_base", "library": "高数", "count": 1},
        ).json()["questions"]
        assert questions, "应先由资料出题"
        qid = questions[0]["id"]

        assert client.delete("/api/knowledge/document", params={"id": doc}).status_code == 200
        assert _scalar(
            db, "SELECT COUNT(*) FROM practice_questions WHERE id = ?", [qid]
        ) == 0


def test_library_delete_cascades_derived_questions(tmp_path) -> None:
    """删整库要连带删掉由库里资料派生的练习题。"""

    db = tmp_path / "crud.db"
    with _client(tmp_path) as client:
        client.post(
            "/api/knowledge/documents",
            json={
                "library": "临时库",
                "title": "草稿",
                "content": "洛必达法则适用于 0/0 型未定式。",
            },
        )
        questions = client.post(
            "/api/practice/generate",
            json={"user_id": "alice", "source": "knowledge_base", "library": "临时库", "count": 1},
        ).json()["questions"]
        assert questions, "应先由资料出题"

        assert client.delete("/api/knowledge/library", params={"name": "临时库"}).status_code == 200
        assert _scalar(db, "SELECT COUNT(*) FROM practice_questions", []) == 0


def test_project_delete_cascades_memories(tmp_path) -> None:
    """删项目要连带清掉它的长期记忆（否则按项目查永远读不到的孤儿记忆）。"""

    with _client(tmp_path) as client:
        pid = client.post(
            "/api/projects", params={"user_id": "alice"}, data={"name": "期末冲刺"}
        ).json()["id"]
        _read_stream(
            client, "记住：我在准备月底的微积分测验", user_id="alice", project_id=pid
        )
        assert client.get("/api/memories", params={"user_id": "alice"}).json()["memories"]

        assert (
            client.delete(f"/api/projects/{pid}", params={"user_id": "alice"}).status_code
            == 200
        )
        assert client.get("/api/memories", params={"user_id": "alice"}).json()["memories"] == []


def test_delete_session_drops_checkpoint_thread(tmp_path) -> None:
    """删会话要把它的 LangGraph 检查点线程一起清掉。

    检查点与会话是两套存储：`chat_sessions` 删了，`checkpoints`/`writes` 里的
    线程还在（仍能还原对话正文）。不清理会越攒越多（实测 33 线程 vs 7 会话）。
    """

    db = tmp_path / "crud.db"
    thread = "crud-checkpoint-drop"
    with _client(tmp_path) as client:
        _read_stream(client, "帮我制定一份英语四级复习计划", thread_id=thread)
        assert _scalar(
            db, "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", [thread]
        ) > 0, "对话后应产生检查点"

        chats = client.get("/api/chats").json()["chats"]
        sid = next(c["id"] for c in chats if c["thread_id"] == thread)

        assert client.delete(f"/api/chats/{sid}").status_code == 200
        assert (
            _scalar(db, "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", [thread]) == 0
        )
        assert _scalar(db, "SELECT COUNT(*) FROM writes WHERE thread_id = ?", [thread]) == 0
