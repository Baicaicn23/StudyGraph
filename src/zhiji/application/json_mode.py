"""结构化输出的统一调用入口（JSON 模式，response_format=json_object）。

出题 / 规划 / 智能选库三处都要求模型输出合法 JSON，过去只靠提示词约束 +
手动容错解析。这里统一改为**优先以 JSON 模式请求**（OpenAI 兼容的
`response_format` 参数，DeepSeek / GLM 均支持），服务端保证合法 JSON；
个别 provider 不认该参数报错时自动去掉重试一次——调用方原有的解析兜底
逻辑保持不变，只是失败率大幅下降。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

from .ports import ChatModelPort

_JSON_KWARGS: dict[str, Any] = {"response_format": {"type": "json_object"}}


async def invoke_json(
    model: ChatModelPort, messages: list[BaseMessage]
) -> BaseMessage:
    """以 JSON 模式调用模型；参数不被支持时自动回落普通调用。"""

    try:
        return await model.ainvoke(messages, **_JSON_KWARGS)
    except Exception:  # noqa: BLE001 — provider 不支持 response_format → 普通调用
        return await model.ainvoke(messages)
