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

import asyncio
import json
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..application import tools
from ..application.graph import build_graph
from ..application.guardrails import screen_input, screen_output
from ..application.image_notes import ImageNoteError, image_to_markdown
from ..application.learning_service import LearningService
from ..application.schedule_service import ScheduleService
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
from ..infrastructure.schedule_repository import SqliteScheduleRepository
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
    # 本条消息携带的聊天附件（先经 /api/chat/attachments 上传拿 id）
    attachment_ids: list[int] = Field(default_factory=list)


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


class DocumentUpdateRequest(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200000)


class LibraryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class FeedbackRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    library: str = Field(default="", max_length=64)
    question: str = Field(default="", max_length=4000)
    note: str = Field(min_length=1, max_length=2000)
    # 错误类型（可选）：concept / step / condition / calc / wording
    kind: str = Field(default="", max_length=16)


class GenerateRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    source: str = Field(default="knowledge_base", max_length=32)
    library: str = Field(default="", max_length=64)
    count: int = Field(default=3, ge=1, le=10)
    # 难度：basic / apply / transfer / auto（auto 按该学科掌握度自动分档）
    difficulty: str = Field(default="auto", max_length=16)
    # 指定用哪几条错题出变式题（给了就忽略 source/library 的筛选）
    mistake_ids: list[int] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    question_id: int
    rating: str = Field(min_length=1, max_length=16)


class ScheduleTaskRequest(BaseModel):
    """新建/更新日程任务。date 缺省 = 进收件箱。"""

    user_id: str = Field(default="local", max_length=64)
    title: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=2000)
    date: str | None = Field(default=None, max_length=10)
    start_minutes: int | None = Field(default=None, ge=0, le=1439)
    duration_minutes: int = Field(default=30, ge=5, le=600)


class ScheduleUpdateRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    title: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    date: str | None = Field(default=None, max_length=10)
    start_minutes: int | None = Field(default=None, ge=0, le=1439)
    duration_minutes: int | None = Field(default=None, ge=5, le=600)
    done: bool | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _attachment_dir(settings: Settings) -> Path:
    """附件落盘目录：与数据库同级的 attachments/。"""

    return Path(settings.database_path).parent / "attachments"


_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


# 工具名 → 用户能看懂的状态文案（前端状态行直接展示）。
_TOOL_STATUS = {
    "knowledge_search": "检索知识库",
    "mistake_search": "查阅错题记录",
    "save_note": "整理笔记",
}
_NODE_STATUS = {"route": "理解问题", "plan": "制定学习计划"}

# 意图 → 中文标签（思考过程里告诉用户「它在判断什么」）。键取自
# application.routing 的常量：concept_explain / practice / progress /
# retrieval / calculation / smalltalk。
_INTENT_LABEL = {
    "concept_explain": "讲解知识点",
    "practice": "出练习题",
    "progress": "查看学习进度",
    "retrieval": "检索学习资料",
    "calculation": "计算求解",
    "smalltalk": "日常问答",
}


def _tool_status(name: str) -> str:
    return _TOOL_STATUS.get(name, f"调用工具 {name}")


def _summarize_tool_args(name: str, args: dict) -> str:
    """工具参数摘要：让「调用了什么」在过程流里一目了然。"""

    def text(key: str, limit: int = 40) -> str:
        value = args.get(key)
        if not isinstance(value, str) or not value.strip():
            return ""
        value = value.strip().replace("\n", " ")
        return value if len(value) <= limit else f"{value[:limit]}…"

    if name == "knowledge_search":
        return " · ".join(p for p in (text("library", 16), text("query")) if p)
    if name == "mistake_search":
        return " · ".join(p for p in (text("library", 16), text("question")) if p)
    if name == "save_note":
        return " · ".join(p for p in (text("library", 16), text("title")) if p)
    return " · ".join(
        f"{k}={v}" for k, v in list(args.items())[:2] if isinstance(v, (str, int))
    )[:80]


