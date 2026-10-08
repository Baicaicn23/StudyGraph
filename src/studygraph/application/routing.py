"""意图识别与子智能体路由（纯规则实现）。

一次学习回合先判断"学生想干什么"，再决定交给哪个子智能体——每个子智能体有
自己的角色提示词和**工具最小权限**（默认工具 + 黑名单）。规则是确定性的、零成本、
可单测；LLM 复核是后续里程碑的可选增强，不影响这里的契约。

权限按"读 / 写"分档：进度 agent 一个工具都不给（deny_all），练习 agent 只能读
（能检索、不能写），讲解 / 检索 / 闲聊可以读写。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CONCEPT_EXPLAIN = "concept_explain"
PRACTICE = "practice"
PROGRESS = "progress"
RETRIEVAL = "retrieval"
CALCULATION = "calculation"
SMALLTALK = "smalltalk"

# 匹配"数字 + 运算符 + 数字"，避免把"第 3-4 章"这类纯数字当成计算。
_MATH_RE = re.compile(r"\d+(?:\.\d+)?\s*[\+\-\*/×÷\^%]\s*\d")

_KEYWORDS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    (PRACTICE, 0.90, ("出题", "练习题", "练习一下", "考考我", "做题", "来几道", "刷题")),
    (
        RETRIEVAL,
        0.85,
        (
            "我的资料", "知识库", "我的笔记", "我上传", "文档里", "检索",
            "查一下资料", "出处", "讲义",
        ),
    ),
    (PROGRESS, 0.85, ("进度", "掌握度", "复习计划", "学到哪", "薄弱", "还剩多少", "学习报告")),
    (
        CONCEPT_EXPLAIN,
        0.80,
        ("讲解", "解释", "为什么", "什么是", "原理", "教我", "帮我理解", "证明", "推导"),
    ),
    (CALCULATION, 0.80, ("计算", "算一下", "算算", "等于几", "等于多少")),
)


def classify(text: str) -> tuple[str, float]:
    """把一句学生的话判成一个意图。返回 (意图, 置信度)。纯函数、确定性。"""

    content = (text or "").strip()
    if not content:
        return SMALLTALK, 0.5
    if _MATH_RE.search(content):
        return CALCULATION, 0.95
    for intent, confidence, keywords in _KEYWORDS:
        if any(keyword in content for keyword in keywords):
            return intent, confidence
    return SMALLTALK, 0.5


@dataclass(frozen=True)
class AgentProfile:
    agent: str
    system_prompt: str
    default_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    deny_all: bool = False


AGENT_PROFILES: dict[str, AgentProfile] = {
    "tutor": AgentProfile(
        agent="tutor",
        system_prompt=(
            "你是讲解型导师。先给直觉与结论，再讲原理，配一个具体例子；"
            "学生自己的资料里有的内容，优先检索资料再讲，并指出出处。"
        ),
        default_tools=("knowledge_search", "calculator", "save_note"),
    ),
    "practice": AgentProfile(
        agent="practice",
        system_prompt=(
            "你是出题教练。生成有梯度的练习题（记忆题 / 应用题 / 迁移题），"
            "每题写清作答要求；先让学习者作答，不要直接给答案。"
            "你可以检索学习者的资料来出题，但不要改动他的数据。"
        ),
        # 只读：能检索资料出题，写入工具进黑名单——"出题不改动数据"在执行层也成立。
        default_tools=("knowledge_search",),
        denied_tools=("save_note",),
    ),
    "progress": AgentProfile(
        agent="progress",
        system_prompt="你是学习进度助手。只依据已提供的档案与历史信息回答，不检索、不写入。",
        deny_all=True,
    ),
    "retriever": AgentProfile(
        agent="retriever",
        system_prompt=(
            "你是资料检索助手。调用检索工具找到学习者资料里的相关片段，"
            "据此回答，并逐条给出出处（哪个库、哪份资料）。"
        ),
        default_tools=("knowledge_search", "save_note"),
    ),
    "calculator": AgentProfile(
        agent="calculator",
        system_prompt=(
            "你是计算助手。调用计算器工具得到数值结果，再分步解释计算过程；"
            "不要心算，也不要检索资料。"
        ),
        default_tools=("calculator",),
        denied_tools=("knowledge_search",),
    ),
    "chat": AgentProfile(
        agent="chat",
        system_prompt="你是通用的学习陪伴助手，友好、简洁地回答，必要时追问以澄清需求。",
        default_tools=("knowledge_search", "calculator", "save_note"),
    ),
}

_INTENT_TO_AGENT = {
    CONCEPT_EXPLAIN: "tutor",
    PRACTICE: "practice",
    PROGRESS: "progress",
    RETRIEVAL: "retriever",
    CALCULATION: "calculator",
    SMALLTALK: "chat",
}


def profile_for_intent(intent: str) -> AgentProfile:
    return AGENT_PROFILES[_INTENT_TO_AGENT.get(intent, "chat")]


def profile_for_agent(agent: str | None) -> AgentProfile:
    return AGENT_PROFILES.get(agent or "chat", AGENT_PROFILES["chat"])


def allowed_tools(profile: AgentProfile, requested: list[str] | None = None) -> list[str]:
    """算出这个子智能体最终可用的工具名。

    规则：`deny_all` 一律清空；否则取"用户显式选择的工具（若有）否则默认集"，
    再统一减去黑名单。**黑名单优先于用户选择**，否则用户勾一下就能拿回写权限。
    """

    if profile.deny_all:
        return []
    base = list(requested) if requested else list(profile.default_tools)
    denied = set(profile.denied_tools)
    seen: list[str] = []
    for name in base:
        if name not in denied and name not in seen:
            seen.append(name)
    return seen


def is_tool_allowed(profile: AgentProfile, name: str) -> bool:
    """执行层权限判定：即使模型硬发一个被禁工具，也在这里被拦下。"""

    if profile.deny_all:
        return False
    return name not in profile.denied_tools
