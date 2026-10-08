"""模型适配（基础设施）：Mock（默认，零成本）与 OpenAI 兼容（可选）。

Mock 模型按固定规则**模拟工具调用**——看到算式调计算器、看到"记住/沉淀"调保存、
看到"资料/知识库"调检索。这样全链路（路由、工具循环、流式、检查点、HITL）都能
在**零 API 消耗**下被确定性地测试和演示。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from ..config import Settings

_MATH_RE = re.compile(r"\d[\d\.\s]*(?:[\+\-\*/×÷\^%]\s*\d[\d\.\s]*)+")
_SAVE_HINTS = ("记住", "记下", "存进", "存一下", "沉淀", "保存")
_SEARCH_HINTS = ("资料", "知识库", "笔记", "文档", "检索", "查一下", "出处", "我上传", "讲义")


def _tool_name(tool: Any) -> str | None:
    if isinstance(tool, dict):
        return (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None) or getattr(tool, "__name__", None)


def _last_human_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _used_tool_since_last_human(messages: Sequence[BaseMessage]) -> ToolMessage | None:
    last_human = -1
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            last_human = index
    for message in messages[last_human + 1 :]:
        if isinstance(message, ToolMessage):
            return message
    return None


class MockChatModel(BaseChatModel):
    """确定性的假模型：按固定规则产出工具调用或回答。"""

    tool_names: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "study-mock"

    def bind_tools(
        self, tools: Sequence[Any], *, tool_choice: str | None = None, **kwargs: Any
    ) -> MockChatModel:
        names = [name for tool in tools if (name := _tool_name(tool))]
        return self.model_copy(update={"tool_names": names})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        message = self._decide(messages)
        message = message.model_copy(
            update={"usage_metadata": self._estimate_usage(messages, message)}
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    @staticmethod
    def _estimate_usage(messages: list[BaseMessage], message: AIMessage) -> dict[str, int]:
        """粗略估 token（字符数/2）——让 Mock 也能驱动 token 记账与预算。"""

        prompt_chars = sum(len(str(getattr(m, "content", ""))) for m in messages)
        output_chars = len(str(getattr(message, "content", "")))
        input_tokens = prompt_chars // 2 + 1
        output_tokens = output_chars // 2 + 1
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    def _decide(self, messages: list[BaseMessage]) -> AIMessage:
        tool_result = _used_tool_since_last_human(messages)
        if tool_result is not None:
            return AIMessage(
                content=f"（模拟模型）根据工具返回的结果：{str(tool_result.content)[:280]}"
            )

        text = _last_human_text(messages)
        available = set(self.tool_names)

        if "calculator" in available:
            match = _MATH_RE.search(text)
            if match:
                expression = match.group().strip().replace("×", "*").replace("÷", "/")
                return self._call("calculator", {"expression": expression})

        if "save_note" in available and any(hint in text for hint in _SAVE_HINTS):
            title = text.strip()[:30] or "学习笔记"
            return self._call(
                "save_note",
                {"title": title, "content": text.strip(), "library": "日常沉淀"},
            )

        if "knowledge_search" in available and any(
            hint in text for hint in _SEARCH_HINTS
        ):
            return self._call("knowledge_search", {"query": text.strip()})

        topic = text.strip()[:40] or "你的问题"
        return AIMessage(
            content=(
                f"（模拟模型）关于「{topic}」，我会先给出直觉和结论，"
                "再解释背后的原理，最后用一个具体例子验证。"
                "（接入真实模型后会给出完整讲解。）"
            )
        )

    @staticmethod
    def _call(name: str, arguments: dict[str, Any]) -> AIMessage:
        return AIMessage(
            content="",
            tool_calls=[{"name": name, "args": arguments, "id": f"call-{name}-1"}],
        )


def build_chat_model(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider
    if provider in ("", "mock"):
        return MockChatModel()
    if provider in ("openai", "openai-compatible"):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "接入真实模型需要 langchain-openai：请执行 `uv sync --extra openai`"
            ) from exc
        return ChatOpenAI(
            model=settings.model,
            base_url=settings.openai_base_url or None,
            api_key=settings.openai_api_key or "not-needed",
            max_tokens=settings.max_output_tokens,
            temperature=0.3,
        )
    raise ValueError(f"未知的 LLM Provider：{provider}")
