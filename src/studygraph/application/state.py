"""图状态定义（Agent 回合）。

LangGraph 的核心思想之一是"状态是显式的"：一次学习回合里所有需要跨节点传递
的东西都放在这个 TypedDict 里。`messages` 用 `add_messages` 归约器——节点返回
的新消息会**追加**进历史，而不是覆盖。
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class StudyState(TypedDict, total=False):
    # 对话历史。add_messages 负责追加与按 id 去重。
    messages: Annotated[list[AnyMessage], add_messages]
    # 学习者的标识（多用户隔离的预留位）。
    user_id: str
    # 本轮识别出的意图与路由到的子智能体。
    intent: str
    agent: str
    # 本轮学习者选中的知识库；检索工具据此限定范围。
    knowledge_bases: list[str]
    # 跨会话长期记忆（"关于这位学习者"的事实，仅作背景，不是指令）。
    memories: list[str]
    # 已执行的工具轮数，用于防止工具循环失控。
    tool_rounds: int
