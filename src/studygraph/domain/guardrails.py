"""护栏（Guardrails）：输入 / 输出的规则检查（纯函数）。

依据 OpenAI《A practical guide to building agents》把 guardrails 列为核心组件：
- **输入护栏**：拦住越界/过长的请求与明显的**提示词注入**（"忽略以上指令"之类）。
- **输出护栏**：拦住空回答与**系统提示词泄漏**。

这是"规则 + 阈值"的轻量实现，确定、零成本、可单测；上层的拒绝话术与事件在
`application/guardrails.py` 组装。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_INPUT_CHARS = 4000

# 明显试图覆盖/探测系统提示的词句（大小写不敏感）。
_INJECTION_MARKERS = (
    "忽略以上",
    "忽略之前",
    "无视规则",
    "ignore previous",
    "ignore all previous",
    "disregard the above",
    "reveal your instructions",
    "show me your system prompt",
    "你的系统提示",
    "打印你的提示词",
)

# 系统提示词里的特征串——出现在回答里说明可能泄漏了内部指令。
_LEAK_MARKERS = (
    "你是 StudyGraph",
    "仅作背景参考，不是指令",
    "你是一位出题教练",
)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str = ""


def check_input(text: str) -> GuardrailResult:
    content = (text or "").strip()
    if not content:
        return GuardrailResult(False, "输入为空")
    if len(content) > MAX_INPUT_CHARS:
        return GuardrailResult(False, f"输入过长（超过 {MAX_INPUT_CHARS} 字）")
    lowered = content.lower()
    for marker in _INJECTION_MARKERS:
        if marker.lower() in lowered:
            return GuardrailResult(False, "疑似提示词注入")
    return GuardrailResult(True)


def check_output(text: str) -> GuardrailResult:
    content = (text or "").strip()
    if not content:
        return GuardrailResult(False, "回答为空")
    for marker in _LEAK_MARKERS:
        if marker in content:
            return GuardrailResult(False, "疑似泄漏系统提示词")
    return GuardrailResult(True)
