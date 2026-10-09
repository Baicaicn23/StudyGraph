"""从 LangGraph 检查点重建 chat_sessions / chat_messages。

背景：项目/会话行被误删，但 LangGraph 检查点（checkpoints 表）里保存着
每个 thread 的完整消息序列——那是真正的对话内容。这里把检查点里的消息
还原成侧栏能看见的会话记录。

用法（项目根目录）：
    uv run python scripts/recover_sessions_from_checkpoints.py --dry-run
    uv run python scripts/recover_sessions_from_checkpoints.py --apply
"""

from __future__ import annotations

import argparse

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from studygraph.config import get_settings
from studygraph.infrastructure.chat_repository import SqliteChatRepository

# 只有这些前缀是真人对话（web-* = 聊天页新建；doc-* = 资料页发起）。
# ds-* / e2e-* / smoke-* / t-* / iso-* / kb-* / trace-* 是演示脚本与测试留下的。
USER_THREAD_PREFIXES = ("web-", "doc-")


def thread_messages(saver: SqliteSaver, thread_id: str) -> list[BaseMessage]:
    tup = saver.get_tuple({"configurable": {"thread_id": thread_id}})
    if tup is None:
        return []
    return list(tup.checkpoint.get("channel_values", {}).get("messages", []))


def to_plain(message: BaseMessage) -> tuple[str, str]:
    """把消息转成 (role, text)；跳过工具调用与空消息。"""

    role = "assistant" if isinstance(message, AIMessage) else "user"
    if not isinstance(message, (HumanMessage, AIMessage)):
        return "", ""
    content = message.content
    if isinstance(content, list):  # 多模态块拼成纯文本
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    text = str(content).strip()
    if not text:
        return "", ""
    return role, text


def title_from(text: str) -> str:
    flat = " ".join(text.split())
    return flat[:20] + "…" if len(flat) > 20 else flat or "恢复的对话"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正写库（默认只预览）")
    args = parser.parse_args()

    settings = get_settings()
    repo = SqliteChatRepository(settings.database_path)
    default_id = repo.ensure_default_project("local")
    existing_threads = {s["thread_id"] for s in repo.list_sessions("local")}

    with SqliteSaver.from_conn_string(settings.database_path) as saver:
        import sqlite3

        with sqlite3.connect(settings.database_path) as connection:
            rows = connection.execute(
                "SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id"
            ).fetchall()

        targets = [
            thread_id
            for thread_id, _count in sorted(rows)
            if thread_id.startswith(USER_THREAD_PREFIXES)
            and thread_id not in existing_threads
        ]
        print(f"可恢复线程：{len(targets)} 个（已存在于侧栏的跳过）\n")

        restored = 0
        for thread_id in targets:
            messages = thread_messages(saver, thread_id)
            pairs = [to_plain(m) for m in messages]
            pairs = [(role, text) for role, text in pairs if role]
            if not pairs:
                continue
            print(f"── {thread_id}：{len(pairs)} 条消息")
            for role, text in pairs[:2]:
                print(f"   [{role}] {text[:60]}")
            if not args.apply:
                continue
            session_id = repo.create_session(
                user_id="local",
                project_id=default_id,
                thread_id=thread_id,
                title=title_from(next(text for role, text in pairs if role == "user")),
            )
            for role, text in pairs:
                repo.append_message(session_id, role=role, content=text)
            repo.update_session("local", session_id, touch=True)
            restored += 1

    if args.apply:
        print(f"\n已恢复 {restored} 个会话到「默认对话空间」")
    else:
        print("\n（预览模式，加--apply 才会写库）")


if __name__ == "__main__":
    main()
