"""联网与文件工具的回归测试（全部离线：搜索与抓取都替换成桩）。

锁死的规则：
- 文件工具只能落在工作区内（绝对路径 / .. / 反斜杠穿越都拒绝）；
- web_search 结果格式稳定，网络故障转成可读提示而不是抛异常；
- fetch_url 只允许 http/https 公网地址（SSRF 防护），结果带元信息首行；
- 权限：tutor / retriever / chat 拿到对应的新工具，practice / progress 拿不到。
"""

from __future__ import annotations

import pytest

from zhiji.application import tools
from zhiji.application.routing import allowed_tools, profile_for_agent
from zhiji.config import Settings
from zhiji.interfaces.api import create_app


@pytest.fixture()
def workspace(tmp_path):
    """配置临时工作区 + 用户 u，并在测试后恢复全局状态（contextvar 会跨测试泄漏）。"""

    old_root = tools._workspace_root
    user_token = tools._current_user.set("u")
    tools.configure_workspace(tmp_path / "workspace")
    yield tmp_path / "workspace" / "u"
    tools._current_user.reset(user_token)
    tools._workspace_root = old_root


def test_file_roundtrip_and_listing(workspace) -> None:
    written = tools.write_file.invoke(
        {"filename": "notes/作文模板.md", "content": "# 模板\n正文"}
    )
    assert "已写入" in written and "notes/作文模板.md" in written

    read = tools.read_file.invoke({"filename": "notes/作文模板.md"})
    assert "读取成功" in read and "# 模板" in read

    listing = tools.list_files.invoke({})
    assert "notes/作文模板.md" in listing and "1 个文件" in listing

    # 覆盖写
    tools.write_file.invoke({"filename": "notes/作文模板.md", "content": "v2"})
    assert "v2" in tools.read_file.invoke({"filename": "notes/作文模板.md"})


def test_filename_traversal_blocked(workspace) -> None:
    for bad in ["../evil.txt", "/etc/passwd", "a/../../b.txt", "C:\\x.txt"]:
        out = tools.write_file.invoke({"filename": bad, "content": "x"})
        assert out.startswith("写入失败"), f"{bad} 应被拒绝"
    assert tools.read_file.invoke({"filename": "../../secret"}).startswith("读取失败")
    # 工作区之外没有任何文件被写出来
    assert not (workspace.parent.parent / "evil.txt").exists()


def test_read_missing_file_is_readable_error(workspace) -> None:
    out = tools.read_file.invoke({"filename": "不存在.md"})
    assert out.startswith("读取失败")
    assert "list_files" in out  # 告诉模型下一步怎么办


def test_web_search_formats_and_degrades(workspace, monkeypatch) -> None:
    monkeypatch.setattr(
        tools,
        "_search_web",
        lambda q, n: [
            {
                "title": "六级作文模板",
                "body": "三段式议论文章法",
                "href": "https://example.com/a",
            }
        ],
    )
    out = tools.web_search.invoke({"queries": ["英语六级作文模板"]})
    assert out.startswith("共合并 1 条") and "1 个查询召回 1 条" in out
    assert "【六级作文模板】" in out and "https://example.com/a" in out

    def boom(query, max_results):
        raise RuntimeError("network down")

    monkeypatch.setattr(tools, "_search_web", boom)
    degraded = tools.web_search.invoke({"queries": ["x"]})
    assert degraded.startswith("联网搜索失败") and "RuntimeError" in degraded

    assert tools.web_search.invoke({"queries": []}).startswith("联网搜索失败")


