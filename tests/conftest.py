"""全局测试护栏：任何测试都不许碰到项目里的真实数据库。

历史教训：`data/zhiji.db` 里混进了 user_id=alice 的测试项目/会话，
说明曾经有测试用相对路径落到了真实库上。这里把所有测试的工作目录切到
临时目录——Settings 的默认 `database_path` 是相对路径
`data/zhiji.db`，CWD 一变，写入就落在临时盘里。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_working_directory(tmp_path, monkeypatch):
    """每个测试都在自己的临时目录里跑，杜绝误写真实数据库/知识库目录。

    同时隔离本机 `.env` 的模型/搜索配置：测试里 web_search 若因本机配了
    DeepSeek 而触发真实联网搜索，会消耗 API 且结果不可测——统一禁用，
    需要测 DeepSeek 路径的测试自行 monkeypatch。
    """

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZHIJI_DEEPSEEK_SEARCH", "0")
    monkeypatch.delenv("ZHIJI_OPENAI_API_KEY", raising=False)
