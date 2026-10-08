"""trace 命令行：把一个会话读成一棵诊断树。

    studygraph-trace --thread <thread_id> [--db path]

例子：

    $ studygraph-trace --thread math
    回合 thread=math
    ├─ 用户消息： 我的笔记里怎么讲导数的？
    ├─ 意图：retrieval  →  retriever
    ├─ 工具：knowledge_search  [空]
    └─ 归因：retrieval
       ⚠ 检索返回空结果：模型没有资料可用
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ..application import tools
from ..application.graph import build_graph
from ..application.trace import diagnose, render
from ..config import get_settings
from ..infrastructure.embeddings import get_embedder
from ..infrastructure.knowledge import KnowledgeStore
from ..infrastructure.llm import build_chat_model


async def _trace(settings, thread: str) -> int:
    knowledge = KnowledgeStore(settings.database_path, embedder=get_embedder(settings))
    tools.configure(knowledge)
    model = build_chat_model(settings)
    async with AsyncSqliteSaver.from_conn_string(settings.database_path) as checkpointer:
        graph = build_graph(
            model=model,
            checkpointer=checkpointer,
            max_tool_rounds=settings.max_tool_rounds,
        )
        state = await graph.aget_state({"configurable": {"thread_id": thread}})
        messages = list(state.values.get("messages", []))
    if not messages:
        print(f"会话 {thread} 没有历史记录。")
        return 1
    diagnosis = diagnose(messages, dict(state.values))
    print(render(diagnosis, thread=thread))
    return 0 if diagnosis["attribution"] == "ok" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studygraph-trace", description="回合 trace 诊断")
    parser.add_argument("--thread", required=True, help="会话 id")
    parser.add_argument("--db", default=None, help="数据库路径（默认读环境变量）")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.db:
        settings = replace(settings, database_path=args.db)
    return asyncio.run(_trace(settings, args.thread))


if __name__ == "__main__":
    sys.exit(main())
