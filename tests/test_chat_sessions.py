"""会话持久化 + 项目分组 + 记忆隔离 + 自动标题的回归测试。"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from studygraph.application.title_writer import generate_title
from studygraph.config import Settings
from studygraph.infrastructure.chat_repository import SqliteChatRepository
from studygraph.infrastructure.learning_repository import SqliteLearningRepository
from studygraph.interfaces.api import _status_from_update, create_app

# -- 仓储层：项目 / 会话 / 消息 -----------------------------------------------

def test_default_space_is_created_once_and_adopts_ungrouped(tmp_path) -> None:
    repo = SqliteChatRepository(tmp_path / "chat.db")
    # 无主会话先存在（历史数据）
    stray = repo.create_session(user_id="u", thread_id="t0")

    first = repo.ensure_default_project("u")
    second = repo.ensure_default_project("u")
    assert first == second, "重复调用应返回同一个默认空间"

    projects = repo.list_projects("u")
    assert len(projects) == 1
    assert projects[0]["name"] == repo.DEFAULT_SPACE_NAME
    assert projects[0]["is_default"] == 1

    # 无主会话被收编进默认空间
    assert repo.get_session("u", stray)["project_id"] == first


def test_default_space_adopts_same_name_project(tmp_path) -> None:
    repo = SqliteChatRepository(tmp_path / "chat.db")
    manually = repo.create_project(user_id="u", name=repo.DEFAULT_SPACE_NAME)
    default_id = repo.ensure_default_project("u")
    assert default_id == manually, "同名项目应收编为默认空间，而不是再建一个"
    assert len(repo.list_projects("u")) == 1


def test_project_delete_removes_sessions_messages_and_attachments(tmp_path) -> None:
    repo = SqliteChatRepository(tmp_path / "chat.db")
    default_id = repo.ensure_default_project("u")
    project_id = repo.create_project(user_id="u", name="考研数学")
    session_id = repo.create_session(user_id="u", project_id=project_id, thread_id="t1")
    repo.append_message(session_id, role="user", content="高数问题")
    repo.add_attachment(
        user_id="u",
        session_id=session_id,
        filename="shot.png",
        kind="image",
        content="图",
        storage_path="/tmp/shot.png",
        project_id=str(project_id),
    )
    keep_session = repo.create_session(user_id="u", project_id=default_id, thread_id="t2")

    # 默认空间不可删除
    assert repo.delete_project("u", default_id) is False
    assert any(p["id"] == default_id for p in repo.list_projects("u"))

    # 删普通项目 → 项目连同里面的会话 / 消息 / 附件一起消失
    assert repo.delete_project("u", project_id) is True
    assert repo.list_projects("u")[0]["id"] == default_id
    remaining = repo.list_sessions("u")
    assert [s["id"] for s in remaining] == [keep_session], "只该剩默认空间的会话"
    assert repo.list_messages("u", session_id) == [], "旧会话的消息应一并删除"
    assert repo.list_attachment_paths("u", [session_id]) == []


def test_session_ownership_and_rename(tmp_path) -> None:
    repo = SqliteChatRepository(tmp_path / "chat.db")
    session_id = repo.create_session(user_id="alice", thread_id="t1")

    # 别人看不到这个会话
    assert repo.get_session("bob", session_id) is None
    assert repo.get_session("alice", session_id)["title"] == "新对话"

    assert repo.update_session("alice", session_id, title="导数入门") is True
    assert repo.get_session("alice", session_id)["title"] == "导数入门"


def test_message_roundtrip_with_ownership_check(tmp_path) -> None:
    repo = SqliteChatRepository(tmp_path / "chat.db")
    session_id = repo.create_session(user_id="alice", thread_id="t1")
    repo.append_message(session_id, role="user", content="什么是导数")
    repo.append_message(session_id, role="assistant", content="导数是瞬时变化率")

    assert len(repo.list_messages("alice", session_id)) == 2
    # 越权读取返回空列表（不暴露存在性）
    assert repo.list_messages("bob", session_id) == []


def test_old_database_gets_thread_id_migration(tmp_path) -> None:
    import sqlite3
    import time

    db = str(tmp_path / "legacy.db")
    now = time.time()
    connection = sqlite3.connect(db)
    connection.executescript(
        f"""
        CREATE TABLE chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            project_id INTEGER,
            title TEXT NOT NULL DEFAULT '新对话',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        INSERT INTO chat_sessions (user_id, project_id, title, created_at, updated_at)
        VALUES ('u', NULL, '旧会话', {now:.6f}, {now:.6f});
        """
    )
    connection.commit()
    connection.close()

    repo = SqliteChatRepository(db)
    legacy = repo.get_session("u", 1)
    assert legacy["title"] == "旧会话"
    assert legacy["thread_id"] == ""
    new_id = repo.create_session(user_id="u", thread_id="t-new")
    assert repo.get_session("u", new_id)["thread_id"] == "t-new"


# -- 记忆按项目隔离 -----------------------------------------------------------

def test_memories_are_isolated_by_project(tmp_path) -> None:
    repo = SqliteLearningRepository(tmp_path / "learn.db")
    repo.remember_fact("u", "考研目标：华东师大", created_at=1.0, project_id="1")
    repo.remember_fact("u", "偏好苏格拉底式提问", created_at=2.0, project_id="2")
    repo.remember_fact("u", "全局偏好：中文回答", created_at=3.0)

    project_one = repo.list_memories("u", project_id="1")
    assert [m["content"] for m in project_one] == ["考研目标：华东师大"]

    everything = repo.list_memories("u")
    assert len(everything) == 3  # 不传 project_id → 全部可见


def test_old_memories_migrate_to_default_project(tmp_path) -> None:
    import sqlite3

    db = str(tmp_path / "legacy.db")
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE (user_id, content)
        );
        INSERT INTO memories (user_id, content, created_at) VALUES ('u', '老记忆', 1.0);
        """
    )
    connection.commit()
    connection.close()

    repo = SqliteLearningRepository(db)
    assert repo.list_memories("u", project_id="")[0]["content"] == "老记忆"
    # 迁移后的表支持项目隔离写入
    repo.remember_fact("u", "新记忆", created_at=2.0, project_id="9")
    assert [m["content"] for m in repo.list_memories("u", project_id="9")] == ["新记忆"]


