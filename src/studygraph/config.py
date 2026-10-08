"""运行配置：全部来自环境变量，默认零成本（Mock 模型）。

设计原则：默认值必须让 `uv run python -m studygraph.cli ...` 开箱即用、不消耗
任何 API 额度。接真实模型只需设置环境变量，不改代码。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "mock"
    model: str = "study-mock"
    model_small: str = ""
    model_large: str = ""
    openai_base_url: str = ""
    openai_api_key: str = ""
    max_output_tokens: int = 2048
    daily_token_budget: int = 0
    budget_exceeded_action: str = "block"
    embedding_provider: str = "mock"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 256
    database_path: str = "data/studygraph.db"
    knowledge_root: str = "data/knowledge"
    user_id: str = "local"
    max_tool_rounds: int = 6
    tool_timeout_seconds: float = 10.0
    tool_max_retries: int = 2
    max_history_messages: int = 24
    max_upload_bytes: int = 5_000_000
    mcp_servers: str = ""


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.environ.get("STUDYGRAPH_LLM_PROVIDER", "mock").strip().lower(),
        model=os.environ.get("STUDYGRAPH_MODEL", "study-mock"),
        model_small=os.environ.get("STUDYGRAPH_MODEL_SMALL", ""),
        model_large=os.environ.get("STUDYGRAPH_MODEL_LARGE", ""),
        openai_base_url=os.environ.get("STUDYGRAPH_OPENAI_BASE_URL", ""),
        openai_api_key=os.environ.get("STUDYGRAPH_OPENAI_API_KEY", ""),
        max_output_tokens=int(os.environ.get("STUDYGRAPH_MAX_OUTPUT_TOKENS", "2048")),
        daily_token_budget=int(os.environ.get("STUDYGRAPH_DAILY_TOKEN_BUDGET", "0")),
        budget_exceeded_action=os.environ.get(
            "STUDYGRAPH_BUDGET_EXCEEDED_ACTION", "block"
        ),
        embedding_provider=os.environ.get("STUDYGRAPH_EMBEDDING_PROVIDER", "mock")
        .strip()
        .lower(),
        embedding_model=os.environ.get(
            "STUDYGRAPH_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
        embedding_dim=int(os.environ.get("STUDYGRAPH_EMBEDDING_DIM", "256")),
        database_path=os.environ.get("STUDYGRAPH_DATABASE_PATH", "data/studygraph.db"),
        knowledge_root=os.environ.get("STUDYGRAPH_KNOWLEDGE_ROOT", "data/knowledge"),
        user_id=os.environ.get("STUDYGRAPH_USER", "local"),
        max_tool_rounds=int(os.environ.get("STUDYGRAPH_MAX_TOOL_ROUNDS", "6")),
        tool_timeout_seconds=float(
            os.environ.get("STUDYGRAPH_TOOL_TIMEOUT_SECONDS", "10")
        ),
        tool_max_retries=int(os.environ.get("STUDYGRAPH_TOOL_MAX_RETRIES", "2")),
        max_history_messages=int(
            os.environ.get("STUDYGRAPH_MAX_HISTORY_MESSAGES", "24")
        ),
        max_upload_bytes=int(
            os.environ.get("STUDYGRAPH_MAX_UPLOAD_BYTES", "5000000")
        ),
        mcp_servers=os.environ.get("STUDYGRAPH_MCP_SERVERS", ""),
    )


def parse_mcp_servers(raw: str) -> list[dict]:
    """解析 MCP server 配置（JSON 数组）。非法配置一律忽略，不阻塞启动。"""

    text = (raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [
        item
        for item in data
        if isinstance(item, dict) and item.get("command")
    ]
