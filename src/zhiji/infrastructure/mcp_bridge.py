"""把 MCP server 发现的工具桥接成 LangChain 工具并注册进工具表。

- 从 `inputSchema`（JSON Schema）动态生成参数模型。
- 工具名加上 `mcp_<server>_<tool>` 前缀，避免与内置工具冲突。
- server 起不来或列工具失败**不阻塞应用启动**（MCP 是可选增强）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

from .mcp_client import McpStdioClient

_JSON_TO_PY = {"integer": int, "number": float, "boolean": bool}


def _args_model(name: str, schema: dict[str, Any] | None):
    properties = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])
    fields: dict[str, Any] = {}
    for prop_name, spec in properties.items():
        py_type = _JSON_TO_PY.get((spec or {}).get("type"), str)
        if prop_name in required:
            fields[prop_name] = (py_type, ...)
        else:
            fields[prop_name] = (py_type | None, None)
    return create_model(f"{name}_args", **fields)


def _to_tool(client: McpStdioClient, name: str, spec: dict[str, Any]) -> StructuredTool:
    tool_name = str(spec.get("name", ""))
    description = str(spec.get("description") or name)

    async def _call(**kwargs: Any) -> str:
        arguments = {key: value for key, value in kwargs.items() if value is not None}
        return await client.call_tool(tool_name, arguments)

    return StructuredTool.from_function(
        coroutine=_call,
        name=name,
        description=description,
        args_schema=_args_model(name, spec.get("inputSchema")),
    )


async def connect_and_register(
    configs: list[dict[str, Any]] | None,
    register: Callable[[str, Any], None],
) -> tuple[list[McpStdioClient], list[str]]:
    clients: list[McpStdioClient] = []
    registered: list[str] = []
    for config in configs or []:
        name = str(config.get("name", "mcp"))
        try:
            client = McpStdioClient(
                name, str(config["command"]), list(config.get("args") or [])
            )
            await client.start()
        except Exception:  # noqa: BLE001 — server 起不来不阻塞启动
            continue
        clients.append(client)
        try:
            specs = await client.list_tools()
        except Exception:  # noqa: BLE001
            continue
        for spec in specs:
            tool_name = f"mcp_{name}_{spec.get('name', 'tool')}"
            register(tool_name, _to_tool(client, tool_name, spec))
            registered.append(tool_name)
    return clients, registered
