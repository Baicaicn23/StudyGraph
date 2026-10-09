"""意图识别与子智能体路由（纯规则实现）。

一次学习回合先判断"学生想干什么"，再决定交给哪个子智能体——每个子智能体有
自己的角色提示词和**工具最小权限**（默认工具 + 黑名单 + MCP 授权策略）。规则
是确定性的、零成本、可单测；LLM 复核是后续里程碑的可选增强，不影响这里的契约。

权限按"读 / 写"分档：进度 agent 一个工具都不给（deny_all），练习 agent 只能读
（能检索、不能写），讲解 / 检索 / 闲聊可以读写；MCP 外部工具默认对所有人关闭，
只有显式 `mcp_enabled=True` 的子智能体才能拿到。

教学人格的总纲（`TEACHING_CHARTER`，三条红线）由 `graph.build_system_prompt`
拼进每个子智能体的系统提示词——所有角色共享同一套"私教"底线。
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
        (
            "讲解", "解释", "为什么", "什么是", "原理", "教我", "帮我理解", "证明", "推导",
            "错题", "误区", "易错", "我哪里错", "又错了", "归因",
        ),
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
    # 工具最小权限：MCP 外部工具**默认不下发**，只有显式授权的子智能体才能看到
    # 和执行。否则每个非 deny_all 的 agent 都能拿到外部写工具（曾导致 calculator
    # 拿到 mcp_filesystem_write 的权限泄漏）。
    mcp_enabled: bool = False


# 教学人格的总纲（三条红线），所有子智能体共用——它决定这个 Agent 是"私教"
# 而不是"答题机器"：
# 1. 个人数据优先：学生知识库/错题本里有的，绝不泛泛用通用知识回答；
#    没有的先说明"你的笔记里还没沉淀这部分"，再补充讲解并引导沉淀。
# 2. 引导优先于告知：默认先给思路提示、分步引导，而不是一次性甩完整解答。
# 3. 贴合掌握水平：讲解深度、术语密度、例子难度都要看学生的掌握度数据。
TEACHING_CHARTER = (
    "【教学总纲——三条红线，必须遵守】\n"
    "1. 个人数据优先：能从学生的知识库、错题本里找到的内容，"
    "优先检索后再回答，"
    "并明确标注出处（哪个库、哪份笔记）；学生资料里没有的，先说一句"
    "「这部分你的笔记里还没沉淀」，再做通用讲解，最后建议学生把新学的内容沉淀进知识库。\n"
    "2. 引导优先于告知：学生问「怎么做/为什么」时，不要直接给完整答案。先给一个"
    "思路提示或拆解后的第一个小问题，等学生回应后再推进下一步；学生卡住了就换"
    "一种提示方式，连续两次卡住或学生明确要求答案时才给出完整解答。"
    "学生只要答对一步就具体地肯定，再抛出下一步。\n"
    "3. 贴合掌握水平：下方会给出学生各学科的掌握度。掌握度低（<60%）的学科"
    "多用生活类比、少用术语、讲基础；掌握度高（>=80%）的可以讲本质、讲拓展，"
    "并额外抛一个进阶思考题。\n"
    "【语气与禁忌】平和、耐心、鼓励式；多说「我们试试」「你想想看」，"
    "不说「你应该/你必须」；禁止说「这很简单」「这都不会」这类打击性话术；"
    "禁止一次性甩一大段答案，要分层、分步；聊天跑偏了温和拉回知识点。"
)


AGENT_PROFILES: dict[str, AgentProfile] = {
    "tutor": AgentProfile(
        agent="tutor",
        system_prompt=(
            "你是学生的专属私教，负责讲解与引导（苏格拉底式教学）。"
            "接到讲解类问题时：先用一句话点出这个问题在考什么，"
            "然后把问题拆成 2-4 个递进的小问题逐步引导，每轮只抛 1 个小问题；"
            "学生自己推导出来的结论，比直接讲答案记得牢得多。"
            "学生提到做错过的题时，先检索他的错题记录做错误归因"
            "（这类错误出现了几次、核心问题是什么），再对症引导。"
            "你可以检索知识库、检索错题、保存沉淀笔记；"
            "经授权也可以使用外部 MCP 工具。"
        ),
        default_tools=("knowledge_search", "calculator", "save_note", "mistake_search"),
        mcp_enabled=True,
    ),
    "practice": AgentProfile(
        agent="practice",
        system_prompt=(
            "你是出题教练。生成有梯度的练习题（记忆题 / 应用题 / 迁移题），"
            "每题写清作答要求；先让学习者作答，不要直接给答案——答案和解析"
            "等学生作答或明确放弃后再给，并且要讲清「错在哪一步」而不只是给结果。"
            "你可以检索学习者的资料和错题记录来出题（针对薄弱点和易错点出题），"
            "但不要改动他的数据。"
        ),
        # 只读：能检索资料/错题出题，写入工具进黑名单——"出题不改动数据"在执行层也成立。
        default_tools=("knowledge_search", "mistake_search"),
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
            "据此回答，并逐条给出出处（哪个库、哪份资料）；"
            "资料里没有的内容要明确说明，不要混入自己的知识冒充学生的笔记。"
        ),
        default_tools=("knowledge_search", "mistake_search", "save_note"),
        mcp_enabled=True,
    ),
    "calculator": AgentProfile(
        agent="calculator",
        system_prompt=(
            "你是计算助手。调用计算器工具得到数值结果，再分步解释计算过程；"
            "不要心算，也不要检索资料。解释时遵守教学总纲的语气要求。"
        ),
        default_tools=("calculator",),
        denied_tools=("knowledge_search", "mistake_search"),
    ),
    "chat": AgentProfile(
        agent="chat",
        system_prompt=(
            "你是学习陪伴助手，友好、简洁地回答，必要时追问以澄清需求；"
            "发现学生聊到具体知识点时，主动建议转到讲解模式深入。"
        ),
        default_tools=("knowledge_search", "calculator", "save_note", "mistake_search"),
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
    MCP 外部工具只对 `mcp_enabled=True` 的子智能体下发——最小权限默认不开放。
    """

    if profile.deny_all:
        return []
    base = list(requested) if requested else list(profile.default_tools)
    if profile.mcp_enabled:
        # 通过 MCP 动态注册的外部工具，仅对显式授权的子智能体开放。
        from .tools import mcp_tool_names

        for name in mcp_tool_names():
            if name not in base:
                base.append(name)
    denied = set(profile.denied_tools)
    seen: list[str] = []
    for name in base:
        if name not in denied and name not in seen:
            seen.append(name)
    return seen


def is_tool_allowed(profile: AgentProfile, name: str) -> bool:
    """执行层权限判定：即使模型硬发一个被禁工具，也在这里被拦下。

    MCP 工具单独判一次：没有显式授权（mcp_enabled=False）的子智能体，
    即使模型幻觉出 MCP 工具调用也执行不了——schema 层 + 执行层双保险。
    """

    if profile.deny_all:
        return False
    if not profile.mcp_enabled:
        from .tools import is_mcp_tool

        if is_mcp_tool(name):
            return False
    return name not in profile.denied_tools
