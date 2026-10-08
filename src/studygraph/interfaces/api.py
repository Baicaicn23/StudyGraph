"""接口层：HTTP。这里是**组合根**——把基础设施实现注入应用层服务与图。

启动：`uv run uvicorn studygraph.interfaces.api:app --port 8011 --reload`

SSE 事件协议（每行一个事件，`data` 为 JSON）：

    event: token      data: {"content": "..."}
    event: interrupt  data: {"action": "save_note", "library": "...", ...}
    event: done       data: {}
    event: error      data: {"message": "..."}
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from dataclasses import replace

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..application import tools
from ..application.graph import build_graph
from ..application.guardrails import screen_input, screen_output
from ..application.learning_service import LearningService
from ..config import Settings, get_settings, parse_mcp_servers
from ..domain.errors import LearningError
from ..infrastructure.embeddings import get_embedder
from ..infrastructure.extract import ExtractError, extract_text
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


class ResumeRequest(BaseModel):
    thread_id: str = Field(default="web", max_length=64)
    approved: bool = False


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


class AnswerRequest(BaseModel):
    user_id: str = Field(default="local", max_length=64)
    question_id: int
    rating: str = Field(min_length=1, max_length=16)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_stream(graph, payload: object, config: dict):
    interrupted = False
    try:
        async for mode, chunk in graph.astream(
            payload, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                message, _meta = chunk
                if isinstance(message, (AIMessage, AIMessageChunk)) and message.content:
                    yield _sse("token", {"content": message.content})
            elif isinstance(chunk, dict) and "__interrupt__" in chunk:
                interrupted = True
                yield _sse("interrupt", chunk["__interrupt__"][0].value)
        if not interrupted:
            warning = await _screen_last_answer(graph, config)
            if warning:
                yield _sse("guard", {"reason": warning})
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
        learning = LearningService(knowledge, repository)
        tools.configure(knowledge)
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
        try:
            text = extract_text(file.filename or "", data)
        except ExtractError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not text.strip():
            raise HTTPException(status_code=400, detail="文件里没有可提取的文本")
        title = (file.filename or "上传资料").strip()
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
        learning.remember(body.user_id, body.message)
        payload: dict = {
            "messages": [HumanMessage(body.message)],
            "user_id": body.user_id,
            "memories": learning.memories(body.user_id),
        }
        if body.knowledge_bases:
            payload["knowledge_bases"] = body.knowledge_bases
        return StreamingResponse(
            _run_stream(request.app.state.graph, payload, config),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/chat/resume")
    async def chat_resume(body: ResumeRequest, request: Request) -> StreamingResponse:
        config = {"configurable": {"thread_id": body.thread_id}}
        return StreamingResponse(
            _run_stream(request.app.state.graph, Command(resume=body.approved), config),
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

    @app.get("/api/memories")
    async def list_memories(request: Request, user_id: str = "local") -> dict:
        return {"memories": request.app.state.learning.memories(user_id)}

    @app.get("/api/usage")
    async def usage(request: Request, user_id: str = "local", days: int = 1) -> dict:
        since = time.time() - max(1, days) * 86400
        repository = request.app.state.usage
        return {
            "total_tokens": repository.total_since(user_id=user_id, since=since),
            "by_model": repository.summary(user_id=user_id, since=since),
        }

    return app


app = create_app()
