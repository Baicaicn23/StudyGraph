"""接口层：HTTP。这里是**组合根**——把基础设施实现注入应用层服务与图。

启动：`uv run uvicorn studygraph.interfaces.api:app --port 8011 --reload`

SSE 事件协议（每行一个事件，`data` 为 JSON）：

    event: token      data: {"content": "..."}
    event: status     data: {"label": "检索知识库"}        # 节点/工具进展
    event: session    data: {"id": 3, "title": "导数与极限"}  # 会话保存/自动标题
    event: interrupt  data: {"action": "save_note", "library": "...", ...}
    event: done       data: {}
    event: error      data: {"message": "..."}
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from dataclasses import replace

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..application import tools
from ..application.graph import build_graph
from ..application.guardrails import screen_input, screen_output
from ..application.image_notes import ImageNoteError, image_to_markdown
from ..application.learning_service import LearningService
from ..application.title_writer import generate_title
from ..config import Settings, get_settings, parse_mcp_servers
from ..domain.errors import LearningError
from ..infrastructure.chat_repository import SqliteChatRepository
from ..infrastructure.embeddings import get_embedder
from ..infrastructure.extract import ExtractError, extract_text, is_image
from ..infrastructure.knowledge import KnowledgeStore
from ..infrastructure.learning_repository import SqliteLearningRepository
from ..infrastructure.llm import build_chat_model
from ..infrastructure.mcp_bridge import connect_and_register
from ..infrastructure.usage_repository import SqliteUsageRepository


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(default="web", max_length=64)
    user_id: str = Field(default="local", max_length=64)
    knowledge_bases: list[str] = Field(default_factory=list)
    # 会话持久化：session_id 指向已保存的会话；缺省时自动新建（自动保存）。
    # project_id 让本轮记忆按项目隔离（不同项目的记忆互不串味）。
    session_id: int | None = None
    project_id: int | None = None


class ResumeRequest(BaseModel):
    thread_id: str = Field(default="web", max_length=64)
    approved: bool = False
    # resume 时补齐会话归属：回答写回这个会话，但不重复落用户消息。
    session_id: int | None = None
    user_id: str = Field(default="local", max_length=64)


class NoteRequest(BaseModel):
    library: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=20000)


class DocumentRequest(BaseModel):
    library: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200000)


class FeedbackRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    library: str = Field(default="", max_length=64)
    question: str = Field(default="", max_length=4000)
    note: str = Field(min_length=1, max_length=2000)


class GenerateRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    source: str = Field(default="knowledge_base", max_length=32)
    library: str = Field(default="", max_length=64)
    count: int = Field(default=3, ge=1, le=10)
    # 难度：basic / apply / transfer / auto（auto 按该学科掌握度自动分档）
    difficulty: str = Field(default="auto", max_length=16)


class AnswerRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    question_id: int
    rating: str = Field(min_length=1, max_length=16)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 工具名 → 用户能看懂的状态文案（前端状态行直接展示）。
_TOOL_STATUS = {
    "knowledge_search": "检索知识库",
    "mistake_search": "查阅错题记录",
    "save_note": "整理笔记",
}
_NODE_STATUS = {"route": "理解问题", "plan": "制定学习计划"}


def _tool_status(name: str) -> str:
    return _TOOL_STATUS.get(name, f"调用工具 {name}")


def _status_from_update(chunk: dict) -> str | None:
    """从 updates 流里提取一条状态文案；没有值得播报的返回 None。

    agent 节点结束时若带着工具调用，说明接下来要跑工具——此刻播报
    「检索知识库…」正好卡在工具执行**之前**，用户能看到实时动作。
    """

    node = next(iter(chunk))
    update = chunk[node]
    if node in _NODE_STATUS:
        return _NODE_STATUS[node]
    if node == "agent":
        messages = update.get("messages", []) if isinstance(update, dict) else []
        for message in messages:
            calls = getattr(message, "tool_calls", None) or []
            if calls:
                return _tool_status(calls[0]["name"])
    return None


async def _run_stream(
    graph,
    payload: object,
    config: dict,
    *,
    chat: object | None = None,
    session: dict | None = None,
    user_id: str = "local",
    user_message: str = "",
    model: object | None = None,
    persist_user: bool = True,
):
    """跑图并转成 SSE 流。

    - ``status`` 事件：让前端在等待时显示「理解问题 / 检索知识库…」；
    - 会话持久化：session 传入就落库消息，标题还是「新对话」时让模型
      起一个短标题。落库失败不影响对话本身。
    - ``persist_user=False`` 用于 interrupt 后的 resume：用户消息在首段
      已经落过库，这里只负责补上续写出的回答。
    """

    interrupted = False
    answer_parts: list[str] = []
    if session is not None and chat is not None:
        try:
            if persist_user:
                chat.append_message(session["id"], role="user", content=user_message)
            chat.update_session(user_id, session["id"], touch=True)
            yield _sse("session", {"id": session["id"], "title": session["title"]})
        except Exception:  # noqa: BLE001 — 落库失败不拦对话
            session = None
    try:
        async for mode, chunk in graph.astream(
            payload, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                message, _meta = chunk
                if isinstance(message, (AIMessage, AIMessageChunk)) and message.content:
                    answer_parts.append(str(message.content))
                    yield _sse("token", {"content": message.content})
            elif isinstance(chunk, dict) and "__interrupt__" in chunk:
                interrupted = True
                yield _sse("interrupt", chunk["__interrupt__"][0].value)
            elif isinstance(chunk, dict) and chunk:
                status = _status_from_update(chunk)
                if status:
                    yield _sse("status", {"label": status})
        if not interrupted:
            warning = await _screen_last_answer(graph, config)
            if warning:
                yield _sse("guard", {"reason": warning})
            if session is not None and chat is not None:
                answer = "".join(answer_parts).strip()
                if answer:
                    chat.append_message(session["id"], role="assistant", content=answer)
                if session["title"] in ("", "新对话"):
                    title = await generate_title(model, user_message)
                    chat.update_session(user_id, session["id"], title=title)
                    yield _sse("session", {"id": session["id"], "title": title})
        yield _sse("done", {})
    except Exception as exc:  # noqa: BLE001 - 把失败作为事件返回，而不是断连
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})


async def _screen_last_answer(graph, config: dict) -> str | None:
    """输出护栏：复核最终回答（空回答 / 系统提示词泄漏）。"""

    try:
        state = await graph.aget_state(config)
        messages = state.values.get("messages", [])
        last = messages[-1] if messages else None
        return screen_output(str(getattr(last, "content", "")))
    except Exception:  # noqa: BLE001 - 复核失败不应影响正常返回
        return None


async def _refusal_stream(message: str):
    yield _sse("token", {"content": message})
    yield _sse("done", {})


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved = settings or get_settings()
        knowledge = KnowledgeStore(
            resolved.database_path, embedder=get_embedder(resolved)
        )
        repository = SqliteLearningRepository(resolved.database_path)
        usage_repository = SqliteUsageRepository(resolved.database_path)
        chat_repository = SqliteChatRepository(resolved.database_path)
        learning = LearningService(knowledge, repository)
        tools.configure(knowledge, repository)
        mcp_clients, _ = await connect_and_register(
            parse_mcp_servers(resolved.mcp_servers), tools.register_mcp_tool
        )
        model = build_chat_model(resolved)
        tier_models: dict[str, object] = {}

        def model_router(tier: str):
            name = {
                "small": resolved.model_small,
                "large": resolved.model_large,
            }.get(tier, "")
            if not name:
                return model
            if tier not in tier_models:
                tier_models[tier] = build_chat_model(replace(resolved, model=name))
            return tier_models[tier]

        async with AsyncSqliteSaver.from_conn_string(resolved.database_path) as checkpointer:
            app.state.settings = resolved
            app.state.store = knowledge
            app.state.learning = learning
            app.state.chat = chat_repository
            app.state.model = model
            app.state.usage = usage_repository
            app.state.graph = build_graph(
                model=model,
                checkpointer=checkpointer,
                max_tool_rounds=resolved.max_tool_rounds,
                tool_timeout=resolved.tool_timeout_seconds,
                tool_retries=resolved.tool_max_retries,
                max_history_messages=resolved.max_history_messages,
                model_router=model_router,
                usage_repository=usage_repository,
                daily_token_budget=resolved.daily_token_budget,
                budget_exceeded_action=resolved.budget_exceeded_action,
            )
            yield
        for client in mcp_clients:
            await client.close()

    app = FastAPI(title="StudyGraph API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health(request: Request) -> dict:
        return {"status": "ok", "provider": request.app.state.settings.llm_provider}

    @app.get("/api/knowledge/libraries")
    async def list_libraries(request: Request) -> dict:
        return {"libraries": request.app.state.store.list_libraries()}

    @app.get("/api/knowledge/documents")
    async def list_documents(
        request: Request, library: str = Query(min_length=1, max_length=64)
    ) -> dict:
        return {"documents": request.app.state.store.list_documents(library)}

    @app.get("/api/knowledge/document")
    async def get_document(
        request: Request, id: int = Query(ge=1)
    ) -> dict:
        document = request.app.state.store.get_document(id)
        if document is None:
            raise HTTPException(status_code=404, detail="资料不存在")
        return {"document": document}

    @app.post("/api/knowledge/notes")
    async def add_note(body: NoteRequest, request: Request) -> dict:
        document_id = request.app.state.store.add_note(
            body.library, body.title, body.content
        )
        return {"id": document_id, "library": body.library, "title": body.title}

    @app.post("/api/knowledge/documents")
    async def add_document(body: DocumentRequest, request: Request) -> dict:
        document_id = request.app.state.store.add_document(
            body.library, body.title, body.content
        )
        return {"id": document_id, "library": body.library, "title": body.title}

    @app.post("/api/knowledge/upload")
    async def upload_document(
        request: Request,
        library: str = Form(min_length=1, max_length=64),
        file: UploadFile = File(...),  # noqa: B008 — FastAPI 的标准依赖注入写法
    ) -> dict:
        data = await file.read()
        if len(data) > request.app.state.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="文件太大")
        title = (file.filename or "上传资料").strip()

        # 图片走视觉转写（拍照课件/板书 → Markdown 入库），文本走原抽取管线。
        if is_image(file.filename or ""):
            model = request.app.state.model
            if getattr(model, "_llm_type", "") == "study-mock":
                raise HTTPException(
                    status_code=400,
                    detail="图片识别需要真实视觉模型（当前是 Mock 模式，"
                    "请在 .env 里配置 provider=openai）",
                )
            try:
                text = await image_to_markdown(model, file.filename or "", data)
            except ImageNoteError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        else:
            try:
                text = extract_text(file.filename or "", data)
            except ExtractError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not text.strip():
            raise HTTPException(status_code=400, detail="文件里没有可提取的文本")
        document_id = request.app.state.store.add_document(library, title, text)
        return {"id": document_id, "library": library, "title": title, "chars": len(text)}

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
        # 输入护栏：越界 / 注入 在进入图之前就拦下，直接流式返回拒绝话术。
        refusal = screen_input(body.message)
        if refusal:
            return StreamingResponse(
                _refusal_stream(refusal),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        config = {"configurable": {"thread_id": body.thread_id}}
        learning: LearningService = request.app.state.learning
        learning.remember(
            body.user_id, body.message, project_id=str(body.project_id or "")
        )
        payload: dict = {
            "messages": [HumanMessage(body.message)],
            "user_id": body.user_id,
            "memories": [
                m["content"]
                for m in learning.memories(
                    body.user_id, project_id=str(body.project_id or "")
                )
            ],
            # 掌握度快照：system prompt 据此调整讲解深度（贴合学生水平）。
            "progress": learning.progress(body.user_id),
        }
        if body.knowledge_bases:
            payload["knowledge_bases"] = body.knowledge_bases

        # 自动保存：没有 session_id 就新建会话（标题先占位，回复完后自动起名）。
        session = None
        chat = request.app.state.chat
        if body.session_id is not None:
            session = chat.get_session(body.user_id, body.session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="会话不存在")
        else:
            session_id = chat.create_session(
                user_id=body.user_id,
                project_id=body.project_id,
                thread_id=body.thread_id,
            )
            session = chat.get_session(body.user_id, session_id)
        return StreamingResponse(
            _run_stream(
                request.app.state.graph,
                payload,
                config,
                chat=chat,
                session=session,
                user_id=body.user_id,
                user_message=body.message,
                model=request.app.state.model,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/chat/resume")
    async def chat_resume(body: ResumeRequest, request: Request) -> StreamingResponse:
        config = {"configurable": {"thread_id": body.thread_id}}
        session = None
        if body.session_id is not None:
            session = request.app.state.chat.get_session(body.user_id, body.session_id)
        return StreamingResponse(
            _run_stream(
                request.app.state.graph,
                Command(resume=body.approved),
                config,
                chat=request.app.state.chat,
                session=session,
                user_id=body.user_id,
                model=request.app.state.model,
                persist_user=False,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/feedback")
    async def add_feedback(body: FeedbackRequest, request: Request) -> dict:
        feedback_id = request.app.state.learning.add_feedback(
            user_id=body.user_id,
            library=body.library,
            question=body.question,
            note=body.note,
        )
        return {"id": feedback_id}

    @app.get("/api/feedback")
    async def list_feedback(request: Request, user_id: str = "local") -> dict:
        return {"feedback": request.app.state.learning.list_feedback(user_id)}

    @app.post("/api/practice/generate")
    async def generate_practice(body: GenerateRequest, request: Request) -> dict:
        try:
            questions = await request.app.state.learning.generate(
                user_id=body.user_id,
                source=body.source,
                library=body.library,
                count=body.count,
                model=request.app.state.model,
                difficulty=body.difficulty,
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"questions": questions}

    @app.get("/api/practice/due")
    async def due_practice(request: Request, user_id: str = "local") -> dict:
        return {"questions": request.app.state.learning.due_questions(user_id)}

    @app.post("/api/practice/answer")
    async def answer_practice(body: AnswerRequest, request: Request) -> dict:
        try:
            result = request.app.state.learning.answer(
                user_id=body.user_id, question_id=body.question_id, rating=body.rating
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    @app.get("/api/study/plan")
    async def study_plan(request: Request, user_id: str = "local") -> dict:
        return request.app.state.learning.plan(user_id)

    @app.get("/api/study/activity")
    async def study_activity(
        request: Request,
        user_id: str = "local",
        days: int = Query(default=30, ge=1, le=60),
    ) -> dict:
        return {"days": request.app.state.learning.activity_series(user_id, days=days)}

    # -- 项目与会话（WorkBuddy 式分组） ----------------------------------------

    @app.post("/api/projects")
    async def create_project(request: Request, user_id: str = "local", name: str = Form(...)) -> dict:  # noqa: E501
        name = name.strip()[:64]
        if not name:
            raise HTTPException(status_code=400, detail="项目名不能为空")
        try:
            project_id = request.app.state.chat.create_project(
                user_id=user_id, name=name
            )
        except Exception as exc:  # noqa: BLE001 — UNIQUE 冲突 → 409 已存在
            if "UNIQUE" in str(exc):
                raise HTTPException(status_code=409, detail="同名项目已存在") from exc
            raise
        return {"id": project_id, "name": name}

    @app.get("/api/projects")
    async def list_projects(request: Request, user_id: str = "local") -> dict:
        return {"projects": request.app.state.chat.list_projects(user_id)}

    @app.put("/api/projects/{project_id}")
    async def rename_project(
        request: Request, project_id: int, user_id: str = "local", name: str = Form(...)
    ) -> dict:
        if not request.app.state.chat.rename_project(
            user_id, project_id, name.strip()[:64]
        ):
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"id": project_id, "name": name.strip()}

    @app.delete("/api/projects/{project_id}")
    async def delete_project(
        request: Request, project_id: int, user_id: str = "local"
    ) -> dict:
        if not request.app.state.chat.delete_project(user_id, project_id):
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"deleted": project_id}

    @app.get("/api/chats")
    async def list_chats(
        request: Request,
        user_id: str = "local",
        project_id: int | None = Query(default=None),
    ) -> dict:
        return {"chats": request.app.state.chat.list_sessions(user_id, project_id=project_id)}

    @app.get("/api/chats/{session_id}/messages")
    async def chat_messages(
        request: Request, session_id: int, user_id: str = "local"
    ) -> dict:
        return {
            "messages": request.app.state.chat.list_messages(user_id, session_id)
        }

    @app.put("/api/chats/{session_id}")
    async def update_chat(
        request: Request,
        session_id: int,
        user_id: str = "local",
        title: str | None = Form(default=None),
        project_id: int | None = Form(default=None),
    ) -> dict:
        updated = request.app.state.chat.update_session(
            user_id, session_id, title=(title or None), project_id=project_id, touch=True
        )
        if not updated:
            raise HTTPException(status_code=404, detail="会话不存在")
        return {"id": session_id}

    @app.delete("/api/chats/{session_id}")
    async def delete_chat(
        request: Request, session_id: int, user_id: str = "local"
    ) -> dict:
        if not request.app.state.chat.delete_session(user_id, session_id):
            raise HTTPException(status_code=404, detail="会话不存在")
        return {"deleted": session_id}

    @app.get("/api/memories")
    async def list_memories(
        request: Request, user_id: str = "local", project_id: int | None = Query(default=None)
    ) -> dict:
        # project_id 缺省 → 全部记忆；传了 → 只看该项目的（记忆按项目隔离）。
        return {
            "memories": request.app.state.learning.memories(
                user_id, project_id=str(project_id or "")
            )
        }

    @app.get("/api/usage")
    async def usage(request: Request, user_id: str = "local", days: int = 1) -> dict:
        since = time.time() - max(1, days) * 86400
        repository = request.app.state.usage
        return {
            "total_tokens": repository.total_since(user_id=user_id, since=since),
            "by_model": repository.summary(user_id=user_id, since=since),
            "by_day": repository.daily_series(user_id=user_id, days=7),
            "daily_token_budget": request.app.state.settings.daily_token_budget,
        }

    return app


app = create_app()
