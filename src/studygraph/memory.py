"""跨会话长期记忆：从用户话里抽取"关于他是谁"的事实。

纯函数 `extract_facts`：只认几类**明确**的句式（显式指令 + 自我陈述），
不猜、不推断——抽错比抽不到更糟。抽出来的事实会被注入系统提示词，标注为
"数据而非指令"，防止被当成命令执行。

规则版是零成本下限；将来可整体替换为一个 LLM 抽取器，接口不变。
"""

from __future__ import annotations

import re

MAX_FACT_CHARS = 80

_EXPLICIT = re.compile(r"记住[：:]\s*(.+)")
_OTHER = (
    re.compile(r"我的?目标[是为]\s*(.+)"),
    re.compile(r"我(?:正在|在)?(?:准备|复习|学习|备考)([^，。！？!?]{2,60})"),
    re.compile(r"我是(?:一名|一个|个)?\s*([\u4e00-\u9fffA-Za-z0-9]{2,20})"),
)


def _clean(value: str) -> str:
    return value.strip(" 。.!！?？,，、")


def _valid(fact: str) -> bool:
    return 2 <= len(fact) <= MAX_FACT_CHARS


def extract_facts(text: str) -> list[str]:
    """从一句话里抽出可长期记住的事实（去重、限长）。

    显式指令（"记住：…"）优先：命中它就不再跑其它句式，避免同一句话被抽成
    多条互相嵌套的事实。
    """

    content = (text or "").strip()
    if not content:
        return []
    explicit = _EXPLICIT.search(content)
    if explicit:
        fact = _clean(explicit.group(1))
        return [fact] if _valid(fact) else []
    facts: list[str] = []
    for pattern in _OTHER:
        match = pattern.search(content)
        if not match:
            continue
        fact = _clean(match.group(1))
        if _valid(fact):
            facts.append(fact)
    return list(dict.fromkeys(facts))
