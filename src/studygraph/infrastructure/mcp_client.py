"""最小 MCP（Model Context Protocol）stdio 客户端——零外部依赖。

Anthropic 把 MCP 列为"连接外部工具/能力的标准方式"。这里实现 stdio 传输的
JSON-RPC 2.0 客户端：启动 server 子进程、`initialize` 握手、`tools/list` 发现工具、
`tools/call` 调用工具。消息按**换行分隔的 JSON**收发（stdio 传输约定）。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

_PROTOCOL_VERSION = "2024-11-05"


class McpError(RuntimeError):
    pass


class McpStdioClient:
    def __init__(
        self, name: str, command: str, args: list[str] | None = None, *, timeout: float = 15.0
    ) -> None:
        self.name = name
        self._command = command
        self._args = args or []
        self._timeout = timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._id = 0

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "studygraph", "version": "0.1.0"},
            },
        )
        await self._notify("notifications/initialized", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._request("tools/list", {})
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self._request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        parts = result.get("content", [])
        texts = [
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)

    async def close(self) -> None:
        if self._proc is None or self._proc.returncode is not None:
            return
        self._proc.terminate()
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=5)
        except TimeoutError:  # pragma: no cover - 进程不退出时强杀
            self._proc.kill()

    # -- JSON-RPC -------------------------------------------------------------

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("MCP 客户端尚未启动")
        self._proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise McpError("MCP 客户端尚未启动")
        line = await asyncio.wait_for(self._proc.stdout.readline(), self._timeout)
        if not line:
            raise McpError("MCP server 已关闭连接")
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - 脏输出
            raise McpError(f"无法解析 MCP 消息：{line!r}") from exc

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        request_id = self._id
        await self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        while True:
            message = await self._read()
            if message.get("id") != request_id:
                continue  # 跳过 server 的通知
            if "error" in message:
                raise McpError(str(message["error"]))
            result = message.get("result", {})
            return result if isinstance(result, dict) else {}

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})
