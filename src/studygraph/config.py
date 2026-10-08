"""运行配置：全部来自环境变量，默认零成本（Mock 模型）。

设计原则：默认值必须让 `uv run python -m studygraph.cli ...` 开箱即用、不消耗
任何 API 额度。接真实模型只需设置环境变量，不改代码。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "mock"
    model: str = "study-mock"
    openai_base_url: str = ""
    openai_api_key: str = ""
    max_output_tokens: int = 2048
    database_path: str = "data/studygraph.db"
    knowledge_root: str = "data/knowledge"
    user_id: str = "local"
    max_tool_rounds: int = 6


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.environ.get("STUDYGRAPH_LLM_PROVIDER", "mock").strip().lower(),
        model=os.environ.get("STUDYGRAPH_MODEL", "study-mock"),
        openai_base_url=os.environ.get("STUDYGRAPH_OPENAI_BASE_URL", ""),
        openai_api_key=os.environ.get("STUDYGRAPH_OPENAI_API_KEY", ""),
        max_output_tokens=int(os.environ.get("STUDYGRAPH_MAX_OUTPUT_TOKENS", "2048")),
        database_path=os.environ.get("STUDYGRAPH_DATABASE_PATH", "data/studygraph.db"),
        knowledge_root=os.environ.get("STUDYGRAPH_KNOWLEDGE_ROOT", "data/knowledge"),
        user_id=os.environ.get("STUDYGRAPH_USER", "local"),
        max_tool_rounds=int(os.environ.get("STUDYGRAPH_MAX_TOOL_ROUNDS", "6")),
    )
