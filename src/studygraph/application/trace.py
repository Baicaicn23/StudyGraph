"""回合 trace：把一段会话历史读成"哪一步出了问题"的诊断。

这不是日志，而是**归因**：不满足于"失败了"，要指出责任层。能从消息历史推断的
责任层有四类（更细的编排/费用层需要事件元数据，见文档"当前边界"）：

    retrieval  检索返回空结果（模型没有资料可用）
    tool       工具调用失败（权限拦截或执行错误）
    model      没有产出最终回答
    ok         正常结束
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

ATTRIBUTION_LAYERS = ("retrieval", "tool", "model", "ok")


def _is_error(content: str) -> bool:
    return (
        content.startswith("[tool_not_allowed]")
        or content.startswith("[unknown_tool]")
        or "出错" in content
    )


def _is_empty(content: str) -> bool:
    return "没有找到" in content or content.strip() == ""


def diagnose(messages: list[Any], state: dict[str, Any]) -> dict[str, Any]:
    last_user = ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            last_user = str(message.content)
            break

    tool_calls: list[dict[str, Any]] = []
    empty_sources = False
    tool_error = False
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        content = str(message.content)
        empty = _is_empty(content)
        error = _is_error(content)
        tool_calls.append({"name": message.name, "ok": not error, "empty": empty})
        empty_sources = empty_sources or empty
        tool_error = tool_error or error

    answered = False
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            answered = bool(message.content) and not getattr(message, "tool_calls", None)
            break

    if empty_sources:
        attribution = "retrieval"
    elif tool_error:
        attribution = "tool"
    elif not answered:
        attribution = "model"
    else:
        attribution = "ok"

    warnings: list[str] = []
    if empty_sources:
        warnings.append("检索返回空结果：模型没有资料可用")
    if tool_error:
        warnings.append("有工具调用失败（权限拦截或执行错误）")
    if not answered:
        warnings.append("没有产出最终回答")

    return {
        "last_user": last_user,
        "intent": state.get("intent"),
        "agent": state.get("agent"),
        "tool_calls": tool_calls,
        "answered": answered,
        "empty_sources": empty_sources,
        "attribution": attribution,
        "warnings": warnings,
    }


def render(diagnosis: dict[str, Any], *, thread: str) -> str:
    lines = [f"回合 thread={thread}"]
    lines.append(f"├─ 用户消息： {diagnosis['last_user']}")
    if diagnosis["intent"]:
        lines.append(f"├─ 意图：{diagnosis['intent']}  →  {diagnosis['agent']}")
    for call in diagnosis["tool_calls"]:
        mark = "空" if call["empty"] else ("失败" if not call["ok"] else "ok")
        lines.append(f"├─ 工具：{call['name']}  [{mark}]")
    lines.append(f"└─ 归因：{diagnosis['attribution']}")
    for warning in diagnosis["warnings"]:
        lines.append(f"   ⚠ {warning}")
    return "\n".join(lines)
