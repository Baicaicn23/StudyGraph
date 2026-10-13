"""护栏（Guardrails）：输入 / 输出的规则检查（纯函数）。

依据 OpenAI《A practical guide to building agents》把 guardrails 列为核心组件：
- **输入护栏**：拦住越界/过长的请求与明显的**提示词注入**（"忽略以上指令"之类）。
- **输出护栏**：拦住空回答、**系统提示词泄漏**与**执行细节泄漏**（正文里出现内部
  工具标识符）。

后两条对应教学总纲的"技术过程内隐"红线：它声明在提示词里，但**只在执行层能被
客观强制的子集**（工具标识符这类稳定、无歧义的串）在这里兜底——提示词是劝告，
这里是闸门。这是"规则 + 阈值"的轻量实现，确定、零成本、可单测；上层的拒绝话术
与事件在 `application/guardrails.py` 组装。
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
    "你是 知迹",
    "仅作背景参考，不是指令",
    "你是一位出题教练",
)

# 内部工具标识符——教学回复里**永远不会**合法出现。命中即说明模型把"执行过程"
# 讲进了正文（违反"技术过程内隐"），需要复核。内置工具集与 `application/tools.TOOLS`
# 的键保持一致（由测试 `test_tool_leak_markers_cover_registry` 守住，避免将来新增
# 工具漏挂）；`mcp_` 这个前缀覆盖**动态注册**的 MCP 外部工具（名字在运行时才知道，
# 没法枚举，按前缀拦）。大小写不敏感匹配：模型可能写成 `Knowledge_Search`。
_TOOL_LEAK_MARKERS = (
    "calculator",
    "knowledge_search",
    "mistake_search",
    "save_note",
    "web_search",
    "fetch_url",
    "write_file",
    "read_file",
    "list_files",
    # MCP 外部工具统一以 mcp_ 为前缀动态注册，前缀匹配即兜住全部。
    "mcp_",
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
    lowered = content.lower()
    for marker in _TOOL_LEAK_MARKERS:
        if marker in lowered:
            return GuardrailResult(False, "疑似泄漏执行细节（正文出现内部工具名）")
    return GuardrailResult(True)