# -- 自动标题 ----------------------------------------------------------------

class _EchoModel:
    """直接返回预设文本的假模型（模拟真实模型的标题输出）。"""

    def __init__(self, text: str) -> None:
        self.text = text

    async def ainvoke(self, _prompt, **_kwargs):
        return AIMessage(content=self.text)


async def test_title_from_model_is_cleaned() -> None:
    title = await generate_title(_EchoModel("标题：「泰勒展开的应用」"), "讲讲泰勒展开")
    assert title == "泰勒展开的应用"


async def test_title_falls_back_when_model_output_too_long() -> None:
    title = await generate_title(
        _EchoModel("这是一段明显超过二十个字上限的啰嗦输出，必须降级为截断方案才对"),
        "帮我复习一下极限的计算技巧和常见的陷阱",
    )
    assert title.endswith("…")
    assert len(title) <= 13  # 12 字 + 省略号


async def test_title_falls_back_when_model_is_none_or_fails() -> None:
    snippet = "讲讲拉格朗日中值定理的几何意义"

    class _Boom:
        async def ainvoke(self, _prompt, **_kwargs):
            raise RuntimeError("模型挂了")

    assert (await generate_title(None, snippet)).startswith("讲讲拉格朗日中值定理")
    assert (await generate_title(_Boom(), snippet)).startswith("讲讲拉格朗日中值定理")
    assert await generate_title(None, "") == "新对话"


# -- 状态事件提取 ------------------------------------------------------------

def test_status_from_update_maps_nodes_and_tools() -> None:
    assert _status_from_update({"route": {}}) == "理解问题"
    assert _status_from_update({"plan": {}}) == "制定学习计划"
    tool_call = _status_from_update(
        {
            "agent": {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "knowledge_search", "args": {}, "id": "1"}],
                    )
                ]
            }
        }
    )
    assert tool_call == "检索知识库"
    # 普通回答（没有工具调用）不播报状态，避免和 token 流打架
    assert _status_from_update({"agent": {"messages": [AIMessage(content="答案")]}}) is None
    assert _status_from_update({"tools": {"messages": []}}) is None


# -- API 层：自动保存 + 状态事件 + 会话接口 -------------------------------------

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


def test_chat_stream_autosaves_session_with_status_and_title(tmp_path) -> None:
    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        events = _read_events(
            client, "/api/chat/stream", {"message": "帮我算一下 7 * 9", "thread_id": "s1"}
        )
        names = [name for name, _ in events]
        assert "status" in names, "应播报节点/工具状态"
        assert "session" in names, "应播报自动保存的会话"

        session_event = next(data for name, data in events if name == "session")
        session_id = session_event["id"]

        # 会话出现在列表里，消息已落库
        chats = client.get("/api/chats").json()["chats"]
        assert any(chat["id"] == session_id for chat in chats)
        messages = client.get(f"/api/chats/{session_id}/messages").json()["messages"]
        roles = [m["role"] for m in messages]
        assert roles == ["user", "assistant"]
        assert messages[0]["content"] == "帮我算一下 7 * 9"
        assert "63" in messages[1]["content"]

        # 自动标题已生成（Mock 模型 → 大概率走截断降级，但一定不再是"新对话"）
        assert chats[0]["title"] != "新对话"