def test_fetch_url_guard_and_format(workspace, monkeypatch) -> None:
    for bad in [
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://192.168.1.2/x",
        "http://169.254.1.1/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ]:
        assert tools.fetch_url.invoke({"url": bad}).startswith("读取网页失败"), bad

    monkeypatch.setattr(tools, "_fetch_page_text", lambda url: "正文第一行\n正文第二行")
    out = tools.fetch_url.invoke({"url": "https://example.com/page"})
    assert out.startswith("读取成功：example.com")
    assert "正文第一行" in out

    # 非文本内容类型被拒
    def binary(url):
        raise ValueError("不支持的内容类型：image/png")

    monkeypatch.setattr(tools, "_fetch_page_text", binary)
    assert tools.fetch_url.invoke({"url": "https://example.com/a.png"}).startswith(
        "读取网页失败"
    )


def test_profiles_get_new_tools() -> None:
    tutor = allowed_tools(profile_for_agent("tutor"), None)
    assert {"web_search", "fetch_url", "write_file", "read_file", "list_files"} <= set(
        tutor
    )

    retriever = allowed_tools(profile_for_agent("retriever"), None)
    assert {
        "web_search",
        "fetch_url",
        "write_file",
        "read_file",
        "list_files",
    } <= set(retriever)

    practice = allowed_tools(profile_for_agent("practice"), None)
    assert "web_search" not in practice and "write_file" not in practice

    # chat 也是通用助手：联网 + 文件能力齐备
    chat = allowed_tools(profile_for_agent("chat"), None)
    assert {"web_search", "fetch_url", "write_file", "read_file", "list_files"} <= set(
        chat
    )

    assert allowed_tools(profile_for_agent("progress"), None) == []


def test_app_wires_workspace(tmp_path) -> None:
    """组合根把工作区指到 data 目录下；不配置时回落到 data/workspace。"""

    from fastapi.testclient import TestClient

    settings = Settings(database_path=str(tmp_path / "api.db"))
    with TestClient(create_app(settings)):
        # 显式设定用户：别的测试文件可能泄漏 contextvar，这里不依赖全局状态
        tools.set_current_user("local")
        out = tools.write_file.invoke({"filename": "hello.md", "content": "hi"})
        assert "已写入" in out, out
        expected = tmp_path / "workspace" / "local" / "hello.md"
        assert expected.exists(), f"应落在本次测试的 tmp 工作区：{out}"


def test_tavily_takes_priority_and_formats(monkeypatch) -> None:
    """配置了 Tavily Key → 走 Tavily；没配 / 失败 → 回落 DuckDuckGo。"""

    from zhiji.config import Settings

    monkeypatch.setattr(
        tools, "_workspace_dir", lambda: __import__("pathlib").Path("/tmp/ignore")
    )
    monkeypatch.setattr(
        "zhiji.config.get_settings",
        lambda: Settings(tavily_api_key="tvly-test"),
    )
    calls = {"tavily": 0, "ddg": 0}

    def fake_tavily(query, n):
        calls["tavily"] += 1
        return [{"title": "T", "body": "B", "href": "https://t.example/a"}]

    def fake_ddg(query, n):
        calls["ddg"] += 1
        return [{"title": "D", "body": "B2", "href": "https://d.example/a"}]

    monkeypatch.setattr(tools, "_tavily_text", fake_tavily)
    monkeypatch.setattr(tools, "_bing_cn_text", fake_tavily)
    monkeypatch.setattr(tools, "_ddg_text", fake_ddg)

    out = tools.web_search.invoke({"queries": ["六级作文"]})
    assert calls["tavily"] == 1 and calls["ddg"] == 0
    assert "【T】" in out

    # Tavily 失败 → 回落 DDG
    def broken_tavily(query, n):
        raise RuntimeError("tavily down")

    monkeypatch.setattr(tools, "_tavily_text", broken_tavily)
    monkeypatch.setattr(tools, "_bing_cn_text", broken_tavily)
    out = tools.web_search.invoke({"queries": ["六级作文"]})
    assert calls["ddg"] == 1 and "【D】" in out

    # 没配 Key → 直接 DDG
    monkeypatch.setattr(
        "zhiji.config.get_settings", lambda: Settings(tavily_api_key="")
    )
    out = tools.web_search.invoke({"queries": ["六级作文"]})
    assert calls["ddg"] == 2


def test_multi_query_merge_dedupe_and_rerank(monkeypatch) -> None:
    """多路召回：多查询合并 → URL/标题去重 → 权威度排序。"""

    def fake_search(query, n):
        if "教程" in query:
            return [
                {
                    "title": "菜鸟教程 DP",
                    "body": "动态规划 教程 入门",
                    "href": "https://www.runoob.com/dp",
                },
                {
                    "title": "重复文章",
                    "body": "动态规划 解法",
                    "href": "https://blog.csdn.net/a",
                },
            ]
        return [
            {
                "title": "重复文章",
                "body": "动态规划 解法",
                "href": "https://blog.csdn.net/a",
            },
            {
                "title": "维基 DP",
                "body": "动态规划 定义 适用条件",
                "href": "https://zh.wikipedia.org/wiki/DP",
            },
            # 与查询零相关的词典/机构页：相关性过滤应把它们丢掉
            {"title": "六（汉字）- 词典释义", "body": "数字六的解释", "href": "https://dict.example/liu"},
            {"title": "教师资格考试官网", "body": "报名入口", "href": "https://ntce.example/x"},
        ]

    monkeypatch.setattr(tools, "_search_web", fake_search)
    out = tools.web_search.invoke(
        {"queries": ["动态规划 教程", "动态规划 定义"], "max_results": 8}
    )
    lines = [line for line in out.split("\n") if line.startswith("【")]
    # 相关性过滤：零相关的词典/机构页被丢弃
    assert not any("词典" in line or "教师资格" in line for line in lines)
    # 相关性优先于权威度：菜鸟（标题+正文命中多）在维基（仅正文命中）之前
    assert lines[0].startswith("【菜鸟教程 DP】")
    assert lines[1].startswith("【维基 DP】")
    # 去重：同一篇「重复文章」只出现一次
    assert sum(1 for line in lines if "重复文章" in line) == 1


def test_merge_and_rank_caps_per_domain() -> None:
    rows = [
        {"title": f"t{i} 相关", "body": f"t0 相关内容 {i}", "href": f"https://same.example/{i}"}
        for i in range(5)
    ]
    picked = tools._merge_and_rank([rows], 10, queries=["t0 相关"])
    assert len(picked) == tools._MAX_PER_DOMAIN


def test_fetch_url_focus_extracts_relevant_paragraphs(monkeypatch) -> None:
    text = "\n".join(
        [
            "网站导航 | 首页 | 联系我们 | 版权所有 © 某某网站",
            "动态规划是一种把原问题分解为子问题的方法，核心是状态转移方程。",
            "本站使用 Cookie 收集浏览数据并用于广告投放，请阅读隐私政策。",
            "记忆化搜索避免了重复计算，大幅提升时间效率。",
        ]
    )
    monkeypatch.setattr(tools, "_fetch_page_text", lambda url: text)
    out = tools.fetch_url.invoke(
        {"url": "https://example.com/dp", "focus": "动态规划 状态转移 记忆化"}
    )
    assert "状态转移方程" in out and "记忆化搜索" in out
    assert "Cookie" not in out and "网站导航" not in out
