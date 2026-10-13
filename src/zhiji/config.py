"""运行配置：全部来自环境变量，默认零成本（Mock 模型）。

设计原则：默认值必须让 `uv run python -m zhiji.cli ...` 开箱即用、不消耗
任何 API 额度。接真实模型只需设置环境变量（或项目根目录 `.env`，已被 Git
忽略），不改代码。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    """加载项目根目录的 .env（不覆盖已有环境变量；文件不存在则跳过）。"""

    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # config.py 位于 <root>/src/zhiji/，向上两级是项目根。
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


_load_dotenv()


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
    # 向量服务的独立地址/Key（空 = 回落 openai_base_url / openai_api_key）——
    # 主模型是 DeepSeek 时它没有 /embeddings 接口，需单独配（如硅基流动 bge-m3）
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    database_path: str = "data/zhiji.db"
    knowledge_root: str = "data/knowledge"
    user_id: str = "local"
    max_tool_rounds: int = 6
    tool_timeout_seconds: float = 10.0
    tool_max_retries: int = 2
    max_history_messages: int = 24
    max_upload_bytes: int = 5_000_000
    mcp_servers: str = ""
    # 可选：Tavily 联网搜索的 API Key（配了就用 Tavily，稳定；不配则回落 DuckDuckGo）
    tavily_api_key: str = ""
    # 可选：博查 Web Search API Key（中文搜索质量最好，付费；配了在 Tavily 之前优先用）
    bocha_api_key: str = ""
    # 可选：自定义同义词组文件（JSON，每项 = 一组等价术语）——追加在内置表之后
    synonyms_file: str = ""


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.environ.get("ZHIJI_LLM_PROVIDER", "mock").strip().lower(),
        model=os.environ.get("ZHIJI_MODEL", "study-mock"),
        model_small=os.environ.get("ZHIJI_MODEL_SMALL", ""),
        model_large=os.environ.get("ZHIJI_MODEL_LARGE", ""),
        openai_base_url=os.environ.get("ZHIJI_OPENAI_BASE_URL", ""),
        openai_api_key=os.environ.get("ZHIJI_OPENAI_API_KEY", ""),
        max_output_tokens=int(os.environ.get("ZHIJI_MAX_OUTPUT_TOKENS", "2048")),
        daily_token_budget=int(os.environ.get("ZHIJI_DAILY_TOKEN_BUDGET", "0")),
        budget_exceeded_action=os.environ.get(
            "ZHIJI_BUDGET_EXCEEDED_ACTION", "block"
        ),
        embedding_provider=os.environ.get("ZHIJI_EMBEDDING_PROVIDER", "mock")
        .strip()
        .lower(),
        embedding_model=os.environ.get(
            "ZHIJI_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
        embedding_dim=int(os.environ.get("ZHIJI_EMBEDDING_DIM", "256")),
        embedding_base_url=os.environ.get("ZHIJI_EMBEDDING_BASE_URL", "").strip(),
        embedding_api_key=os.environ.get("ZHIJI_EMBEDDING_API_KEY", "").strip(),
        database_path=os.environ.get("ZHIJI_DATABASE_PATH", "data/zhiji.db"),
        knowledge_root=os.environ.get("ZHIJI_KNOWLEDGE_ROOT", "data/knowledge"),
        user_id=os.environ.get("ZHIJI_USER", "local"),
        max_tool_rounds=int(os.environ.get("ZHIJI_MAX_TOOL_ROUNDS", "6")),
        tool_timeout_seconds=float(
            os.environ.get("ZHIJI_TOOL_TIMEOUT_SECONDS", "10")
        ),
        tool_max_retries=int(os.environ.get("ZHIJI_TOOL_MAX_RETRIES", "2")),
        max_history_messages=int(
            os.environ.get("ZHIJI_MAX_HISTORY_MESSAGES", "24")
        ),
        max_upload_bytes=int(
            os.environ.get("ZHIJI_MAX_UPLOAD_BYTES", "5000000")
        ),
        mcp_servers=os.environ.get("ZHIJI_MCP_SERVERS", ""),
        tavily_api_key=os.environ.get(
            "ZHIJI_TAVILY_API_KEY", ""
        ).strip(),
        bocha_api_key=os.environ.get(
            "ZHIJI_BOCHA_API_KEY", ""
        ).strip(),
        synonyms_file=os.environ.get("ZHIJI_SYNONYMS_FILE", "").strip(),
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
