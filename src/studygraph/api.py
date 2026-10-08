"""HTTP 接口层：把 LangGraph 图通过 SSE 暴露给前端。

- `POST /api/chat/stream`：发起一回合，流式返回 `token` / `interrupt` / `done` 事件。
- `POST /api/chat/resume`：对上一次 `interrupt`（HITL）给出确认，继续流式返回。
- `GET  /api/knowledge/libraries`：列出学科知识库。
- `POST /api/knowledge/notes`：写入一条笔记（演示/播种用）。

SSE 事件协议（每行一个事件，`data` 为 JSON）：

    event: token      data: {"content": "..."}
    event: interrupt  data: {"action": "save_note", "library": "...", ...}
    event: done       data: {}
    event: error      data: {"message": "..."}

启动：`uv run uvicorn studygraph.api:app --port 8011 --reload`
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from . import tools
from .config import Settings, get_settings
from .embeddings import get_embedder
from .graph import build_graph
from .knowledge import KnowledgeStore
from .providers import build_chat_model


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


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_stream(graph, payload: object, config: dict):
    try:
        async for mode, chunk in graph.astream(
            payload, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                message, _meta = chunk
                if isinstance(message, (AIMessage, AIMessageChunk)) and message.content:
                    yield _sse("token", {"content": message.content})
            elif isinstance(chunk, dict) and "__interrupt__" in chunk:
                yield _sse("interrupt", chunk["__interrupt__"][0].value)
        yield _sse("done", {})
    except Exception as exc:  # noqa: BLE001 - 把失败作为事件返回，而不是断连
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved = settings or get_settings()
        store = KnowledgeStore(resolved.database_path, embedder=get_embedder(resolved))
        tools.configure(store)
        model = build_chat_model(resolved)
        async with AsyncSqliteSaver.from_conn_string(resolved.database_path) as checkpointer:
            app.state.settings = resolved
            app.state.store = store
            app.state.graph = build_graph(
                model=model,
                checkpointer=checkpointer,
                max_tool_rounds=resolved.max_tool_rounds,
            )
            yield

    app = FastAPI(title="StudyGraph API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health(request: Request) -> dict:
        return {
            "status": "ok",
            "provider": request.app.state.settings.llm_provider,
        }

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

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
        config = {"configurable": {"thread_id": body.thread_id}}
        payload: dict = {
            "messages": [HumanMessage(body.message)],
            "user_id": body.user_id,
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
            _run_stream(
                request.app.state.graph, Command(resume=body.approved), config
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