def _summarize_tool_result(name: str, content: str, *, failed: bool) -> str:
    """工具结果摘要：一句话说清"拿到了什么"（不把原始长文倒进过程流）。"""

    if failed:
        return content[:120].replace("\n", " ")
    if name == "knowledge_search":
        hits = content.count("【")
        if hits == 0:
            return "没有命中相关片段"
        first = content.split("【", 1)[1].split("】", 1)[0].strip()
        return f"命中 {hits} 篇 · 首篇：{first}"
    if name == "mistake_search":
        if "还没有记录" in content or "没有" in content[:20]:
            return "没有相关误区记录"
        hits = max(content.count("\n- "), content.count("- "), 1)
        return f"命中 {hits} 条误区"
    if name == "save_note":
        return content[:80].replace("\n", " ")
    return content[:100].replace("\n", " ")


def _steps_from_update(chunk: dict) -> list[dict]:
    """把一次节点更新翻译成「过程步骤」，供前端渲染 WorkBuddy 式思考流。

    节点返回的都是结构化状态（意图 / 计划 / 工具调用 / 工具结果），
    这里只做翻译，不掺任何生成内容。
    """

    node = next(iter(chunk))
    update = chunk[node]
    if not isinstance(update, dict):
        return []

    if node == "route":
        intent = str(update.get("intent", ""))
        agent = str(update.get("agent", ""))
        label = _INTENT_LABEL.get(intent, "综合问答")
        suffix = f"，已切换到「{agent}」模式。" if agent else "。"
        return [
            {
                "kind": "thinking",
                "title": "理解问题",
                "detail": f"判断为「{label}」{suffix}",
            }
        ]

    if node == "plan":
        plan = update.get("plan") or []
        if not plan:
            return []
        lines = "\n".join(f"{i}. {step}" for i, step in enumerate(plan, 1))
        return [{"kind": "thinking", "title": "制定学习计划", "detail": lines}]

    if node == "agent":
        steps: list[dict] = []
        for message in update.get("messages", []):
            for call in getattr(message, "tool_calls", None) or []:
                name = call.get("name", "")
                args = call.get("args") or {}
                steps.append(
                    {
                        "kind": "tool",
                        "title": _tool_status(name),
                        "detail": _summarize_tool_args(name, args),
                    }
                )
        return steps

    if node == "tools":
        steps = []
        for message in update.get("messages", []):
            name = getattr(message, "name", "") or "工具"
            content = str(getattr(message, "content", ""))
            failed = content.startswith("[tool_error") or content.startswith(
                ("[tool_not_allowed", "[unknown_tool")
            )
            steps.append(
                {
                    "kind": "tool",
                    "title": f"{_tool_status(name)} · {'失败' if failed else '完成'}",
                    "detail": _summarize_tool_result(name, content, failed=failed),
                }
            )
        return steps

    return []


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
    attachment_meta: list[dict] | None = None,
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
    steps: list[dict] = []
    # HITL 中断后续写：把中断前那条助手消息取回来，文字与步骤都接在同一条上，
    # 否则历史回放只看到"确认之后"的半截过程（用户反馈"不知道智能体去干嘛了"）。
    resume_message_id: int | None = None
    if not persist_user and session is not None and chat is not None:
        try:
            previous = chat.last_assistant_message(user_id, session["id"])
        except Exception:  # noqa: BLE001 — 读不到就当新消息
            previous = None
        if previous is not None:
            resume_message_id = int(previous["id"])
            if previous["content"]:
                answer_parts.append(str(previous["content"]))
            try:
                existing_steps = json.loads(previous["steps"] or "[]")
            except (TypeError, ValueError):
                existing_steps = []
            if isinstance(existing_steps, list):
                steps.extend(existing_steps)
    if session is not None and chat is not None:
        try:
            if persist_user:
                chat.append_message(
                    session["id"],
                    role="user",
                    content=user_message,
                    attachments=json.dumps(
                        attachment_meta or [], ensure_ascii=False
                    ),
                )
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
                new_steps = _steps_from_update(chunk)
                if new_steps:
                    steps.extend(new_steps)
                    for step in new_steps:
                        yield _sse("step", step)
                status = _status_from_update(chunk)
                if status:
                    yield _sse("status", {"label": status})
        if not interrupted:
            # 被中断的半截回答不做过护栏复核（还没说完）；完整回合才复核
            warning = await _screen_last_answer(graph, config)
            if warning:
                yield _sse("guard", {"reason": warning})
        if session is not None and chat is not None:
            answer = "".join(answer_parts).strip()
            payload_steps = json.dumps(steps, ensure_ascii=False)
            if resume_message_id is not None:
                # 续写：把新的文字与步骤并回中断前那条消息
                chat.update_message(
                    user_id,
                    resume_message_id,
                    content=answer,
                    steps=payload_steps,
                )
            elif answer or steps:
                chat.append_message(
                    session["id"],
                    role="assistant",
                    content=answer,
                    steps=payload_steps,
                )
            if session["title"] in ("", "新对话") and user_message:
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
        schedule = ScheduleService(SqliteScheduleRepository(resolved.database_path))
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
            app.state.schedule = schedule
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

    @app.post("/api/knowledge/libraries")
    async def create_library(body: LibraryRequest, request: Request) -> dict:
        """新建知识库（只建空库；重名视为已存在，幂等）。"""

        name = body.name.strip()
        try:
            request.app.state.store.ensure_library(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"name": name}

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

    @app.put("/api/knowledge/document")
    async def update_document(body: DocumentUpdateRequest, request: Request) -> dict:
        """编辑资料：标题/正文更新并重建检索索引（切块 + 向量）。"""

        try:
            updated = request.app.state.store.update_document(
                body.id, title=body.title, content=body.content
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="资料不存在")
        return {"id": body.id, "title": body.title}

    @app.delete("/api/knowledge/document")
    async def delete_document(request: Request, id: int = Query(ge=1)) -> dict:
        if not request.app.state.store.delete_document(id):
            raise HTTPException(status_code=404, detail="资料不存在")
        return {"deleted": id}

    @app.delete("/api/knowledge/library")
    async def delete_library(request: Request, name: str = Query(min_length=1, max_length=64)) -> dict:  # noqa: E501
        """删除整个学科库：库里所有资料与检索索引一起删。"""

        if not request.app.state.store.delete_library(name):
            raise HTTPException(status_code=404, detail="知识库不存在")
        return {"deleted": name}

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

    @app.post("/api/chat/attachments")
    async def upload_chat_attachment(
        request: Request,
        file: UploadFile = File(...),  # noqa: B008 — FastAPI 的标准依赖注入写法
        session_id: int | None = Form(default=None),
        project_id: int | None = Form(default=None),
        user_id: str = Form(default="local"),
    ) -> dict:
        """聊天附件上传：抽取文本（图片走视觉转写）存库，返回附件 id。

        project_id 记录附件归属：消息发出前session 可能还不存在，但附件
        已经属于某个项目，删项目时才能一起清掉。
        """

        data = await file.read()
        if len(data) > request.app.state.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="文件太大（上限 5MB）")
        filename = (file.filename or "附件").strip()

        if session_id is not None and request.app.state.chat.get_session(
            user_id, session_id
        ) is None:
            raise HTTPException(status_code=404, detail="会话不存在")

        if is_image(filename):
            model = request.app.state.model
            # Mock 模型不支持识图（真实模型如 deepseek-flash 已实测可转写图片）
            if getattr(model, "_llm_type", "") == "study-mock":
                raise HTTPException(
                    status_code=400,
                    detail="当前是 Mock 模式，不支持识别图片；"
                    "请在 .env 里配置真实模型后再传图",
                )
            try:
                text = await image_to_markdown(model, filename, data)
            except ImageNoteError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            kind = "image"
        else:
            try:
                text = extract_text(filename, data)
            except ExtractError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            kind = "file"
        if not text.strip():
            raise HTTPException(status_code=400, detail="文件里没有可提取的文本")

        attachment_id = request.app.state.chat.add_attachment(
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            kind=kind,
            content=text,
            project_id=str(
                project_id
                if project_id is not None
                else request.app.state.chat.ensure_default_project(user_id)
            ),
        )
        # 原文件落盘，供前端「点击预览」用（只存图片，PDF 等暂不重复存）
        if kind == "image":
            suffix = Path(filename).suffix.lower() or ".png"
            if suffix not in _IMAGE_MIME_BY_SUFFIX:
                suffix = ".png"
            directory = _attachment_dir(request.app.state.settings)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"{attachment_id}{suffix}"
            target.write_bytes(data)
            request.app.state.chat.set_attachment_path(
                user_id, attachment_id, str(target)
            )
        return {"id": attachment_id, "filename": filename, "kind": kind, "chars": len(text)}

    @app.get("/api/chat/attachments/{attachment_id}/raw")
    async def chat_attachment_raw(
        request: Request, attachment_id: int, user_id: str = "local"
    ) -> FileResponse:
        """附件原文件（图片预览），带归属校验。"""

        record = request.app.state.chat.get_attachment(user_id, attachment_id)
        if record is None or not record["storage_path"]:
            raise HTTPException(status_code=404, detail="附件不存在")
        path = Path(record["storage_path"])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="附件文件已丢失")
        media_type = _IMAGE_MIME_BY_SUFFIX.get(
            path.suffix.lower(), "application/octet-stream"
        )
        return FileResponse(path, media_type=media_type)

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
        chat = request.app.state.chat
        # 项目兜底：没带project_id 时归入「默认对话空间」。
        # 否则记忆会落进project_id="" 的黑洞桶——按项目查询时谁都读不到，
        # 表现为「明明让它记住了，它却忘了」。
        project_id = (
            body.project_id
            if body.project_id is not None
            else chat.ensure_default_project(body.user_id)
        )
        project_key = str(project_id)
        learning.remember(body.user_id, body.message, project_id=project_key)

        # 聊天附件：把抽取出的文本拼进本轮消息，模型就能「看到」PDF/图片内容。
        attachment_meta: list[dict] = []
        composed = body.message
        if body.attachment_ids:
            if len(body.attachment_ids) > 6:
                raise HTTPException(status_code=400, detail="一条消息最多带 6 个附件")
            attachments = request.app.state.chat.get_attachments(
                body.user_id, body.attachment_ids
            )
            if attachments:
                sections = [body.message]
                attachment_meta = [
                    {
                        "id": item["id"],
                        "name": item["filename"],
                        "kind": item["kind"],
                    }
                    for item in attachments
                ]
                for item in attachments:
                    # 单附件最多取前 8000 字，防止长文档撑爆上下文
                    sections.append(
                        f"---\n[附件 {item['filename']}]\n{item['content'][:8000]}"
                    )
                composed = "\n\n".join(sections)

        payload: dict = {
            "messages": [HumanMessage(composed)],
            "user_id": body.user_id,
            "memories": [
                m["content"]
                for m in learning.memories(body.user_id, project_id=project_key)
            ],
            # 掌握度快照：system prompt 据此调整讲解深度（贴合学生水平）。
            "progress": learning.progress(body.user_id),
        }
        if body.knowledge_bases:
            payload["knowledge_bases"] = body.knowledge_bases

        # 自动保存：没有 session_id 就新建会话（标题先占位，回复完后自动起名）。
        session = None
        if body.session_id is not None:
            session = chat.get_session(body.user_id, body.session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="会话不存在")
        else:
            session_id = chat.create_session(
                user_id=body.user_id,
                project_id=project_id,
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
                attachment_meta=attachment_meta or None,
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
        try:
            feedback_id = request.app.state.learning.add_feedback(
                user_id=body.user_id,
                library=body.library,
                question=body.question,
                note=body.note,
                kind=body.kind,
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": feedback_id}

    @app.get("/api/feedback")
    async def list_feedback(request: Request, user_id: str = "local") -> dict:
        return {"feedback": request.app.state.learning.list_feedback(user_id)}

    @app.delete("/api/feedback/{feedback_id}")
    async def delete_feedback(
        request: Request, feedback_id: int, user_id: str = "local"
    ) -> dict:
        if not request.app.state.learning.delete_feedback(user_id, feedback_id):
            raise HTTPException(status_code=404, detail="误区记录不存在")
        return {"deleted": feedback_id}

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
                mistake_ids=body.mistake_ids,
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"questions": questions}

    @app.post("/api/practice/generate/stream")
    async def generate_practice_stream(
        body: GenerateRequest, request: Request
    ) -> StreamingResponse:
        """流式出题：每出一题推一帧 progress，最后推 done（questions 全量）。"""

        async def _stream() -> StreamingResponse:  # type: ignore[return]
            events: asyncio.Queue[dict | None] = asyncio.Queue()

            async def _run() -> None:
                try:
                    questions = await request.app.state.learning.generate(
                        user_id=body.user_id,
                        source=body.source,
                        library=body.library,
                        count=body.count,
                        model=request.app.state.model,
                        difficulty=body.difficulty,
                        mistake_ids=body.mistake_ids,
                        on_progress=lambda info: events.put_nowait(
                            {"type": "progress", **info}
                        ),
                    )
                    await events.put({"type": "done", "questions": questions})
                except LearningError as exc:
                    await events.put({"type": "error", "message": str(exc)})
                except Exception as exc:  # noqa: BLE001 — 流内兜底，不让任务静默死
                    await events.put(
                        {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
                    )
                finally:
                    await events.put(None)

            task = asyncio.create_task(_run())
            while True:
                event = await events.get()
                if event is None:
                    break
                yield _sse(str(event.pop("type")), event)
            await task

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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

    @app.delete("/api/practice/{question_id}")
    async def delete_practice(
        request: Request, question_id: int, user_id: str = "local"
    ) -> dict:
        if not request.app.state.learning.delete_question(user_id, question_id):
            raise HTTPException(status_code=404, detail="练习题不存在")
        return {"deleted": question_id}

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

    # -- 日程（时间轴 + 收件箱） ------------------------------------------------

    @app.get("/api/schedule")
    async def schedule_day(
        request: Request,
        user_id: str = "local",
        date: str = Query(min_length=10, max_length=10),
    ) -> dict:
        """某天时间轴：任务列表 + 收件箱计数（页面一次拿全）。"""

        try:
            return request.app.state.schedule.day_view(user_id, date)
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/schedule/inbox")
    async def schedule_inbox(request: Request, user_id: str = "local") -> dict:
        return {"tasks": request.app.state.schedule.inbox(user_id)}

    @app.get("/api/schedule/week")
    async def schedule_week(
        request: Request,
        user_id: str = "local",
        date: str = Query(min_length=10, max_length=10),
    ) -> dict:
        """周条密度：date 所在周（周日开头）每天 排期数/完成数。"""

        try:
            return request.app.state.schedule.week(user_id, date)
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/schedule/tasks")
    async def create_schedule_task(body: ScheduleTaskRequest, request: Request) -> dict:
        try:
            task = request.app.state.schedule.create(
                user_id=body.user_id,
                title=body.title,
                note=body.note,
                date=body.date,
                start_minutes=body.start_minutes,
                duration_minutes=body.duration_minutes,
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"task": task}

    @app.put("/api/schedule/tasks/{task_id}")
    async def update_schedule_task(
        task_id: int, body: ScheduleUpdateRequest, request: Request
    ) -> dict:
        try:
            task = request.app.state.schedule.update(
                user_id=body.user_id,
                task_id=task_id,
                title=body.title,
                note=body.note,
                date=body.date,
                start_minutes=body.start_minutes,
                duration_minutes=body.duration_minutes,
                done=body.done,
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"task": task}

    @app.post("/api/schedule/tasks/{task_id}/arrange")
    async def arrange_schedule_task(
        task_id: int,
        request: Request,
        user_id: str = "local",
        date: str | None = Query(default=None, min_length=10, max_length=10),
    ) -> dict:
        """一键安排：落到目标日（缺省今天）的第一个空档。"""

        try:
            task = request.app.state.schedule.arrange(
                user_id=user_id, task_id=task_id, date=date
            )
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"task": task}

    @app.post("/api/schedule/tasks/{task_id}/unarrange")
    async def unarrange_schedule_task(
        task_id: int, request: Request, user_id: str = "local"
    ) -> dict:
        """退回收件箱（清日期与开始时间）。"""

        try:
            task = request.app.state.schedule.unarrange(user_id=user_id, task_id=task_id)
        except LearningError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"task": task}

    @app.delete("/api/schedule/tasks/{task_id}")
    async def delete_schedule_task(
        task_id: int, request: Request, user_id: str = "local"
    ) -> dict:
        if not request.app.state.schedule.delete(user_id=user_id, task_id=task_id):
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"deleted": task_id}

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
        chat = request.app.state.chat
        # 首次访问自动建「默认对话空间」，并把历史无主会话归入其中
        chat.ensure_default_project(user_id)
        return {"projects": chat.list_projects(user_id)}

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
        """删除项目：项目内的会话、消息、附件（含磁盘上的图片）一起清空。"""

        chat = request.app.state.chat
        project = chat.get_project(user_id, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        if project.get("is_default"):
            raise HTTPException(status_code=400, detail="默认对话空间不能删除")

        session_ids = [
            session["id"]
            for session in chat.list_sessions(user_id, project_id=project_id)
        ]
        attachment_paths = chat.list_project_attachment_paths(user_id, project_id)

        if not chat.delete_project(user_id, project_id):
            raise HTTPException(status_code=404, detail="项目不存在")

        # 磁盘上的附件图片一并清理（失败不影响删除结果）
        for raw_path in attachment_paths:
            try:
                Path(raw_path).unlink(missing_ok=True)
            except OSError:  # noqa: PERF203 — 逐个尽力清理即可
                pass
        return {"deleted": project_id, "sessions": len(session_ids)}

    @app.get("/api/chats")
    async def list_chats(
        request: Request,
        user_id: str = "local",
        project_id: int | None = Query(default=None),
    ) -> dict:
        return {"chats": request.app.state.chat.list_sessions(user_id, project_id=project_id)}

    @app.get("/api/chat/activity")
    async def chat_activity(
        request: Request,
        user_id: str = "local",
        days: int = Query(default=84, ge=7, le=366),
    ) -> dict:
        """近 N 天提问频率（GitHub 式热力图）：按天统计用户消息数。"""

        return {
            "days": request.app.state.chat.ask_activity(user_id, days=days)
        }

    @app.get("/api/chats/{session_id}/messages")
    async def chat_messages(
        request: Request, session_id: int, user_id: str = "local"
    ) -> dict:
        messages = request.app.state.chat.list_messages(user_id, session_id)
        for item in messages:
            # 附件名/过程步骤落库时是 JSON 字符串，回放时还原成列表
            try:
                item["attachments"] = json.loads(item.get("attachments") or "[]")
            except (TypeError, ValueError):
                item["attachments"] = []
            try:
                item["steps"] = json.loads(item.get("steps") or "[]")
            except (TypeError, ValueError):
                item["steps"] = []
        return {"messages": messages}

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

    @app.delete("/api/memories/{memory_id}")
    async def delete_memory(
        request: Request, memory_id: int, user_id: str = "local"
    ) -> dict:
        if not request.app.state.learning.delete_memory(user_id, memory_id):
            raise HTTPException(status_code=404, detail="记忆不存在")
        return {"deleted": memory_id}

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
