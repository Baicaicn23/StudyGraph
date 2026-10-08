from __future__ import annotations

import sys
from pathlib import Path

from studygraph.infrastructure.mcp_bridge import connect_and_register
from studygraph.infrastructure.mcp_client import McpStdioClient

_SERVER = Path(__file__).parent / "fake_mcp_server.py"


def _configs() -> list[dict]:
    return [{"name": "fake", "command": sys.executable, "args": [str(_SERVER)]}]


async def test_mcp_client_lists_and_calls_tools() -> None:
    client = McpStdioClient("fake", sys.executable, [str(_SERVER)])
    await client.start()
    try:
        tools = await client.list_tools()
        assert tools and tools[0]["name"] == "echo"
        assert await client.call_tool("echo", {"text": "hi"}) == "echo:hi"
    finally:
        await client.close()


async def test_bridge_registers_callable_langchain_tool() -> None:
    registered: dict[str, object] = {}
    clients, names = await connect_and_register(
        _configs(), lambda name, tool: registered.__setitem__(name, tool)
    )
    try:
        assert names and "mcp_fake_echo" in registered
        tool = registered["mcp_fake_echo"]
        assert await tool.ainvoke({"text": "yo"}) == "echo:yo"  # type: ignore[attr-defined]
    finally:
        for client in clients:
            await client.close()


async def test_bridge_ignores_broken_server() -> None:
    clients, names = await connect_and_register(
        [{"name": "broken", "command": "/nonexistent/binary", "args": []}],
        lambda name, tool: None,
    )
    assert clients == []
    assert names == []