def test_chat_stream_emits_process_steps(tmp_path) -> None:
    """过程流：节点更新要翻译成 step 事件，并随助手消息落库（历史可见）。"""

    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        events = _read_events(
            client,
            "/api/chat/stream",
            {"message": "帮我总结今天的错题", "thread_id": "steps-1"},
        )
        steps = [data for name, data in events if name == "step"]
        assert steps, "应播报过程步骤（思考/工具）"
        assert steps[0]["kind"] == "thinking"
        assert steps[0]["title"] == "理解问题"
        assert all({"kind", "title", "detail"} <= set(step) for step in steps)

        session_id = next(d for n, d in events if n == "session")["id"]
        messages = client.get(f"/api/chats/{session_id}/messages").json()["messages"]
        assistant = next(m for m in messages if m["role"] == "assistant")
        assert assistant["steps"], "助手消息应带着过程步骤落库"
        assert assistant["steps"][0]["title"] == "理解问题"


def test_memories_without_project_fall_back_to_default_space(tmp_path) -> None:
    """没带project_id 发消息，记忆也要落进默认空间（不能进 project_id='' 的黑洞桶）。"""

    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        default_id = client.get("/api/projects").json()["projects"][0]["id"]

        _read_events(
            client,
            "/api/chat/stream",
            {"message": "记住：兜底也要记住我", "thread_id": "fb-1"},
        )

        scoped = client.get(
            "/api/memories", params={"project_id": default_id}
        ).json()["memories"]
        assert any(m["content"] == "兜底也要记住我" for m in scoped), (
            "记忆应能在默认空间里查到，否则表现为「明明记住了却忘了」"
        )


def test_chat_stream_with_existing_session_reuses_thread(tmp_path) -> None:
    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        project_id = client.post(
            "/api/projects", data={"name": "考研数学"}, params={"user_id": "alice"}
        ).json()["id"]
        first = _read_events(
            client,
            "/api/chat/stream",
            {"message": "什么是导数", "thread_id": "s2", "user_id": "alice"},
        )
        session_id = next(d for n, d in first if n == "session")["id"]
        # 挂到项目下
        client.put(
            f"/api/chats/{session_id}",
            data={"project_id": str(project_id)},
            params={"user_id": "alice"},
        )

        chats = client.get(
            "/api/chats", params={"user_id": "alice", "project_id": project_id}
        ).json()["chats"]
        assert [chat["id"] for chat in chats] == [session_id]

        # 续聊同一会话：不新建，消息继续追加
        second = _read_events(
            client,
            "/api/chat/stream",
            {
                "message": "那偏导数呢",
                "thread_id": "s2",
                "user_id": "alice",
                "session_id": session_id,
                "project_id": project_id,
            },
        )
        session_events = [d for n, d in second if n == "session"]
        assert session_events and session_events[0]["id"] == session_id
        messages = client.get(
            f"/api/chats/{session_id}/messages", params={"user_id": "alice"}
        ).json()["messages"]
        assert len(messages) == 4  # 两轮 user+assistant


def test_chat_stream_rejects_foreign_session(tmp_path) -> None:
    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/projects", data={"name": "x"}, params={"user_id": "alice"}
        )
        _ = created.json()
        response = client.post(
            "/api/chat/stream",
            json={"message": "hi", "thread_id": "s3", "session_id": 99999},
        )
    assert response.status_code == 404


def test_project_endpoints_crud(tmp_path) -> None:
    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        # 首次列出 → 自动创建默认对话空间且排最前
        seeded = client.get("/api/projects", params={"user_id": "alice"}).json()[
            "projects"
        ]
        assert seeded[0]["name"] == "默认对话空间"
        assert seeded[0]["is_default"] == 1
        default_id = seeded[0]["id"]

        created = client.post(
            "/api/projects", data={"name": "线代冲刺"}, params={"user_id": "alice"}
        ).json()
        project_id = created["id"]

        # 重命名
        renamed = client.put(
            f"/api/projects/{project_id}",
            data={"name": "线代总复习"},
            params={"user_id": "alice"},
        )
        assert renamed.status_code == 200

        # 重名项目被拒：409 而不是 500
        duplicate = client.post(
            "/api/projects", data={"name": "线代总复习"}, params={"user_id": "alice"}
        )
        assert duplicate.status_code == 409

        projects = client.get("/api/projects", params={"user_id": "alice"}).json()[
            "projects"
        ]
        assert [p["name"] for p in projects] == ["默认对话空间", "线代总复习"]

        # 默认空间删除被拒：400
        blocked = client.delete(
            f"/api/projects/{default_id}", params={"user_id": "alice"}
        )
        assert blocked.status_code == 400
        assert "不能删除" in blocked.json()["detail"]

        # 普通项目可删
        deleted = client.delete(
            f"/api/projects/{project_id}", params={"user_id": "alice"}
        )
        assert deleted.status_code == 200
        missing = client.delete(f"/api/projects/{project_id}", params={"user_id": "alice"})
        assert missing.status_code == 404


def test_chat_messages_endpoint_404s_never_leak(tmp_path) -> None:
    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)) as client:
        # 不存在的会话：返回空（所有权校验），不报 500
        body = client.get(
            "/api/chats/424242/messages", params={"user_id": "alice"}
        ).json()
        assert body == {"messages": []}
