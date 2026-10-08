"""接口层：CLI。组合根，把基础设施注入应用层。

用法：

    uv run python -m studygraph.interfaces.cli "计算 7 * 9"
    uv run python -m studygraph.interfaces.cli "记住：我在准备月底的微积分测验" --yes
    uv run python -m studygraph.interfaces.cli "我的笔记里怎么讲导数的？" --thread math
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from ..application import tools
from ..application.graph import build_graph
from ..application.learning_service import LearningService
from ..config import Settings, get_settings
from ..infrastructure.embeddings import get_embedder
from ..infrastructure.knowledge import KnowledgeStore
from ..infrastructure.learning_repository import SqliteLearningRepository
from ..infrastructure.llm import build_chat_model


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="studygraph", description="StudyGraph CLI")
    parser.add_argument("message", nargs="*", help="本轮要说的话")
    parser.add_argument("--thread", default="local", help="会话 id（断点持久化用）")
    parser.add_argument("--user", default=None, help="用户标识")
    parser.add_argument("--yes", action="store_true", help="自动同意所有需要确认的操作")
    return parser.parse_args(argv)


async def _run(
    graph,
    text: str,
    *,
    thread: str,
    user_id: str,
    auto_approve: bool,
    memories: list[str] | None = None,
) -> None:
    config = {"configurable": {"thread_id": thread}}
    payload: object = {
        "messages": [HumanMessage(text)],
        "user_id": user_id,
        "memories": memories or [],
    }
    while True:
        interrupted = None
        async for mode, chunk in graph.astream(
            payload, config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                message, _meta = chunk
                if isinstance(message, (AIMessage, AIMessageChunk)) and message.content:
                    print(message.content, end="", flush=True)
            elif isinstance(chunk, dict) and "__interrupt__" in chunk:
                interrupted = chunk["__interrupt__"]
        print()

        if not interrupted:
            break

        request = interrupted[0].value
        print(
            f"[需要确认] 保存到「{request.get('library')}」：《{request.get('title')}》"
        )
        print(f"  预览：{request.get('preview', '')[:160]}")
        if auto_approve:
            approved = True
        else:
            answer = input("  确认保存？(y/N) ").strip().lower()
            approved = answer in ("y", "yes", "是")
        payload = Command(resume=approved)


async def _amain(settings: Settings, text: str, args: argparse.Namespace) -> None:
    knowledge = KnowledgeStore(settings.database_path, embedder=get_embedder(settings))
    repository = SqliteLearningRepository(settings.database_path)
    learning = LearningService(knowledge, repository)
    tools.configure(knowledge)
    model = build_chat_model(settings)
    user_id = args.user or settings.user_id
    learning.remember(user_id, text)
    async with AsyncSqliteSaver.from_conn_string(settings.database_path) as checkpointer:
        graph = build_graph(
            model=model,
            checkpointer=checkpointer,
            max_tool_rounds=settings.max_tool_rounds,
        )
        await _run(
            graph,
            text,
            thread=args.thread,
            user_id=user_id,
            auto_approve=args.yes,
            memories=learning.memories(user_id),
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    text = " ".join(args.message).strip()
    if not text:
        print(
            '请输入要发送的内容，例如：'
            'uv run python -m studygraph.interfaces.cli "计算 7 * 9"'
        )
        return 2
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(_amain(settings, text, args))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
